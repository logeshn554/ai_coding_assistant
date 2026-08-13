import os
import sys
import json
import shutil
from pathlib import Path

# Mock Client Classes for testing without a live API key
class MockContent:
    def __init__(self, type, text=None, id=None, name=None, input=None):
        self.type = type
        self.text = text
        self.id = id
        self.name = name
        self.input = input

class MockResponse:
    def __init__(self, content):
        self.content = content

class MockMessages:
    def __init__(self):
        self.call_count = 0

    def create(self, model, max_tokens, system, messages, tools):
        self.call_count += 1
        last_message = messages[-1]
        
        # If user sends a text request
        if isinstance(last_message, dict) and last_message.get("role") == "user":
            content = last_message.get("content")
            if isinstance(content, str):
                if "Flask web app" in content:
                    return MockResponse([
                        MockContent(
                            type="tool_use",
                            id="tc_create_app",
                            name="create_file",
                            input={
                                "path": "app.py",
                                "content": "from flask import Flask\napp = Flask(__name__)\n\n@app.route('/')\ndef home():\n    return 'Hello World'\n\nif __name__ == '__main__':\n    app.run()\n"
                            }
                        ),
                        MockContent(
                            type="tool_use",
                            id="tc_create_reqs",
                            name="create_file",
                            input={
                                "path": "requirements.txt",
                                "content": "Flask>=2.0.0\n"
                            }
                        )
                    ])
                elif "api/status" in content:
                    return MockResponse([
                        MockContent(
                            type="tool_use",
                            id="tc_write_app",
                            name="write_file",
                            input={
                                "path": "app.py",
                                "content": "from flask import Flask, jsonify\napp = Flask(__name__)\n\n@app.route('/')\ndef home():\n    return 'Hello World'\n\n@app.route('/api/status')\ndef status():\n    return jsonify(status='ok')\n\nif __name__ == '__main__':\n    app.run()\n"
                            }
                        )
                    ])
        
        # If last message was tool results, return a final text summary response
        if isinstance(last_message, dict) and last_message.get("role") == "user":
            content = last_message.get("content")
            if isinstance(content, list) and any(item.get("type") == "tool_result" for item in content):
                is_status = any("status" in str(item.get("content")) for item in content)
                if is_status:
                    return MockResponse([
                        MockContent(
                            type="text",
                            text="I have added the `/api/status` route to `app.py`. It returns a JSON response containing `status: 'ok'` as requested."
                        )
                    ])
                else:
                    return MockResponse([
                        MockContent(
                            type="text",
                            text="I have created the Flask web app with `app.py` returning 'Hello World' on the home route, and a `requirements.txt` file listing the Flask dependency."
                        )
                    ])
        
        return MockResponse([
            MockContent(
                type="text",
                text="Mock response completed."
            )
        ])

class MockAnthropic:
    def __init__(self, api_key):
        self.api_key = api_key
        self.messages = MockMessages()


