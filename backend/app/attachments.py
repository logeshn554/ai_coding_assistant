"""Multi-file attachment processor and prompt formatter for Loopix AI Assistant.

Routes attached files based on type:
- Image files (.png, .jpg, .jpeg, .webp, .gif) -> `vision.analyze_image`
- Non-image files (code, docs, logs, PDF) -> sequential `rag` chunking + embedding + top_k retrieval
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass
from typing import Any

from .rag import Chunk, chunk_file, embed_and_index
from .rag import query as rag_query
from .vision import VisionResult, analyze_image

logger = logging.getLogger("loopix.attachments")

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"}


@dataclass
class AttachmentResult:
    """Structured result of processing an individual file attachment."""

    path: str
    file_type: str  # "image" or "document"
    summary_or_chunks: str
    mode: str  # "vision_model", "ocr", "rag"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_image_file(path: str) -> bool:
    """Return True if path represents a supported image format."""
    ext = os.path.splitext(path)[1].lower()
    return ext in IMAGE_EXTENSIONS


async def process_attachments(
    paths: list[str],
    query: str = "",
    workspace_root: str = "",
) -> list[AttachmentResult]:
    """Process a list of attached files, routing images to vision/OCR and documents to RAG.

    Args:
        paths: List of relative or absolute file paths.
        query: User question / prompt to target document retrieval.
        workspace_root: Active workspace directory.

    Returns:
        List of AttachmentResult objects in the original order.
    """
    results: list[AttachmentResult] = []

    for path in paths or []:
        if not path:
            continue

        abs_path = path
        if workspace_root and not os.path.isabs(path):
            abs_path = os.path.join(workspace_root, path)

        if is_image_file(path):
            # Image routing -> vision / OCR
            try:
                v_res: VisionResult = await analyze_image(abs_path)
                results.append(
                    AttachmentResult(
                        path=path,
                        file_type="image",
                        summary_or_chunks=v_res.text,
                        mode=v_res.mode,
                    )
                )
            except Exception as v_err:
                logger.error("Failed to analyze image attachment '%s': %s", path, v_err)
                results.append(
                    AttachmentResult(
                        path=path,
                        file_type="image",
                        summary_or_chunks=f"[Image Analysis Error: {v_err}]",
                        mode="ocr",
                    )
                )
        else:
            # Document / Code routing -> RAG one file at a time
            try:
                chunks: list[Chunk] = chunk_file(abs_path)
                if not chunks:
                    results.append(
                        AttachmentResult(
                            path=path,
                            file_type="document",
                            summary_or_chunks="[File empty or unreadable]",
                            mode="rag",
                        )
                    )
                    continue

                collection_name = f"attachment_{os.path.basename(path)}"
                await embed_and_index(chunks, collection_name=collection_name, workspace_root=workspace_root)

                top_chunks: list[Chunk] = await rag_query(
                    collection_name=collection_name,
                    question=query,
                    top_k=5,
                    workspace_root=workspace_root,
                )

                # Fall back to first 5 chunks if query returned nothing
                if not top_chunks:
                    top_chunks = chunks[:5]

                chunk_texts = [
                    f"--- Lines {c.start_line}-{c.end_line} ---\n{c.text}" for c in top_chunks
                ]
                formatted_chunks = "\n\n".join(chunk_texts)

                results.append(
                    AttachmentResult(
                        path=path,
                        file_type="document",
                        summary_or_chunks=formatted_chunks,
                        mode="rag",
                    )
                )
            except Exception as rag_err:
                logger.error("RAG attachment processing failed for '%s': %s", path, rag_err)
                results.append(
                    AttachmentResult(
                        path=path,
                        file_type="document",
                        summary_or_chunks=f"[RAG Error: {rag_err}]",
                        mode="rag",
                    )
                )

    return results


def format_attachment_prompt(results: list[AttachmentResult]) -> str:
    """Format attachment results into a prompt-ready markdown block with per-file headers.

    Args:
        results: List of AttachmentResult objects.

    Returns:
        Formatted markdown block string.
    """
    if not results:
        return ""

    parts = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📎 ATTACHED FILE CONTEXT ({len(results)} file{'s' if len(results) != 1 else ''})",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    for res in results:
        fname = os.path.basename(res.path)
        parts.append(f"### 📄 File: `{res.path}` [{res.file_type.upper()} | Mode: {res.mode}]")
        parts.append(res.summary_or_chunks.strip())
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"
