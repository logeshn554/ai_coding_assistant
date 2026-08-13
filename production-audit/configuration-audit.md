# Configuration Audit — DevPilot IDE Platform

This document audits configuration settings, precedence evaluation order, keyring fallback mechanics, and secret exposure risks.

---

## 1. Configuration Sources and Precedence

The application config is managed via Pydantic Settings in [config.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/config.py):

```text
Host Environment Variables (highest precedence)
       ↓
.env File Configurations
       ↓
Local User Profiles (stored in ~/.devpilot/config.json)
       ↓
Pydantic Default Field Values (lowest precedence)
```

---

## 2. Keyring Fallback Bottlenecks

- **Headless Docker Override:** In Docker environments, [config.py](file:///e:/os%20kernel%20with%20ani/ai_coding_assistant/backend/app/config.py) overrides the default system keyring backend with `DevPilotFileKeyring` (lines 97–185) which encrypts secrets using Fernet and saves them in `~/.devpilot/.keyring.json` with the key file in `~/.devpilot/.keyring.key`.
- **Issues for Hosted SaaS Scalability:**
  1. **Replication Sync Loss:** If the API server is scaled horizontally across 3 nodes, each container replica will have a local file-based keyring. If User A updates their API key, the update only persists to the specific container replica instance that served their request. Subsequent requests routed to other worker replicas will fail to load the key.
  2. **Vulnerability of Key Storage:** The Fernet encryption key file (`.keyring.key`) is saved directly alongside the keyring file in the user's home directory. If an attacker gains read access to the home directory (e.g. via directory traversal), they can decrypt the keyring file immediately.

---

## 3. Secret Exposure in Logs

- **Vulnerable Paths:**
  - **Tool Arguments:** Raw API keys can easily leak into debug execution logs if tool calls contain authentication parameters in their args.
  - **LLM Prompt Logging:** System prompts and user history are logged to `.devpilot/chat_logs.md` inside the workspace directory. If a user pastes a secret key into the chat, it is written to disk in plain text.
- **Redaction State:**
  - `SecretRedactor` (in `secret_redactor.py`) implements regex-based redaction to filter tokens from logs, but it only runs on final tool outputs and system prompts in specific spots. Centralized logging output streams are not globally hooked.
