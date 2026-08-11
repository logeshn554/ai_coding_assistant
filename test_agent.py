"""
Test script for the coding agent
Tests that it creates files correctly and doesn't create unwanted files
"""
import os
import sys
import shutil
from pathlib import Path
from coding_agent import CodingAgent


def test_agent():
    """Test the coding agent with a real project creation"""
    
    # Create a test workspace
    test_workspace = Path("test_agent_output")
    if test_workspace.exists():
        shutil.rmtree(test_workspace)
    test_workspace.mkdir()
    
    print("=" * 60)
    print("🧪 TESTING AI CODING AGENT")
    print("=" * 60)
    
    # Check API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("\n❌ Error: ANTHROPIC_API_KEY environment variable not set")
        print("\nSet it with:")
        print("   $env:ANTHROPIC_API_KEY='your-key-here'   # Windows PowerShell")
        print("   export ANTHROPIC_API_KEY='your-key-here'  # Linux/Mac")
        sys.exit(1)
    
    # Create agent
    agent = CodingAgent(api_key=api_key, workspace_dir=str(test_workspace))
    
    print("\n✓ Agent initialized")
    print(f"✓ Workspace: {test_workspace.absolute()}\n")
    
    # Test 1: Create a simple Python project
    print("\n" + "=" * 60)
    print("TEST 1: Create a simple Flask web app")
    print("=" * 60)
    
    request = """Create a simple Flask web app with:
- app.py with a home route that returns 'Hello World'
- requirements.txt with Flask dependency
- Do NOT create any research.md or planning files"""
    
    agent.run(request)
    
    # Check what files were created
    print("\n📁 Files created:")
    created_files = []
    for file in test_workspace.rglob("*"):
        if file.is_file():
            rel_path = file.relative_to(test_workspace)
            created_files.append(str(rel_path))
            print(f"   ✓ {rel_path}")
    
    # Verify expectations
    print("\n🔍 Verification:")
    
    # Should have app.py
    if any("app.py" in f for f in created_files):
        print("   ✓ app.py created")
    else:
        print("   ❌ app.py NOT created")
    
    # Should have requirements.txt
    if any("requirements" in f.lower() for f in created_files):
        print("   ✓ requirements.txt created")
    else:
        print("   ❌ requirements.txt NOT created")
    
    # Should NOT have research.md or similar
    unwanted = [f for f in created_files if any(x in f.lower() for x in ["research", "plan", "notes", "todo"])]
    if unwanted:
        print(f"   ⚠️  Unwanted files created: {unwanted}")
    else:
        print("   ✓ No unwanted planning/research files")
    
    # Show content of app.py
    app_files = [f for f in test_workspace.rglob("*.py") if "app" in f.name.lower()]
    if app_files:
        print(f"\n📄 Content of {app_files[0].name}:")
        print("-" * 60)
        content = app_files[0].read_text()
        print(content[:500])  # First 500 chars
        if len(content) > 500:
            print("...")
        print("-" * 60)
    
    # Test 2: Follow-up request
    print("\n" + "=" * 60)
    print("TEST 2: Add a new route")
    print("=" * 60)
    
    request2 = "Add an /api/status route that returns JSON with status: 'ok'"
    agent.run(request2)
    
    print("\n" + "=" * 60)
    print("✅ TESTING COMPLETE")
    print("=" * 60)
    print(f"\nTest workspace: {test_workspace.absolute()}")
    print("Review the files to verify they meet your requirements.")
    print("\nTo clean up: rmdir /s test_agent_output")


if __name__ == "__main__":
    test_agent()
