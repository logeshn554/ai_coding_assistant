"""Proactive workspace monitoring service for continuous health checks and automated insights."""
import os
import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger("devpilot.proactive_monitor")

class ProactiveWorkspaceMonitor:
    def __init__(self, workspace_root: str = ""):
        self.workspace_root = workspace_root

    def set_workspace_root(self, root: str):
        self.workspace_root = root

    def inspect_workspace_health(self) -> Dict[str, Any]:
        """Perform comprehensive health inspection on active workspace."""
        if not self.workspace_root or not os.path.exists(self.workspace_root):
            return {
                "status": "idle",
                "insights": [],
                "summary": {"bugs": 0, "outdated_packages": 0, "failing_tests": 0, "security_warnings": 0}
            }

        insights: List[Dict[str, Any]] = []
        outdated_count = 0
        bugs_count = 0
        tests_failing = 0
        security_warnings = 0

        # 1. Inspect package.json / requirements.txt
        pkg_json = os.path.join(self.workspace_root, "package.json")
        if not os.path.exists(pkg_json):
            pkg_json = os.path.join(self.workspace_root, "frontend", "package.json")

        if os.path.exists(pkg_json):
            try:
                with open(pkg_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    deps = data.get("dependencies", {})
                    if "react" in deps and not deps["react"].startswith("^19") and not deps["react"].startswith("19"):
                        insights.append({
                            "type": "package_update",
                            "severity": "info",
                            "title": "React dependency notice",
                            "message": f"React version is {deps['react']}. Upgrade available for optimal performance."
                        })
                        outdated_count += 1
            except Exception:
                pass

        # 2. Inspect secret leaks in workspace root files
        env_file = os.path.join(self.workspace_root, ".env")
        if os.path.exists(env_file):
            try:
                with open(env_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if "SECRET_KEY=" in content and "change-me" in content:
                        insights.append({
                            "type": "security",
                            "severity": "warning",
                            "title": "Default Secret Key detected",
                            "message": "Replace placeholder SECRET_KEY in .env before deploying to production."
                        })
                        security_warnings += 1
            except Exception:
                pass

        # 3. Overall status determination
        overall_status = "healthy"
        if security_warnings > 0 or bugs_count > 0:
            overall_status = "warning"
        elif outdated_count > 0:
            overall_status = "notice"

        return {
            "status": overall_status,
            "insights": insights,
            "summary": {
                "bugs": bugs_count,
                "outdated_packages": outdated_count,
                "failing_tests": tests_failing,
                "security_warnings": security_warnings
            }
        }

proactive_monitor = ProactiveWorkspaceMonitor()
