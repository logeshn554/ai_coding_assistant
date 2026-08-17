# Security Policy & Architecture — Loopix IDE

## Reporting a Vulnerability

If you discover a security vulnerability within Loopix, please do NOT create a public issue. Send security reports directly via private security advisory on GitHub or email the maintainers. We take security seriously and will investigate and address reported issues promptly.

---

## Security Model

Loopix operates under the fundamental rule: **The LLM model is never trusted to make security decisions. The runtime engine enforces all security boundaries.**

## Defensive Layers

1. **Workspace Boundary Guard** (`backend/app/agent/security/workspace_guard.py`): Blocks path traversal (`../`), null byte injections (`\x00`), tilde home escapes (`~`), and symlink escapes using canonical realpath verification.
2. **Secret Redactor & Protection** (`backend/app/agent/security/secret_redactor.py`): Redacts API keys, JWTs, private keys, and passwords (`[REDACTED]`). Denies access to protected secret files (`.env`, `.pem`, `id_rsa`).
3. **Environment Isolation** (`backend/app/agent/security/environment_isolation.py`): Filters host process environment variables, stripping host tokens and API keys from child subprocesses.
4. **Terminal Sandbox & Process Cleanup** (`backend/app/agent/security/terminal_sandbox.py`): Analyzes shell syntax (subshells, pipes, operators) and terminates process trees on cancellation.
5. **Network Policy Engine** (`backend/app/agent/security/network_policy.py`): Validates outbound domain requests against configured allowlists.
