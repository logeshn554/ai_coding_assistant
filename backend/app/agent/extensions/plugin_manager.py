"""
Phase 15: Extensible AI IDE Platform & Plugin Ecosystem.

Defines plugin interfaces (LanguageProvider, ModelProvider, ToolProvider, ContextProvider),
and manages plugin lifecycle (install, validate, authorize, activate, disable, uninstall)
under strict PermissionEngine security bounds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ..security.permission_engine import PermissionEngine


class PluginState(str, Enum):
    INSTALLED = "INSTALLED"
    VALIDATED = "VALIDATED"
    AUTHORIZED = "AUTHORIZED"
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    UNINSTALLED = "UNINSTALLED"


@dataclass
class PluginManifest:
    name: str
    version: str
    description: str
    capabilities: List[str] = field(default_factory=list)
    permissions_required: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)


@dataclass
class PluginRegistration:
    manifest: PluginManifest
    state: PluginState = PluginState.INSTALLED
    health_status: str = "HEALTHY"


class PluginManager:
    """Manages extension plugin registration, security authorization, and execution lifecycle."""

    def __init__(self, workspace_root: str) -> None:
        self.workspace_root = workspace_root
        self.plugins: Dict[str, PluginRegistration] = {}
        self.permission_engine = PermissionEngine.get_instance(workspace_root)

    def install_plugin(self, manifest: PluginManifest) -> PluginRegistration:
        reg = PluginRegistration(manifest=manifest, state=PluginState.INSTALLED)
        self.plugins[manifest.name] = reg
        return reg

    def validate_plugin(self, plugin_name: str) -> bool:
        reg = self.plugins.get(plugin_name)
        if not reg:
            return False

        # Validate required fields
        m = reg.manifest
        if not m.name or not m.version:
            reg.state = PluginState.DISABLED
            reg.health_status = "INVALID_MANIFEST"
            return False

        reg.state = PluginState.VALIDATED
        return True

    def authorize_and_activate_plugin(self, plugin_name: str, session_id: str) -> bool:
        reg = self.plugins.get(plugin_name)
        if not reg or reg.state != PluginState.VALIDATED:
            return False

        # Authorize plugin permissions through PermissionEngine
        for perm in reg.manifest.permissions_required:
            decision = self.permission_engine.evaluate_tool_call(
                session_id=session_id,
                tool_name=perm,
                arguments={"path": self.workspace_root},
            )
            if not decision.allowed:
                reg.state = PluginState.DISABLED
                reg.health_status = f"PERMISSION_DENIED_{perm}"
                return False

        reg.state = PluginState.ACTIVE
        reg.health_status = "HEALTHY"
        return True

    def disable_plugin(self, plugin_name: str) -> None:
        if plugin_name in self.plugins:
            self.plugins[plugin_name].state = PluginState.DISABLED

    def uninstall_plugin(self, plugin_name: str) -> None:
        if plugin_name in self.plugins:
            self.plugins[plugin_name].state = PluginState.UNINSTALLED
            del self.plugins[plugin_name]
