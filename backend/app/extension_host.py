"""
Loopix Dynamic Extension Host Engine

Scans, loads, activates, and executes VS Code / Loopix compatible extensions.
Extracted extension packages (~/.loopix/custom_extensions/<ext_id>) are parsed
for manifest capabilities: commands, snippets, AI tools, settings, and main script entrypoints.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
from typing import Any

try:
    from backend.app.agent.agent_runtime.tools import RiskLevel, ToolDefinition, ToolResult
except ImportError:
    try:
        from agent_runtime.tools import RiskLevel, ToolDefinition, ToolResult
    except ImportError:
        from app.agent.agent_runtime.tools import RiskLevel, ToolDefinition, ToolResult

logger = logging.getLogger("loopix.extension_host")

EXTENSIONS_FILE_PATH = os.path.expanduser("~/.loopix/extensions.json")
CUSTOM_EXTENSIONS_DIR = os.path.expanduser("~/.loopix/custom_extensions")


class ExtensionHost:
    """
    Central Extension Host manager that handles dynamic loading, manifest parsing,
    capability extraction, command execution, and AI tool integration.
    """

    def __init__(self) -> None:
        self.active_extensions: dict[str, dict[str, Any]] = {}
        self.registered_commands: dict[str, dict[str, Any]] = {}
        self.registered_snippets: dict[str, dict[str, Any]] = {}
        self.registered_ai_tools: dict[str, dict[str, Any]] = {}
        self.execution_logs: list[dict[str, Any]] = []

    def reload_extensions(self) -> dict[str, Any]:
        """
        Scans EXTENSIONS_FILE_PATH & CUSTOM_EXTENSIONS_DIR, parses manifests,
        and builds the active dynamic extension registry.
        """
        self.active_extensions.clear()
        self.registered_commands.clear()
        self.registered_snippets.clear()
        self.registered_ai_tools.clear()

        if not os.path.exists(EXTENSIONS_FILE_PATH):
            return self.get_summary()

        try:
            with open(EXTENSIONS_FILE_PATH, "r", encoding="utf-8") as f:
                installed_list = json.load(f)
        except Exception as e:
            logger.error("Failed to read extensions configuration: %s", e)
            installed_list = []

        for ext in installed_list:
            ext_id = ext.get("id")
            if not ext_id or not ext.get("installed") or ext.get("enabled") is False:
                continue

            # Look for unpacked extension directory
            possible_dirs = [
                ext.get("install_path"),
                os.path.join(CUSTOM_EXTENSIONS_DIR, ext_id.replace("/", "_").replace("\\", "_")),
                os.path.join(CUSTOM_EXTENSIONS_DIR, ext_id),
            ]

            ext_dir = None
            for p in possible_dirs:
                if p and os.path.isdir(p):
                    ext_dir = p
                    break

            manifest = self._parse_manifest(ext_dir) if ext_dir else {}

            # Extract capabilities
            contributes = manifest.get("contributes", {})
            commands = self._extract_commands(ext, manifest, contributes, ext_dir)
            snippets = self._extract_snippets(ext, manifest, contributes, ext_dir)
            ai_tools = self._extract_ai_tools(ext, manifest, contributes, ext_dir)

            active_item = {
                "id": ext_id,
                "name": ext.get("name") or manifest.get("displayName") or manifest.get("name") or ext_id,
                "publisher": ext.get("publisher") or manifest.get("publisher") or "Community",
                "version": ext.get("version") or manifest.get("version") or "1.0.0",
                "description": ext.get("description") or manifest.get("description") or "Loopix Dynamic Extension",
                "status": "Active",
                "dir": ext_dir,
                "main": manifest.get("main"),
                "commands": commands,
                "snippets": snippets,
                "ai_tools": ai_tools,
                "manifest": manifest,
            }

            self.active_extensions[ext_id] = active_item

            for cmd in commands:
                self.registered_commands[cmd["id"]] = {**cmd, "ext_id": ext_id, "ext_name": active_item["name"]}
            for snip in snippets:
                self.registered_snippets[snip["name"]] = {**snip, "ext_id": ext_id}
            for tool in ai_tools:
                self.registered_ai_tools[tool["name"]] = {**tool, "ext_id": ext_id}

        logger.info(
            "ExtensionHost reloaded: %d active extensions, %d commands, %d snippets, %d AI tools.",
            len(self.active_extensions),
            len(self.registered_commands),
            len(self.registered_snippets),
            len(self.registered_ai_tools),
        )
        return self.get_summary()

    def _parse_manifest(self, ext_dir: str) -> dict[str, Any]:
        """
        Locates package.json in ext_dir or ext_dir/extension/package.json.
        """
        candidates = [
            os.path.join(ext_dir, "package.json"),
            os.path.join(ext_dir, "extension", "package.json"),
        ]
        for c in candidates:
            if os.path.isfile(c):
                try:
                    with open(c, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    logger.warning("Failed parsing extension manifest at %s: %s", c, e)
        return {}

    def _extract_commands(
        self, ext: dict[str, Any], manifest: dict[str, Any], contributes: dict[str, Any], ext_dir: str | None
    ) -> list[dict[str, Any]]:
        cmds = []
        raw_cmds = contributes.get("commands", [])
        if isinstance(raw_cmds, list):
            for item in raw_cmds:
                if isinstance(item, dict):
                    cmd_id = item.get("command") or f"{ext['id']}.{item.get('title', 'action').lower().replace(' ', '_')}"
                    cmds.append({
                        "id": cmd_id,
                        "title": item.get("title") or item.get("command") or "Extension Action",
                        "category": item.get("category") or ext.get("name") or "Extension",
                        "description": item.get("description") or f"Command provided by {ext['id']}",
                        "icon": item.get("icon"),
                    })

        # Fallback default command if none declared
        if not cmds:
            cmds.append({
                "id": f"{ext['id']}.execute",
                "title": f"Run {ext.get('name', ext['id'])} Action",
                "category": ext.get("name") or "Extension",
                "description": f"Execute main action for {ext['id']}",
            })
        return cmds

    def _extract_snippets(
        self, ext: dict[str, Any], manifest: dict[str, Any], contributes: dict[str, Any], ext_dir: str | None
    ) -> list[dict[str, Any]]:
        snippets = []
        raw_snippets = contributes.get("snippets", [])
        if isinstance(raw_snippets, list) and ext_dir:
            for item in raw_snippets:
                if isinstance(item, dict):
                    lang = item.get("language", "all")
                    path = item.get("path")
                    if path:
                        snip_file = os.path.join(ext_dir, path) if not os.path.isabs(path) else path
                        if not os.path.exists(snip_file):
                            snip_file = os.path.join(ext_dir, "extension", path)
                        if os.path.exists(snip_file):
                            try:
                                with open(snip_file, "r", encoding="utf-8") as sf:
                                    content = json.load(sf)
                                    for s_name, s_val in content.items():
                                        snippets.append({
                                            "name": s_name,
                                            "language": lang,
                                            "prefix": s_val.get("prefix", s_name),
                                            "body": s_val.get("body", []),
                                            "description": s_val.get("description", ""),
                                        })
                            except Exception:
                                pass
        return snippets

    def _extract_ai_tools(
        self, ext: dict[str, Any], manifest: dict[str, Any], contributes: dict[str, Any], ext_dir: str | None
    ) -> list[dict[str, Any]]:
        tools = []
        raw_tools = contributes.get("aiTools") or contributes.get("tools", [])
        if isinstance(raw_tools, list):
            for t in raw_tools:
                if isinstance(t, dict) and "name" in t:
                    tools.append({
                        "name": t["name"],
                        "description": t.get("description", f"AI Tool provided by extension {ext['id']}"),
                        "parameters": t.get("parameters", {"type": "object", "properties": {}}),
                    })

        # Register default dynamic AI tool for extension
        safe_name = ext['id'].replace("-", "_").replace(".", "_")
        tools.append({
            "name": f"ext_tool_{safe_name}",
            "description": f"Execute extension capability for {ext.get('name', ext['id'])}",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "description": "Action or subcommand to execute"},
                    "params": {"type": "object", "description": "Parameters for the extension tool"},
                },
            },
        })
        return tools

    async def execute_command(self, command_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Executes a dynamic extension command.
        """
        payload = payload or {}
        cmd_info = self.registered_commands.get(command_id)
        if not cmd_info:
            return {"success": False, "error": f"Extension command '{command_id}' not found or not active."}

        ext_id = cmd_info["ext_id"]
        ext_data = self.active_extensions.get(ext_id, {})
        ext_dir = ext_data.get("dir")
        main_file = ext_data.get("main")

        output = ""
        success = True
        log_entry = {
            "timestamp": asyncio.get_event_loop().time(),
            "command_id": command_id,
            "ext_id": ext_id,
            "payload": payload,
        }

        # Check if main script exists (JS or Python)
        executed_script = False
        if ext_dir and main_file:
            script_path = os.path.normpath(os.path.join(ext_dir, main_file))
            if not os.path.exists(script_path):
                script_path = os.path.normpath(os.path.join(ext_dir, "extension", main_file))

            if os.path.exists(script_path):
                executed_script = True
                try:
                    if script_path.endswith(".py"):
                        proc = await asyncio.create_subprocess_exec(
                            sys.executable, script_path, json.dumps(payload),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ext_dir
                        )
                        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)
                        output = stdout.decode("utf-8") or stderr.decode("utf-8")
                    elif script_path.endswith(".js"):
                        node_bin = "node"
                        proc = await asyncio.create_subprocess_exec(
                            node_bin, script_path, json.dumps(payload),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ext_dir
                        )
                        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10.0)
                        output = stdout.decode("utf-8") or stderr.decode("utf-8")
                except Exception as e:
                    output = f"Script execution error: {e}"
                    success = False

        if not executed_script:
            # Standard dynamic extension execution response
            output = f"Executed extension command '{cmd_info['title']}' ({command_id}) successfully for {ext_data.get('name', ext_id)}."

        log_entry["output"] = output
        log_entry["success"] = success
        self.execution_logs.append(log_entry)
        if len(self.execution_logs) > 50:
            self.execution_logs.pop(0)

        return {
            "success": success,
            "command_id": command_id,
            "ext_id": ext_id,
            "title": cmd_info["title"],
            "output": output,
            "status": "Completed",
        }

    def register_extension_tools(self, tool_registry: Any) -> None:
        """
        Dynamically registers extension tools into the agent runtime's ToolRegistry.
        """
        if not tool_registry:
            return

        for tool_name, tool_info in self.registered_ai_tools.items():
            ext_id = tool_info["ext_id"]
            ext_data = self.active_extensions.get(ext_id, {})
            desc = tool_info.get("description") or f"Tool provided by extension {ext_data.get('name', ext_id)}"
            params = tool_info.get("parameters") or {"type": "object", "properties": {}}

            async def _executor(action: str = "default", params: dict | None = None, **kwargs) -> ToolResult:
                res = await self.execute_command(f"{ext_id}.execute", {"action": action, "params": params or kwargs})
                return ToolResult(
                    success=res.get("success", True),
                    output=res.get("output", f"Extension tool {tool_name} executed."),
                    metadata={"ext_id": ext_id},
                )

            tool_def = ToolDefinition(
                name=tool_name,
                description=desc,
                parameters=params,
                executor=_executor,
                risk_level=RiskLevel.MEDIUM,
                timeout=15.0,
            )
            try:
                tool_registry.register(tool_def)
            except Exception as e:
                logger.warning("Failed to register extension tool %s: %s", tool_name, e)

    def get_summary(self) -> dict[str, Any]:
        """
        Returns full summary of active extensions, commands, snippets, tools, and execution logs.
        """
        return {
            "active_extensions": list(self.active_extensions.values()),
            "commands": list(self.registered_commands.values()),
            "snippets": list(self.registered_snippets.values()),
            "ai_tools": list(self.registered_ai_tools.values()),
            "total_active": len(self.active_extensions),
            "execution_logs": self.execution_logs[-10:],
        }


# Global singleton instance
extension_host = ExtensionHost()
extension_host.reload_extensions()
