"""Self-Healing Workspace Engine — Automatically diagnoses runtime failures and proposes candidate repair patches."""
import logging
from typing import Any

logger = logging.getLogger("devpilot.self_healing")

class SelfHealingEngine:
    def diagnose_and_heal(self, error_message: str, workspace_root: str = "") -> dict[str, Any]:
        """Diagnose a runtime failure or test assertion error and return a recommended fix patch."""
        if not error_message:
            return {"status": "no_error", "diagnosis": "No error provided.", "patch_suggested": False}

        lower_err = error_message.lower()
        patches: list[dict[str, str]] = []

        if "module_not_found" in lower_err or "no module named" in lower_err or "cannot find module" in lower_err:
            patches.append({
                "action": "install_missing_dependency",
                "description": "Missing module detected. Run package manager installation.",
                "command": "npm install" if "cannot find module" in lower_err else "pip install -r requirements.txt"
            })
        elif "permission" in lower_err or "access denied" in lower_err:
            patches.append({
                "action": "fix_permissions",
                "description": "File or folder access permission issue detected.",
                "command": "chmod -R 755 ."
            })
        elif "syntaxerror" in lower_err or "unexpected token" in lower_err:
            patches.append({
                "action": "syntax_fix",
                "description": "Syntax error encountered. Requesting AI agent auto-formatting repair.",
                "command": "npx prettier --write ."
            })
        else:
            patches.append({
                "action": "ai_agent_patch",
                "description": "Complex runtime error. Triggering autonomous agent debug & repair turn.",
                "command": "/api/agent/heal"
            })

        return {
            "status": "diagnosed",
            "error_summary": error_message[:200],
            "patch_suggested": True,
            "patches": patches
        }

self_healing_engine = SelfHealingEngine()
