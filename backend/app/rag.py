"""RAG pipeline for non-image file attachments.

Backends (selected via settings.RAG_BACKEND):
- ``pgvector`` — Postgres-native vector search (preferred in server mode)
- ``chroma`` — local ChromaDB under ~/.devpilot/chroma
- ``auto`` — pgvector when DATABASE_URL is Postgres, else ChromaDB

Provides:
- `chunk_file`: line & token-window file chunker preserving line numbers.
- `embed_and_index`: indexes file chunks into the active backend.
- `query`: retrieves top_k relevant chunks for a question.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import time
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger("devpilot.rag")

# Eviction policy configuration (overridable via environment)
_MAX_CHROMA_DIRS = int(os.environ.get("DEVPILOT_MAX_CHROMA_DIRS", "8"))
_MAX_CHROMA_AGE_DAYS = int(os.environ.get("DEVPILOT_CHROMA_MAX_AGE_DAYS", "30"))

_PGVECTOR_DIM = 384  # matches simple hash embedding dimensionality


def _evict_old_chroma_indexes() -> None:
    """Remove ChromaDB workspace indexes that exceed the age or count limits."""
    base = os.path.join(os.path.expanduser("~"), ".devpilot", "chroma")
    if not os.path.isdir(base):
        return

    subdirs = []
    for d in os.listdir(base):
        full_path = os.path.join(base, d)
        if os.path.isdir(full_path):
            try:
                mtime = os.path.getmtime(full_path)
                subdirs.append((full_path, mtime))
            except OSError:
                continue

    if not subdirs:
        return

    now = time.time()
    max_age_secs = _MAX_CHROMA_AGE_DAYS * 86400

    surviving = []
    for path, mtime in subdirs:
        if (now - mtime) > max_age_secs:
            try:
                shutil.rmtree(path)
                logger.info("ChromaDB eviction (age): removed %s", path)
            except Exception as e:
                logger.warning("ChromaDB eviction failed for %s: %s", path, e)
        else:
            surviving.append((path, mtime))

    surviving.sort(key=lambda x: x[1], reverse=True)
    for path, _ in surviving[_MAX_CHROMA_DIRS:]:
        try:
            shutil.rmtree(path)
            logger.info("ChromaDB eviction (count): removed %s", path)
        except Exception as e:
            logger.warning("ChromaDB eviction failed for %s: %s", path, e)


@dataclass
class Chunk:
    """A document text chunk with source location metadata."""

    text: str
    start_line: int
    end_line: int
    source_file: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def chunk_file(path: str, max_tokens: int = 500, overlap: int = 50) -> list[Chunk]:
    """Chunk a file into token-bounded line windows with overlap."""
    if not path or not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as exc:
        logger.error("Failed to read file for chunking '%s': %s", path, exc)
        return []

    if not lines:
        return []

    chunks: list[Chunk] = []
    current_lines: list[str] = []
    current_word_count = 0
    start_line = 1

    for line_idx, line in enumerate(lines, start=1):
        line_words = len(line.split())
        current_lines.append(line)
        current_word_count += line_words

        if current_word_count >= max_tokens:
            chunk_text = "".join(current_lines).strip()
            if chunk_text:
                chunks.append(
                    Chunk(
                        text=chunk_text,
                        start_line=start_line,
                        end_line=line_idx,
                        source_file=path,
                        metadata={
                            "filename": os.path.basename(path),
                            "path": path,
                            "start_line": start_line,
                            "end_line": line_idx,
                        },
                    )
                )
            overlap_lines: list[str] = []
            overlap_words = 0
            for prev_line in reversed(current_lines):
                p_words = len(prev_line.split())
                if overlap_words + p_words <= overlap:
                    overlap_lines.insert(0, prev_line)
                    overlap_words += p_words
                else:
                    break
            current_lines = overlap_lines
            current_word_count = overlap_words
            start_line = max(1, line_idx - len(overlap_lines) + 1)

    if current_lines:
        chunk_text = "".join(current_lines).strip()
        if chunk_text:
            chunks.append(
                Chunk(
                    text=chunk_text,
                    start_line=start_line,
                    end_line=len(lines),
                    source_file=path,
                    metadata={
                        "filename": os.path.basename(path),
                        "path": path,
                        "start_line": start_line,
                        "end_line": len(lines),
                    },
                )
            )

    return chunks


def _use_pgvector() -> bool:
    """Decide whether pgvector should be used for this process."""
    try:
        from .config import settings
        backend = (getattr(settings, "RAG_BACKEND", "auto") or "auto").lower()
        db_url = (getattr(settings, "DATABASE_URL", "") or "").lower()
    except Exception:
        backend = (os.environ.get("RAG_BACKEND") or "auto").lower()
        db_url = (os.environ.get("DATABASE_URL") or "").lower()

    if backend == "chroma":
        return False
    if backend == "pgvector":
        return True
    return "postgres" in db_url or "postgresql" in db_url


def _hash_embed(text: str, dim: int = _PGVECTOR_DIM) -> list[float]:
    """Deterministic bag-of-tokens embedding (no external model dependency)."""
    vec = [0.0] * dim
    tokens = (text or "").lower().split()
    if not tokens:
        return vec
    for tok in tokens:
        h = int(hashlib.sha256(tok.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 8) & 1 else -1.0
        vec[idx] += sign
    norm = sum(v * v for v in vec) ** 0.5
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


_pg_ready = False


async def _ensure_pgvector_schema() -> bool:
    """Create rag_chunks table + extension when using Postgres."""
    global _pg_ready
    if _pg_ready:
        return True
    try:
        from sqlalchemy import text

        from .infrastructure.database.connection import async_session_factory

        async with async_session_factory() as db:
            await db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await db.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS rag_chunks (
                        id TEXT PRIMARY KEY,
                        collection_name TEXT NOT NULL,
                        workspace_root TEXT NOT NULL DEFAULT '',
                        content TEXT NOT NULL,
                        metadata JSONB NOT NULL DEFAULT '{{}}',
                        embedding vector({_PGVECTOR_DIM})
                    )
                    """
                )
            )
            await db.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_rag_chunks_collection
                    ON rag_chunks (collection_name, workspace_root)
                    """
                )
            )
            await db.commit()
        _pg_ready = True
        return True
    except Exception as exc:
        logger.warning("pgvector schema setup failed: %s", exc)
        return False


async def _pg_embed_and_index(
    chunks: list[Chunk],
    collection_name: str,
    workspace_root: str = "",
) -> Any:
    import json as _json

    from sqlalchemy import text

    from .infrastructure.database.connection import async_session_factory

    if not await _ensure_pgvector_schema():
        return None

    safe_name = "col_" + hashlib.sha256(collection_name.encode("utf-8")).hexdigest()[:20]
    try:
        async with async_session_factory() as db:
            for i, c in enumerate(chunks):
                cid = f"chk_{i}_{hashlib.sha256(c.text.encode('utf-8')).hexdigest()[:8]}"
                emb = _hash_embed(c.text)
                emb_literal = "[" + ",".join(f"{v:.8f}" for v in emb) + "]"
                await db.execute(
                    text(
                        """
                        INSERT INTO rag_chunks (id, collection_name, workspace_root, content, metadata, embedding)
                        VALUES (:id, :col, :ws, :content, CAST(:meta AS jsonb), CAST(:emb AS vector))
                        ON CONFLICT (id) DO UPDATE SET
                            content = EXCLUDED.content,
                            metadata = EXCLUDED.metadata,
                            embedding = EXCLUDED.embedding
                        """
                    ),
                    {
                        "id": cid,
                        "col": safe_name,
                        "ws": workspace_root or "",
                        "content": c.text,
                        "meta": _json.dumps(c.metadata or {}),
                        "emb": emb_literal,
                    },
                )
            await db.commit()
        logger.info("RAG(pgvector): Indexed %d chunks into '%s'", len(chunks), safe_name)
        return {"backend": "pgvector", "collection": safe_name, "count": len(chunks)}
    except Exception as exc:
        logger.error("RAG(pgvector) indexing failed: %s", exc)
        return None


async def _pg_query(
    collection_name: str,
    question: str,
    top_k: int = 5,
    workspace_root: str = "",
) -> list[Chunk]:
    import json as _json

    from sqlalchemy import text

    from .infrastructure.database.connection import async_session_factory

    if not await _ensure_pgvector_schema():
        return []

    safe_name = "col_" + hashlib.sha256(collection_name.encode("utf-8")).hexdigest()[:20]
    emb = _hash_embed(question)
    emb_literal = "[" + ",".join(f"{v:.8f}" for v in emb) + "]"
    try:
        async with async_session_factory() as db:
            result = await db.execute(
                text(
                    """
                    SELECT content, metadata
                    FROM rag_chunks
                    WHERE collection_name = :col
                      AND (:ws = '' OR workspace_root = :ws)
                    ORDER BY embedding <=> CAST(:emb AS vector)
                    LIMIT :k
                    """
                ),
                {
                    "col": safe_name,
                    "ws": workspace_root or "",
                    "emb": emb_literal,
                    "k": top_k,
                },
            )
            rows = result.fetchall()
        out: list[Chunk] = []
        for content, meta in rows:
            if isinstance(meta, str):
                try:
                    meta = _json.loads(meta)
                except Exception:
                    meta = {}
            meta = meta or {}
            out.append(
                Chunk(
                    text=content,
                    start_line=int(meta.get("start_line", 1) or 1),
                    end_line=int(meta.get("end_line", 1) or 1),
                    source_file=meta.get("path", meta.get("filename", "attached_file")),
                    metadata=meta,
                )
            )
        logger.info("RAG(pgvector): Retrieved %d chunks for '%s'", len(out), question[:40])
        return out
    except Exception as exc:
        logger.error("RAG(pgvector) query failed: %s", exc)
        return []


_chroma_clients: dict = {}


def _get_chroma_client(workspace_root: str | None = None):
    """Retrieve persistent ChromaDB client for the workspace with connection pooling."""
    if workspace_root and os.path.isdir(workspace_root):
        h = hashlib.sha256(os.path.abspath(workspace_root).encode("utf-8")).hexdigest()[:16]
        chroma_dir = os.path.join(os.path.expanduser("~"), ".devpilot", "chroma", h)

        old_dir = os.path.join(workspace_root, "artifacts", "chroma")
        if os.path.exists(old_dir) and not os.path.exists(chroma_dir):
            try:
                os.makedirs(os.path.dirname(chroma_dir), exist_ok=True)
                shutil.move(old_dir, chroma_dir)
                logger.info(f"Migrated ChromaDB index from {old_dir} to {chroma_dir}")
            except Exception as me:
                logger.warning(f"Failed to migrate ChromaDB index: {me}")
    else:
        chroma_dir = os.path.join(os.path.expanduser("~"), ".devpilot", "chroma", "default")

    chroma_dir = os.path.abspath(chroma_dir)
    if chroma_dir in _chroma_clients:
        return _chroma_clients[chroma_dir]

    os.makedirs(chroma_dir, exist_ok=True)

    try:
        import chromadb
        client = chromadb.PersistentClient(path=chroma_dir)
        _chroma_clients[chroma_dir] = client
        return client
    except Exception as exc:
        logger.warning("ChromaDB initialization failed or not installed: %s. Using ephemeral store.", exc)
        return None


async def embed_and_index(
    chunks: list[Chunk],
    collection_name: str,
    workspace_root: str = "",
) -> Any:
    """Index chunks into pgvector (preferred) or ChromaDB."""
    if not chunks:
        return None

    if _use_pgvector():
        result = await _pg_embed_and_index(chunks, collection_name, workspace_root)
        if result is not None:
            return result
        logger.warning("pgvector indexing unavailable; falling back to ChromaDB")

    safe_name = "col_" + hashlib.sha256(collection_name.encode("utf-8")).hexdigest()[:20]
    client = _get_chroma_client(workspace_root)
    if client is None:
        logger.info("RAG: ChromaDB unavailable, returning %d unindexed chunks.", len(chunks))
        return None

    try:
        collection = client.get_or_create_collection(name=safe_name)
        documents = [c.text for c in chunks]
        metadatas = [c.metadata for c in chunks]
        ids = [f"chk_{i}_{hashlib.sha256(c.text.encode('utf-8')).hexdigest()[:8]}" for i, c in enumerate(chunks)]
        collection.add(documents=documents, metadatas=metadatas, ids=ids)
        logger.info("RAG: Indexed %d chunks into collection '%s'", len(chunks), safe_name)
        return collection
    except Exception as exc:
        logger.error("RAG indexing failed: %s", exc)
        return None


async def query(
    collection_name: str,
    question: str,
    top_k: int = 5,
    workspace_root: str = "",
) -> list[Chunk]:
    """Query the active RAG backend for top_k relevant chunks."""
    if not question or not question.strip():
        question = "relevant code context"

    if _use_pgvector():
        results = await _pg_query(collection_name, question, top_k, workspace_root)
        if results:
            return results

    safe_name = "col_" + hashlib.sha256(collection_name.encode("utf-8")).hexdigest()[:20]
    client = _get_chroma_client(workspace_root)
    if client is None:
        return []

    try:
        try:
            collection = client.get_collection(name=safe_name)
        except Exception:
            return []

        count = collection.count()
        if count == 0:
            return []

        actual_k = min(top_k, count)
        results = collection.query(query_texts=[question], n_results=actual_k)

        retrieved_chunks: list[Chunk] = []
        if results and "documents" in results and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
            for doc, meta in zip(docs, metas):
                retrieved_chunks.append(
                    Chunk(
                        text=doc,
                        start_line=meta.get("start_line", 1),
                        end_line=meta.get("end_line", 1),
                        source_file=meta.get("path", meta.get("filename", "attached_file")),
                        metadata=meta,
                    )
                )
        logger.info("RAG: Retrieved %d chunks for query '%s'", len(retrieved_chunks), question[:40])
        return retrieved_chunks
    except Exception as exc:
        logger.error("RAG query failed: %s", exc)
        return []
