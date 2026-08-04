"""Tests for Phase 1 — Context Collector."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
import asyncio
from pathlib import Path
from app.agent.context_collector import ContextCollector


@pytest.fixture
def workspace(tmp_path):
    return tmp_path


@pytest.fixture
def collector(workspace):
    return ContextCollector(str(workspace))


class TestContextCollector:
    @pytest.mark.asyncio
    async def test_reads_spec_file(self, workspace, collector):
        spec = workspace / "GDD.md"
        spec.write_text("# Battle Royale\n\nA game about survival.")

        ctx = await collector.collect(
            user_query="implement GDD.md",
            referenced_files=["GDD.md"],
            referenced_symbols=[],
            spec_file="GDD.md",
        )

        assert ctx.spec_content
        assert "Battle Royale" in ctx.spec_content

    @pytest.mark.asyncio
    async def test_reads_readme_if_no_spec(self, workspace, collector):
        readme = workspace / "README.md"
        readme.write_text("# My Project\n\nA cool project.")

        ctx = await collector.collect(
            user_query="build a thing",
            referenced_files=[],
            referenced_symbols=[],
            spec_file=None,
        )

        assert ctx.spec_content
        assert "My Project" in ctx.spec_content

    @pytest.mark.asyncio
    async def test_reads_referenced_code_file(self, workspace, collector):
        code = workspace / "auth.py"
        code.write_text("def login(user, password):\n    pass\n")

        ctx = await collector.collect(
            user_query="fix the bug in auth.py",
            referenced_files=["auth.py"],
            referenced_symbols=[],
            spec_file=None,
        )

        assert "auth.py" in ctx.files_read
        assert "def login" in ctx.files_read["auth.py"]

    @pytest.mark.asyncio
    async def test_detects_react_tech_stack(self, workspace, collector):
        pkg = workspace / "package.json"
        pkg.write_text('{"dependencies": {"react": "^18.0.0", "typescript": "^5.0.0"}}')

        ctx = await collector.collect(
            user_query="add a component",
            referenced_files=[],
            referenced_symbols=[],
            spec_file=None,
        )

        assert any("React" in h for h in ctx.config_hints)
        assert any("TypeScript" in h for h in ctx.config_hints)

    @pytest.mark.asyncio
    async def test_detects_python_stack(self, workspace, collector):
        req = workspace / "requirements.txt"
        req.write_text("fastapi==0.100.0\nuvicorn==0.23.0\n")

        ctx = await collector.collect(
            user_query="fix the API endpoint",
            referenced_files=[],
            referenced_symbols=[],
            spec_file=None,
        )

        assert any("Python" in h for h in ctx.config_hints)
        assert any("FastAPI" in h for h in ctx.config_hints)

    @pytest.mark.asyncio
    async def test_workspace_structure_listed(self, workspace, collector):
        (workspace / "src").mkdir()
        (workspace / "src" / "main.py").write_text("pass\n")
        (workspace / "README.md").write_text("# Test\n")

        ctx = await collector.collect(
            user_query="build something",
            referenced_files=[],
            referenced_symbols=[],
            spec_file=None,
        )

        assert ctx.workspace_structure
        assert "src" in ctx.workspace_structure or "README.md" in ctx.workspace_structure

    @pytest.mark.asyncio
    async def test_missing_spec_file_noted(self, workspace, collector):
        ctx = await collector.collect(
            user_query="implement missing_spec.md",
            referenced_files=["missing_spec.md"],
            referenced_symbols=[],
            spec_file="missing_spec.md",
        )

        assert any("not found" in note for note in ctx.collection_notes)

    @pytest.mark.asyncio
    async def test_to_prompt_block_format(self, workspace, collector):
        spec = workspace / "spec.md"
        spec.write_text("# Spec\n\nDo this.")

        ctx = await collector.collect(
            user_query="implement spec.md",
            referenced_files=["spec.md"],
            referenced_symbols=[],
            spec_file="spec.md",
        )

        block = ctx.to_prompt_block()
        assert "AUTO-COLLECTED CONTEXT" in block
        assert "Spec" in block

    @pytest.mark.asyncio
    async def test_empty_workspace_no_crash(self, workspace, collector):
        # Empty workspace should not crash
        ctx = await collector.collect(
            user_query="build a thing",
            referenced_files=[],
            referenced_symbols=[],
            spec_file=None,
        )
        # Should return empty context gracefully
        assert ctx is not None
