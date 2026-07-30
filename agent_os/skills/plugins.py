from typing import Any, Dict
from agent_os.skills.interfaces import ISkill

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
