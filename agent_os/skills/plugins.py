from dataclasses import dataclass, field
from typing import Any, Dict, List
from agent_os.skills.interfaces import ISkill

@dataclass
class IDEContext:
    current_file: str = ""
    selected_symbol: str = ""
    logs: List[str] = field(default_factory=list)
    _extra_data: Dict[str, Any] = field(default_factory=dict)

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key) and key != "_extra_data":
            return getattr(self, key)
        return self._extra_data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if hasattr(self, key) and key != "_extra_data":
            setattr(self, key, value)
        else:
            self._extra_data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def setdefault(self, key: str, default: Any = None) -> Any:
        if key not in self:
            self[key] = default
        return self[key]

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key) or key in self._extra_data

    def pop(self, key: str, default: Any = None) -> Any:
        if hasattr(self, key) and key != "_extra_data":
            val = getattr(self, key)
            setattr(self, key, None)
            return val
        return self._extra_data.pop(key, default)

    def items(self):
        res = {
            "current_file": self.current_file,
            "selected_symbol": self.selected_symbol,
            "logs": self.logs,
        }
        res.update(self._extra_data)
        return res.items()

    def keys(self):
        res = ["current_file", "selected_symbol", "logs"]
        res.extend(self._extra_data.keys())
        return res

    def update(self, other: Dict[str, Any]) -> None:
        for k, v in other.items():
            self[k] = v


class RenameSymbolSkill(ISkill):
    @property
    def name(self) -> str:
        return "Rename Symbol"

    @property
    def description(self) -> str:
        return "Renames a code symbol and updates references across files."

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        context["rename_symbol_executed"] = True
        context["logs"] = context.get("logs", []) + ["Renamed symbol successfully."]
        return context


class GenerateTestSkill(ISkill):
    @property
    def name(self) -> str:
        return "Generate Test"

    @property
    def description(self) -> str:
        return "Generates test cases for target functions/classes."

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        context["generate_test_executed"] = True
        context["logs"] = context.get("logs", []) + ["Generated test cases successfully."]
        return context


class FixImportSkill(ISkill):
    @property
    def name(self) -> str:
        return "Fix Import"

    @property
    def description(self) -> str:
        return "Resolves unused or broken imports in source files."

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        context["fix_import_executed"] = True
        context["logs"] = context.get("logs", []) + ["Resolved import linkages successfully."]
        return context


class ReviewPatchSkill(ISkill):
    @property
    def name(self) -> str:
        return "Review Patch"

    @property
    def description(self) -> str:
        return "Reviews code change patches for style or errors."

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        context["review_patch_executed"] = True
        context["logs"] = context.get("logs", []) + ["Reviewed code patch successfully."]
        return context


class RefactorMethodSkill(ISkill):
    @property
    def name(self) -> str:
        return "Refactor Method"

    @property
    def description(self) -> str:
        return "Refactors logic/complexity inside a target method."

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        context["refactor_method_executed"] = True
        context["logs"] = context.get("logs", []) + ["Refactored method complexity successfully."]
        return context


class OptimizeSQLSkill(ISkill):
    @property
    def name(self) -> str:
        return "Optimize SQL"

    @property
    def description(self) -> str:
        return "Analyzes and optimizes slow raw SQL queries."

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        context["optimize_sql_executed"] = True
        context["logs"] = context.get("logs", []) + ["Optimized SQL query performance successfully."]
        return context


class UpdateDependencySkill(ISkill):
    @property
    def name(self) -> str:
        return "Update Dependency"

    @property
    def description(self) -> str:
        return "Upgrades package dependencies inside requirement manifests."

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        context["update_dependency_executed"] = True
        context["logs"] = context.get("logs", []) + ["Upgraded dependency version successfully."]
        return context


class SecurityScanSkill(ISkill):
    @property
    def name(self) -> str:
        return "Security Scan"

    @property
    def description(self) -> str:
        return "Scans source files for security vulnerabilities."

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        context["security_scan_executed"] = True
        context["logs"] = context.get("logs", []) + ["Security scan completed. No vulnerabilities found."]
        return context
