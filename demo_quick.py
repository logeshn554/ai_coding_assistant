import os
import sys
import shutil
from pathlib import Path
from coding_agent import CodingAgent

def run_demo():
    print("=" * 60)
    print("🚀 AI CODING AGENT - QUICK DEMO")
    print("=" * 60)
    
    # Check API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("\n⚠️  Notice: ANTHROPIC_API_KEY environment variable not set.")
        print("To run with a real Claude model, set it with:")
        print("   $env:ANTHROPIC_API_KEY='your-key-here'   # Windows PowerShell")
        print("\nRunning in MOCK mode to show how the file creation works.")
        api_key = "mock"
        
    demo_workspace = Path("demo_output")
    if demo_workspace.exists():
        shutil.rmtree(demo_workspace)
    demo_workspace.mkdir()
    
    # Initialize agent
    agent = CodingAgent(api_key=api_key, workspace_dir=str(demo_workspace))
    
    request = """Create a simple Flask web app with:
- app.py with a home route that returns 'Hello World'
- requirements.txt with Flask dependency
- Do NOT create any research.md or planning files"""
    
    agent.run(request)
    
    print("\n📁 Demo Output Files Created:")
    for file in demo_workspace.rglob("*"):
        if file.is_file():
            print(f"   ✓ {file.relative_to(demo_workspace)}")
            
    print("\nDemo completed successfully. To clean up: rmdir /s demo_output")

if __name__ == "__main__":
    # Ensure stdout/stderr handles Unicode symbols on Windows consoles
    if os.name == 'nt':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    run_demo()
