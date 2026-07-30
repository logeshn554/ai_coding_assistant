import os
import tempfile
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.context_config import (
    READ_FILE_MAX_CHARS,
    HISTORY_MAX_CHARS,
    CODEBASE_SCAN_MAX_CHARS
)
from app.context_helpers import (
    truncate_text,
    estimate_text_size,
    compact_json,
    prepare_tool_result_for_history,
    build_relevant_file_context,
    deduplicate_blocks,
    assemble_prompt_context,
    build_memory_summary
)
from app.files import (
    read_workspace_file,
    read_workspace_file_range,
    search_workspace_file,
    get_codebase_contents,
    file_cache
)

def test_truncate_text():
    # Fit within limit
    assert truncate_text("hello", 10) == "hello"
    
    # Simple truncation
    long_str = "line1\nline2\nline3\nline4\n"
    res = truncate_text(long_str, 12, label="test")
    assert "[test truncated" in res
    
    # Raise ValueError on invalid limit
    with pytest.raises(ValueError):
        truncate_text("test", 0)

def test_estimate_text_size():
    assert estimate_text_size("hello") == 5
    assert estimate_text_size(None) == 0
    assert estimate_text_size({"a": 1}) == len('{"a":1}')

def test_compact_json():
    val = {"a": "x" * 100}
    res = compact_json(val, 50, "json_test")
    assert "truncated" in res

def test_prepare_tool_result_for_history():
    # Base64 omission
    b64_data = "data:image/png;base64,iVBORw0KGgoAAAANS"
    res = prepare_tool_result_for_history(b64_data, tool_name="test_tool")
    assert "omitted" in res
    
    # Large tool output truncation
    large_output = "data " * 20000
    res2 = prepare_tool_result_for_history(large_output, tool_name="test_tool", max_chars=100)
    assert "truncated" in res2

def test_build_relevant_file_context():
    content = "import os\n\ndef my_cool_function():\n    return 42\n" + "\n" * 20 + "class MyCoolClass:\n    pass\n"
    res = build_relevant_file_context(
        path="foo.py",
        content=content,
        task_description="Implement my_cool_function",
        max_chars=200
    )
    assert "my_cool_function" in res
    assert "MyCoolClass" not in res  # scoped out

def test_deduplicate_blocks():
    blocks = [
        {"role": "user", "content": "my request block that is relatively long " * 5, "source": "s1"},
        {"role": "assistant", "content": "my request block that is relatively long " * 5, "source": "s2"}
    ]
    deduped = deduplicate_blocks(blocks)
    assert len(deduped) == 2
    assert "duplicate content omitted" in deduped[1]["content"]

def test_assemble_prompt_context():
    history = [{"role": "user", "content": "user request"}]
    file_contexts = [{"path": "a.py", "content": "def a(): pass"}]
    res = assemble_prompt_context(
        system_text="system instruction",
        task_text="task description",
        history=history,
        file_contexts=file_contexts,
        memory_summary="{}",
        tool_context=[],
        max_chars=1000
    )
    assert "prompt" in res
    assert "system instruction" in res["prompt"]
    assert "task description" in res["prompt"]

def test_build_memory_summary():
    mem = {
        "file_contents": {"a.py": "huge contents"},
        "task_id": 42,
        "completed": True
    }
    summary = build_memory_summary(mem)
    assert "huge contents" not in summary
    assert "task_id" in summary

def test_bounded_file_reading():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a large file
        filepath = os.path.join(tmpdir, "large.txt")
        large_content = "line " * 20000
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(large_content)
            
        # Read with limit
        content = read_workspace_file(tmpdir, "large.txt", max_chars=100)
        assert "[file 'large.txt' truncated" in content
        assert len(content) < 300
        
        # Test range reader
        range_content = read_workspace_file_range(tmpdir, "large.txt", 1, 10, max_chars=100)
        assert "truncated" in range_content

def test_early_stop_codebase_contents():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create multiple files
        for i in range(5):
            filepath = os.path.join(tmpdir, f"file_{i}.txt")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("content " * 1000)
                
        # Retrieve contents with low limit
        res = get_codebase_contents(tmpdir, max_chars=2000)
        assert "truncated" in res
        # Check that we stopped scanning early
