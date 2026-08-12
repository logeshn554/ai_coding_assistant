# Security Policy & Security Architecture — DevPilot IDE

## Security Model

DevPilot operates under the fundamental rule: **The LLM model is never trusted to make security decisions. The runtime enforces all security boundaries.**

## Defensive Layers

1. **Workspace Boundary Guard** ([workspace_guard.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/security/workspace_guard.py)): Blocks path traversal (`../`), null byte injections (`\x00`), tilde home escapes (`~`), and symlink escapes using canonical realpath verification.
2. **Secret Redactor & Protection** ([secret_redactor.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/security/secret_redactor.py)): Redacts API keys, JWTs, private keys, and passwords (`[REDACTED]`). Denies access to protected secret files (`.env`, `.pem`, `id_rsa`).
3. **Environment Isolation** ([environment_isolation.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/security/environment_isolation.py)): Filters host process environment variables, stripping host tokens and API keys.
4. **Terminal Sandbox & Process Cleanup** ([terminal_sandbox.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/security/terminal_sandbox.py)): Analyzes shell syntax (subshells, pipes, operators) and terminates entire process trees (`kill_process_tree`) on cancellation.
5. **Network Policy Engine** ([network_policy.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/agent/security/network_policy.py)): Validates outbound domain requests against configured allowlists.
