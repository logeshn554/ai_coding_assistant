# Loopix Security & Permissions Architecture

Loopix enforces a failure-closed security model designed for autonomous agent execution on local and remote developer workstations.

## Permission Capabilities & Policies

Loopix categorizes all agent tool invocations into 14 explicit capabilities:

1. `READ_FILES`
2. `WRITE_FILES`
3. `DELETE_FILES`
4. `RUN_COMMAND`
5. `INSTALL_PACKAGE`
6. `NETWORK`
7. `BROWSER`
8. `DATABASE`
9. `GIT`
10. `GIT_PUSH`
11. `REMOTE_ACCESS`
12. `SECRETS`
13. `SYSTEM`

### Preset Policy Modes

- **Safe**: Read-only codebase exploration. Any file write or shell execution requires explicit prompt approval.
- **Balanced (Default)**: Workspace file modifications, test suite execution, and local dev server commands allowed. Destructive deletion, git push, and secret access require approval.
- **Autonomous**: Unrestricted workspace coding with automated self-repair. Mass file deletion and external production operations remain approval-guarded.
- **Custom**: User-configured per-capability matrix via `/api/permissions/policy`.

## Prompt-Injection Defense

Repository contents, external web results, and tool outputs are treated as untrusted input. The `PromptSecurityEngine` (`backend/app/prompt_security.py`):
1. Scans incoming content for injection patterns (`ignore previous instructions`, `bypass security`).
2. Wraps repository content in strict `<UNTRUSTED_CONTENT>` security boundary tags.
3. System policy mandates LLMs ignore instructions embedded inside untrusted content.

## Transactional Edits & Instant Rollback

All agent file modifications pass through `TransactionalFileSystem` (`backend/app/transactional_fs.py`).
- Pre-edit snapshots record original file contents.
- Atomic writes prevent partial file corruption.
- Users can inspect unified diffs or trigger instant task rollbacks via `/api/files/rollback-task`.