class CodingAgent:
    """
    AI Coding Agent that interacts with the workspace via tools.
    Provides creating files, editing files, listing, directory creation,
    and a delete tool to remove files/directories.
    """
    def __init__(self, api_key: str, workspace_dir: str = "."):
        self.api_key = api_key
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.messages = []
        self.model = "claude-3-5-sonnet-20260620"
        
        if api_key == "mock":
            self.client = MockAnthropic(api_key)
        else:
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key)
            
        self.system_prompt = """You are a senior AI software engineering agent.
Your primary task is to write high-quality, production-ready, fully functional code files.
Always implement the full code, avoiding any placeholders like '# TODO'.

CRITICAL INSTRUCTIONS:
1. ONLY create code/doc files that the user explicitly asks for.
2. DO NOT create research.md, planning.md, todo.txt, notes.txt or similar junk/draft files.
3. Use the provided tools to interact with the workspace:
   - Use list_files to inspect the workspace structure.
   - Use read_file to read existing files.
   - Use create_file to build new files.
   - Use write_file to edit or overwrite existing files.
   - Use create_directory to create folders.
   - Use delete_file to delete files or directories recursively.
4. When editing files, rewrite the entire file or ensure it contains clean, complete code.
5. If the user asks you to remove or delete files/directories, use the delete_file tool.
"""

        self.tools = [
            {
                "name": "create_file",
                "description": "Create a new file with the specified content in the workspace.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path of the file to create within the workspace"},
                        "content": {"type": "string", "description": "The complete, working content to write to the file"}
                    },
                    "required": ["path", "content"]
                }
            },
            {
                "name": "write_file",
                "description": "Write or overwrite content to a file in the workspace.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path of the file to write to within the workspace"},
                        "content": {"type": "string", "description": "The content to write to the file"}
                    },
                    "required": ["path", "content"]
                }
            },
            {
                "name": "read_file",
                "description": "Read the content of a file in the workspace.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path of the file to read"}
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "list_files",
                "description": "List all files recursively in the workspace.",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "create_directory",
                "description": "Create a new directory in the workspace.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path of the directory to create"}
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "delete_file",
                "description": "Delete a file or directory recursively from the workspace.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path of the file or directory to delete"}
                    },
                    "required": ["path"]
                }
            }
        ]

    def _resolve_path(self, path: str) -> Path:
        workspace_path = Path(self.workspace_dir).resolve()
        target_path = (workspace_path / path).resolve()
        if target_path != workspace_path and not str(target_path).startswith(str(workspace_path) + os.sep):
            raise PermissionError(f"Path traversal attempt: {path} is outside workspace {self.workspace_dir}")
        return target_path

    def create_file(self, path: str, content: str) -> str:
        target_path = self._resolve_path(path)
        if target_path.exists():
            return f"Error: File already exists at {path}. Use write_file to overwrite it."
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding='utf-8')
        print(f"   ✓ Created file: {path}")
        return f"Successfully created file: {path}"

    def write_file(self, path: str, content: str) -> str:
        target_path = self._resolve_path(path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding='utf-8')
        print(f"   ✓ Wrote file: {path}")
        return f"Successfully wrote content to file: {path}"

    def read_file(self, path: str) -> str:
        target_path = self._resolve_path(path)
        if not target_path.exists():
            return f"Error: File does not exist at {path}"
        if target_path.is_dir():
            return f"Error: {path} is a directory, not a file."
        return target_path.read_text(encoding='utf-8')

    def list_files(self) -> str:
        workspace_path = Path(self.workspace_dir).resolve()
        files = []
        for p in workspace_path.rglob('*'):
            if p.is_file():
                if any(part.startswith('.') for part in p.relative_to(workspace_path).parts):
                    continue
                files.append(str(p.relative_to(workspace_path)))
        if not files:
            return "No files in workspace."
        return "Workspace files:\n" + "\n".join(f"- {f}" for f in files)

    def create_directory(self, path: str) -> str:
        target_path = self._resolve_path(path)
        target_path.mkdir(parents=True, exist_ok=True)
        print(f"   ✓ Created directory: {path}")
        return f"Successfully created directory: {path}"

    def delete_file(self, path: str) -> str:
        target_path = self._resolve_path(path)
        if not target_path.exists():
            return f"Error: Path does not exist: {path}"
        if target_path.is_dir():
            shutil.rmtree(target_path)
            print(f"   ✓ Deleted directory: {path}")
            return f"Successfully deleted directory: {path}"
        else:
            target_path.unlink()
            print(f"   ✓ Deleted file: {path}")
            return f"Successfully deleted file: {path}"

    def run(self, request: str, max_turns: int = 25):
        print(f"🤖 Agent received: {request}\n")
        print("🔧 Executing operations...")
        
        self.messages.append({
            "role": "user",
            "content": request
        })
        
        for turn in range(max_turns):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4000,
                    system=self.system_prompt,
                    messages=self.messages,
                    tools=self.tools
                )
            except Exception as e:
                print(f"❌ API Error: {e}")
                break
            
            assistant_content = []
            tool_calls = []
            
            for block in response.content:
                block_type = getattr(block, 'type', None)
                if block_type == "text":
                    assistant_content.append({
                        "type": "text",
                        "text": block.text
                    })
                elif block_type == "tool_use":
                    tool_calls.append(block)
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input
                    })
            
            self.messages.append({
                "role": "assistant",
                "content": assistant_content
            })
            
            if not tool_calls:
                final_text = "".join(b.text for b in response.content if getattr(b, 'type', None) == "text")
                if final_text.strip():
                    print(f"\n💬 {final_text}")
                break
                
            tool_results = []
            for tc in tool_calls:
                tool_name = tc.name
                tool_args = tc.input
                tool_use_id = tc.id
                
                try:
                    if tool_name == "create_file":
                        result = self.create_file(tool_args["path"], tool_args["content"])
                    elif tool_name == "write_file":
                        result = self.write_file(tool_args["path"], tool_args["content"])
                    elif tool_name == "read_file":
                        result = self.read_file(tool_args["path"])
                    elif tool_name == "list_files":
                        result = self.list_files()
                    elif tool_name == "create_directory":
                        result = self.create_directory(tool_args["path"])
                    elif tool_name == "delete_file":
                        result = self.delete_file(tool_args["path"])
                    else:
                        result = f"Error: Tool {tool_name} not found."
                    
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": result
                    })
                except Exception as e:
                    print(f"   ✗ Operation failed for {tool_name}: {e}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": f"Error executing tool: {e}",
                        "is_error": True
                    })
            
            self.messages.append({
                "role": "user",
                "content": tool_results
            })

    def run_interactive(self):
        print("\n🤖 AI CODING AGENT - Interactive Mode")
        print("Type 'quit' or 'exit' to stop.\n")
        
        while True:
            try:
                user_input = input("👤 You: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("quit", "exit"):
                    print("\n👋 Goodbye!")
                    break
                self.run(user_input)
                print()
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break


if __name__ == "__main__":
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ Error: ANTHROPIC_API_KEY environment variable not set.")
        print("To run in mock mode for testing, set ANTHROPIC_API_KEY=mock")
        sys.exit(1)
        
    workspace_dir = os.getenv("AGENT_WORKSPACE", ".")
    agent = CodingAgent(api_key=api_key, workspace_dir=workspace_dir)
    
    if len(sys.argv) > 1:
        request = " ".join(sys.argv[1:])
        agent.run(request)
    else:
        agent.run_interactive()
