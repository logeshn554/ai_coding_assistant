import os
import shutil
from pathlib import Path
from coding_agent import CodingAgent

def test_delete():
    test_dir = Path("test_delete_workspace")
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir()
    
    # Initialize the agent in the temporary test workspace
    agent = CodingAgent(api_key="mock", workspace_dir=str(test_dir))
    
    print("=" * 60)
    print("🧪 TESTING AGENT DELETE TOOL")
    print("=" * 60)
    
    # 1. Test deleting a single file
    file_to_delete = test_dir / "temp_file.txt"
    file_to_delete.write_text("temporary content", encoding="utf-8")
    assert file_to_delete.exists()
    
    print("Testing file deletion:")
    res = agent.delete_file("temp_file.txt")
    print(f"Result: {res}")
    assert not file_to_delete.exists()
    print("✓ Single file deletion verified\n")
    
    # 2. Test deleting a directory recursively
    subdir = test_dir / "temp_dir"
    subdir.mkdir()
    (subdir / "nested.txt").write_text("nested content", encoding="utf-8")
    assert subdir.exists()
    assert (subdir / "nested.txt").exists()
    
    print("Testing directory deletion recursively:")
    res = agent.delete_file("temp_dir")
    print(f"Result: {res}")
    assert not subdir.exists()
    print("✓ Directory deletion recursively verified\n")
    
    # 3. Test path traversal safety guardrail
    print("Testing path traversal security:")
    try:
        agent.delete_file("../outside_file.txt")
        print("❌ Path traversal security failed (did not raise error)")
        assert False
    except PermissionError as e:
        print(f"✓ Path traversal block caught as expected: {e}\n")
    
    # Clean up workspace
    shutil.rmtree(test_dir)
    print("=" * 60)
    print("✅ ALL DELETE TOOL TESTS PASSED")
    print("=" * 60)

if __name__ == "__main__":
    test_delete()
