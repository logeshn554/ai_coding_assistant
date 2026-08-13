# Execution Path Audit — DevPilot IDE Platform

This document inventories and audits every direct subprocess and system execution call in the codebase, detailing authorization layers, sandboxing coverage, and timeout safety.

---

## 1. Inventory of Subprocess Call Sites

| Call Site File | API Used | Execution Context | Safeguards & Sandboxing |
| :--- | :--- | :--- | :--- |
| **tools/terminal_tool.py** | `asyncio.create_subprocess_exec` | Executes commands requested by the agent. | - Command injection regex checks.<br>- Docker sandbox wrapper (`docker run -v` mounts writeable host workspace).<br>- Host fallback execution if Docker daemon is missing. |
| **processes.py** | `asyncio.create_subprocess_exec` | Spawns background development servers. | - No container sandboxing; executes directly on host.<br>- Confines subprocesses using Windows Job Objects (on Windows) or PGID sessions (on Unix). |
| **workspace_graph.py** | `subprocess.Popen` | Starts a Node.js process to run `js_ast_parser.js`. | - Runs directly on host.<br>- Hardcoded absolute node paths. |
| **brain/versioned_memory.py** | `subprocess.run` | Executes git commit / checkout commands. | - Runs directly on host.<br>- No security checks. |
| **merge/rollback_engine.py** | `subprocess.run` | Executes git reset / checkout commands. | - Runs directly on host.<br>- No security checks. |
| **verification/lint_runner.py** | `subprocess.run` | Executes flake8 / black checks. | - Runs directly on host.<br>- No security checks. |
| **verification/test_runner.py** | `subprocess.run` | Executes pytest command lines. | - Runs directly on host.<br>- No security checks. |
| **agent/security/terminal_sandbox.py** | `asyncio.create_subprocess_shell` | Pre-probes commands for diagnostic status checks. | - Runs on host.<br>- Uses `os.system` string concatenation to taskkill PID. |

---

## 2. Sandbox Boundary Vulnerability Analysis

1. **Docker Mount Escape:**
   - [terminal_tool.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/tools/terminal_tool.py) wraps command execution in Docker using `_wrap_command_in_sandbox` (lines 81–104). It mounts the host workspace path directly:
     `-v {host_root}:/workspace`
   - Since `/workspace` is writeable, any malicious build script running in the container can modify host-level files (such as adding shell scripts or editing `.git/config` hooks) that escape container boundaries when executed on the host.
2. **Silent Fallback Execution:**
   - If the Docker CLI is not installed or the daemon is offline, `_is_docker_available` (lines 55–78) returns False, and the system silently falls back to running the command directly on the host machine:
     ```python
     else:
         from ..shell_adapter import ShellAdapter
         shell_executable = ShellAdapter.get_shell_executable(interactive=False)
         cmd_executable = shell_executable[0]
         cmd_params = shell_executable[1:] + [command]
     ```
   - This fallback lacks sandbox protection.
3. **Regex-Based Shell Validation:**
   - [terminal_sandbox.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/security/terminal_sandbox.py) attempts to detect shell injections via regex matches. Regex checks are bypassable using shell character encodings or obscure command parameters. The security boundary must rely on OS/namespace isolation, not shell syntax analysis.
