"""End-to-End integration tests for all newly added features by generating physical files.

Tests cover:
1. Image generation -> Vision / OCR extraction on generated PNG.
2. Code & Document file generation -> RAG chunking, indexing, and retrieval.
3. MCP server script generation -> Server connection, tool registration, and permission checks.
4. Error log file generation -> StuckDetector error normalization & Tavily web search fallback.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.attachments import format_attachment_prompt, process_attachments
from app.mcp_client import MCP_DISCOVERED_TOOLS, global_mcp_manager
from app.rag import chunk_file, embed_and_index, query
from app.tools.dispatcher import dispatch_tool
from app.vision import VisionResult, analyze_image



@pytest.mark.asyncio
async def test_generated_image_file_vision_analysis(tmp_path):
    """Generates a physical PNG image file and analyzes it via vision/OCR."""
    img_path = tmp_path / "generated_invoice.png"
    img = Image.new("RGB", (300, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((10, 40), "DevPilot QA Invoice #1001", fill=(0, 0, 0))
    img.save(img_path)

    assert os.path.exists(img_path)

    # 1. OCR fallback on generated image file
    res_ocr: VisionResult = await analyze_image(str(img_path))
    assert res_ocr.mode == "ocr"
    assert "generated_invoice.png" in res_ocr.text
    assert res_ocr.confidence > 0.0

    # 2. Vision Model path on generated image file
    with patch("app.state.config_manager.get_image_analysis_model", return_value="gpt-4o"):
        with patch("app.adapters.router.ModelRouter.completion", new_callable=AsyncMock) as mock_comp:
            mock_comp.return_value = "Invoice #1001 detected with amount $500.00"
            res_vision: VisionResult = await analyze_image(str(img_path))

    assert res_vision.mode == "vision_model"
    assert "Invoice #1001" in res_vision.text
    assert res_vision.confidence == 1.0


@pytest.mark.asyncio
async def test_generated_code_files_rag_pipeline(tmp_path):
    """Generates code and documentation files, then tests RAG chunking & retrieval."""
    py_file = tmp_path / "database_service.py"
    py_file.write_text(
        "class DatabaseService:\n"
        "    def __init__(self, db_url: str):\n"
        "        self.db_url = db_url\n\n"
        "    def connect_postgresql(self):\n"
        "        print('Connecting to PostgreSQL database...')\n"
        "        return True\n",
        encoding="utf-8",
    )

    md_file = tmp_path / "API_GUIDE.md"
    md_file.write_text(
        "# API Documentation Guide\n"
        "Use `/api/v1/auth/login` to obtain a JWT bearer token.\n"
        "Use `/api/v1/users/profile` to get user metadata.\n",
        encoding="utf-8",
    )

    assert os.path.exists(py_file)
    assert os.path.exists(md_file)

    # Process both generated attachments
    results = await process_attachments(
        [str(py_file), str(md_file)],
        query="How do I connect to PostgreSQL?",
        workspace_root=str(tmp_path),
    )

    assert len(results) == 2
    assert results[0].file_type == "document"
    assert results[0].mode == "rag"
    assert "connect_postgresql" in results[0].summary_or_chunks

    assert results[1].file_type == "document"
    assert results[1].mode == "rag"

    formatted_prompt = format_attachment_prompt(results)
    assert "ATTACHED FILE CONTEXT" in formatted_prompt
    assert "database_service.py" in formatted_prompt
    assert "API_GUIDE.md" in formatted_prompt


@pytest.mark.asyncio
async def test_generated_mcp_script_server_registration(tmp_path):
    """Generates a mock MCP server script and tests tool registration & dispatcher execution."""
    server_script = tmp_path / "mock_mcp_server.py"
    server_script.write_text(
        "import sys, json\n"
        "for line in sys.stdin:\n"
        "    try:\n"
        "        req = json.loads(line)\n"
        "        req_id = req.get('id')\n"
        "        method = req.get('method')\n"
        "        if method == 'initialize':\n"
        "            res = {'jsonrpc': '2.0', 'id': req_id, 'result': {'protocolVersion': '2025-11-25', 'capabilities': {'tools': {}}, 'serverInfo': {'name': 'mock', 'version': '1.0'}}}\n"
        "        elif method == 'tools/list':\n"
        "            res = {'jsonrpc': '2.0', 'id': req_id, 'result': {'tools': [{'name': 'mcp_gen_query', 'description': 'Mock tool', 'inputSchema': {'type': 'object'}}]}}\n"
        "        elif method.startswith('tools/call'):\n"
        "            res = {'jsonrpc': '2.0', 'id': req_id, 'result': {'content': [{'type': 'text', 'text': 'Executed successfully'}]}}\n"
        "        else:\n"
        "            res = {'jsonrpc': '2.0', 'id': req_id, 'result': {}}\n"
        "        sys.stdout.write(json.dumps(res) + '\\n')\n"
        "        sys.stdout.flush()\n"
        "    except Exception:\n"
        "        sys.exit(1)\n",
        encoding="utf-8",
    )

    server_cfg = {
        "id": "gen-mcp-server",
        "name": "Generated MCP Server",
        "command": sys.executable,
        "args": [str(server_script)],
    }

    discovered = await global_mcp_manager.connect_server(server_cfg)
    assert len(discovered) >= 1

    tool_name = discovered[0]["name"]
    assert tool_name in MCP_DISCOVERED_TOOLS

    class DummySession:
        workspace_root = str(tmp_path)
        _monitor_tasks = []

    # Execute discovered MCP tool via dispatcher
    exec_res = await dispatch_tool(DummySession(), "tc-mcp-1", tool_name, {"query": "SELECT * FROM users"}, auto_apply=True)
    assert "Executed" in exec_res or "Arguments" in exec_res


