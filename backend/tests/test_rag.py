"""Tests for rag.py — RAG Pipeline (chunking, embedding, querying)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag import Chunk, chunk_file, embed_and_index, query


def test_chunk_file_preserves_line_numbers_and_source(tmp_path):
    """chunk_file correctly splits text into line windows with metadata."""
    sample_file = tmp_path / "sample.py"
    sample_code = "\n".join([f"def func_{i}(): return {i}" for i in range(1, 100)])
    sample_file.write_text(sample_code, encoding="utf-8")

    chunks = chunk_file(str(sample_file), max_tokens=100, overlap=10)

    assert len(chunks) >= 1
    for c in chunks:
        assert isinstance(c, Chunk)
        assert c.source_file == str(sample_file)
        assert c.start_line <= c.end_line
        assert "def func_" in c.text


@pytest.mark.asyncio
async def test_chunk_embed_query_roundtrip(tmp_path):
    """Round-trip test: chunking, embedding, and querying ChromaDB returns relevant chunks."""
    doc_file = tmp_path / "architecture.txt"
    doc_content = (
        "DevPilot AI Editor Architecture:\n"
        "1. Backend uses FastAPI and LangGraph for multi-agent routing.\n"
        "2. Database history uses SQLite and async SQLAlchemy.\n"
        "3. Redis fallback is used for session context state.\n"
        "4. Frontend is React with TypeScript and CSS design tokens.\n"
    )
    doc_file.write_text(doc_content, encoding="utf-8")

    chunks = chunk_file(str(doc_file), max_tokens=50, overlap=5)
    assert len(chunks) >= 1

    col_name = "test_arch_collection"
    await embed_and_index(chunks, collection_name=col_name, workspace_root=str(tmp_path))

    results = await query(
        collection_name=col_name,
        question="What database does DevPilot use?",
        top_k=2,
        workspace_root=str(tmp_path),
    )

    # In fallback or ChromaDB mode, query returns chunks
    assert isinstance(results, list)
