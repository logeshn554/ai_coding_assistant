"""Minimal ChromaDB RAG pipeline for non-image file attachments.

Provides:
- `chunk_file`: line & token-window file chunker preserving line numbers.
- `embed_and_index`: indexes file chunks into a workspace ChromaDB collection.
- `query`: retrieves top_k relevant chunks for a question.
"""

from __future__ import annotations

import logging
import os
import hashlib
import shutil
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("devpilot.rag")

# Eviction policy configuration (overridable via environment)
_MAX_CHROMA_DIRS = int(os.environ.get("DEVPILOT_MAX_CHROMA_DIRS", "8"))
_MAX_CHROMA_AGE_DAYS = int(os.environ.get("DEVPILOT_CHROMA_MAX_AGE_DAYS", "30"))


def _evict_old_chroma_indexes() -> None:
    """Remove ChromaDB workspace indexes that exceed the age or count limits.

    Called once at application startup to keep ~/.devpilot/chroma/ bounded.
    - First evicts all indexes older than _MAX_CHROMA_AGE_DAYS.
    - Then evicts oldest-first beyond _MAX_CHROMA_DIRS count.
    """
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

    # Phase 1: remove by age
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

    # Phase 2: remove oldest beyond count limit (newest first)
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
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def chunk_file(path: str, max_tokens: int = 500, overlap: int = 50) -> List[Chunk]:
    """Chunk a file into token-bounded line windows with overlap.

    Args:
        path: Path to the target file.
        max_tokens: Approximate max tokens (words) per chunk.
        overlap: Approximate overlap tokens (words) between chunks.

    Returns:
        List of Chunk objects.
    """
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

    chunks: List[Chunk] = []
    current_lines: List[str] = []
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
            # Retain overlap lines for context continuity
            overlap_lines: List[str] = []
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

    # Remaining lines chunk
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


_chroma_clients: dict = {}

def _get_chroma_client(workspace_root: Optional[str] = None):
    """Retrieve persistent ChromaDB client for the workspace with connection pooling."""
    if workspace_root and os.path.isdir(workspace_root):
        import hashlib
        h = hashlib.sha256(os.path.abspath(workspace_root).encode("utf-8")).hexdigest()[:16]
        chroma_dir = os.path.join(os.path.expanduser("~"), ".devpilot", "chroma", h)
        
        # One-time migration
        old_dir = os.path.join(workspace_root, "artifacts", "chroma")
        if os.path.exists(old_dir) and not os.path.exists(chroma_dir):
            try:
                import shutil
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
    chunks: List[Chunk],
    collection_name: str,
    workspace_root: str = "",
) -> Any:
    """Index chunks into a ChromaDB collection.

    Args:
        chunks: List of Chunk objects to index.
        collection_name: Target collection name.
        workspace_root: Workspace root path.
    """
    if not chunks:
        return None

    # Sanitize collection name for ChromaDB rules (3-63 chars, alphanumeric)
    safe_name = "col_" + hashlib.md5(collection_name.encode("utf-8")).hexdigest()[:20]

    client = _get_chroma_client(workspace_root)
    if client is None:
        logger.info("RAG: ChromaDB unavailable, returning %d unindexed chunks.", len(chunks))
        return None

    try:
        # Get or create collection
        collection = client.get_or_create_collection(name=safe_name)

        documents = [c.text for c in chunks]
        metadatas = [c.metadata for c in chunks]
        ids = [f"chk_{i}_{hashlib.md5(c.text.encode('utf-8')).hexdigest()[:8]}" for i, c in enumerate(chunks)]

        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )
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
) -> List[Chunk]:
    """Query a ChromaDB collection for top_k relevant chunks matching question.

    Args:
        collection_name: Name of collection to query.
        question: Question / search string.
        top_k: Number of relevant chunks to retrieve.
        workspace_root: Workspace root path.

    Returns:
        List of relevant Chunk objects.
    """
    if not question or not question.strip():
        question = "relevant code context"

    safe_name = "col_" + hashlib.md5(collection_name.encode("utf-8")).hexdigest()[:20]

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
        results = collection.query(
            query_texts=[question],
            n_results=actual_k,
        )

        retrieved_chunks: List[Chunk] = []
        if results and "documents" in results and results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0] if "metadatas" in results and results["metadatas"] else [{}] * len(docs)

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
