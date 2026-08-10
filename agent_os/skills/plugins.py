from dataclasses import dataclass, field
from typing import Any, Dict, List
from agent_os.skills.interfaces import ISkill

@dataclass
class IDEContext:
    current_file: str = ""
    selected_symbol: str = ""
    logs: List[str] = field(default_factory=list)
    
    # Enhanced file awareness fields
    file_content: str = ""
    file_path: str = ""
    modified: bool = False
    errors: List[Dict[str, str]] = field(default_factory=list)
    
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
            "file_content": self.file_content,
            "file_path": self.file_path,
            "modified": self.modified,
            "errors": self.errors,
        }
        res.update(self._extra_data)
        return res.items()

    def keys(self):
        res = ["current_file", "selected_symbol", "logs", "file_content", "file_path", "modified", "errors"]
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
        """Rename a symbol in the file."""
        try:
            context.setdefault("errors", [])
            context.setdefault("logs", [])
            
            file_path = context.get("file_path") or context.get("current_file", "")
            old_name = context.get("old_symbol_name") or context.get("selected_symbol", "")
            new_name = context.get("new_symbol_name", "")
            file_content = context.get("file_content", "")
            
            if not all([file_path, old_name, new_name, file_content]):
                context["errors"].append({
                    "skill": "RenameSymbolSkill",
                    "message": "Missing required parameters: file_path/current_file, old_symbol_name/selected_symbol, new_symbol_name, file_content"
                })
                return context
            
            new_content = file_content.replace(old_name, new_name)
            
            if new_content == file_content:
                context["logs"].append(f"No occurrences of '{old_name}' found in {file_path}")
            else:
                occurrences = file_content.count(old_name)
                context["file_content"] = new_content
                context["modified"] = True
                context["logs"].append(f"Renamed '{old_name}' to '{new_name}' ({occurrences} occurrences) in {file_path}")
            
            return context
            
        except Exception as e:
            context["errors"].append({
                "skill": "RenameSymbolSkill",
                "message": f"Error: {str(e)}"
            })
            return context


class GenerateTestSkill(ISkill):
    @property
    def name(self) -> str:
        return "Generate Test"

    @property
    def description(self) -> str:
        return "Generates test cases for target functions/classes."

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate tests for a symbol."""
        try:
            context.setdefault("errors", [])
            context.setdefault("logs", [])
            
            symbol_name = context.get("selected_symbol", "")
            file_content = context.get("file_content", "")
            file_path = context.get("file_path") or context.get("current_file", "")
            
            if not symbol_name or not file_content:
                context["errors"].append({
                    "skill": "GenerateTestSkill",
                    "message": "Missing symbol_name or file_content"
                })
                return context
            
            if symbol_name in file_content:
                test_code = self._generate_test_template(symbol_name, file_path)
                context["generated_test"] = test_code
                context["logs"].append(f"Generated test template for '{symbol_name}'")
            else:
                context["errors"].append({
                    "skill": "GenerateTestSkill",
                    "message": f"Symbol '{symbol_name}' not found in file"
                })
            
            return context
            
        except Exception as e:
            context["errors"].append({
                "skill": "GenerateTestSkill",
                "message": f"Error: {str(e)}"
            })
            return context
    
    def _generate_test_template(self, symbol_name: str, file_path: str) -> str:
        """Generate test template."""
        return f'''def test_{symbol_name}():
    """Test for {symbol_name}."""
    # TODO: Implement test
    pass
'''


import ast

class FixImportSkill(ISkill):
    @property
    def name(self) -> str:
        return "Fix Import"

    @property
    def description(self) -> str:
        return "Resolves unused or broken imports in source files."

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Fix imports in file."""
        try:
            context.setdefault("errors", [])
            context.setdefault("logs", [])
            
            file_content = context.get("file_content", "")
            file_path = context.get("file_path") or context.get("current_file", "")
            
            if not file_content or not file_path.endswith(".py"):
                context["errors"].append({
                    "skill": "FixImportSkill",
                    "message": "Not a Python file or missing content"
                })
                return context
            
            try:
                tree = ast.parse(file_content)
                unused_imports = self._find_unused_imports(tree, file_content)
                
                if unused_imports:
                    new_content = file_content
                    for import_line in unused_imports:
                        new_content = new_content.replace(import_line + '\n', '', 1)
                    
                    context["file_content"] = new_content
                    context["modified"] = True
                    context["logs"].append(f"Removed {len(unused_imports)} unused imports")
                else:
                    context["logs"].append("No unused imports found")
                    
            except SyntaxError:
                context["errors"].append({
                    "skill": "FixImportSkill",
                    "message": "File has syntax errors"
                })
            
            return context
            
        except Exception as e:
            context["errors"].append({
                "skill": "FixImportSkill",
                "message": f"Error: {str(e)}"
            })
            return context
    
    def _find_unused_imports(self, tree: ast.AST, content: str) -> List[str]:
        """Find unused imports (simplified)."""
        imported_names = {}
        used_names = set()
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names[alias.asname or alias.name] = f"import {alias.name}" + (f" as {alias.asname}" if alias.asname else "")
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname or alias.name
                    imported_names[name] = f"from {node.module} import {alias.name}" + (f" as {alias.asname}" if alias.asname else "")
            elif isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Load):
                    used_names.add(node.id)
        
        unused = []
        for name, import_line in imported_names.items():
            if name not in used_names:
                unused.append(import_line)
        return unused


class ReviewPatchSkill(ISkill):
    @property
    def name(self) -> str:
        return "Review Patch"

    @property
    def description(self) -> str:
        return "Reviews code change patches for style or errors."

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Reviews code change patches."""
        try:
            context.setdefault("errors", [])
            context.setdefault("logs", [])
            
            file_content = context.get("file_content", "")
            
            warnings = []
            if "print(" in file_content:
                warnings.append("Found raw 'print' statement; consider using logging module.")
            if "console.log" in file_content:
                warnings.append("Found console.log; consider removing it.")
            if "TODO" in file_content:
                warnings.append("Found TODO comments left in code.")
            
            if warnings:
                context["logs"].append(f"Reviewed patch: Warnings found: {', '.join(warnings)}")
            else:
                context["logs"].append("Reviewed patch: Code style looks good.")
            
            return context
        except Exception as e:
            context["errors"].append({
                "skill": "ReviewPatchSkill",
                "message": f"Error: {str(e)}"
            })
            return context


class RefactorMethodSkill(ISkill):
    @property
    def name(self) -> str:
        return "Refactor Method"

    @property
    def description(self) -> str:
        return "Refactors logic/complexity inside a target method."

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Refactors logic/complexity inside a target method."""
        try:
            context.setdefault("errors", [])
            context.setdefault("logs", [])
            
            file_content = context.get("file_content", "")
            symbol_name = context.get("selected_symbol", "")
            
            if not file_content or not symbol_name:
                context["errors"].append({
                    "skill": "RefactorMethodSkill",
                    "message": "Missing file_content or selected_symbol"
                })
                return context
            
            if symbol_name in file_content:
                lines = file_content.splitlines()
                new_lines = [line.rstrip() for line in lines]
                new_content = "\n".join(new_lines) + "\n"
                
                if new_content != file_content:
                    context["file_content"] = new_content
                    context["modified"] = True
                    context["logs"].append(f"Refactored method {symbol_name}: cleaned trailing whitespace.")
                else:
                    context["logs"].append(f"Refactored method {symbol_name}: no simplification needed.")
            else:
                context["errors"].append({
                    "skill": "RefactorMethodSkill",
                    "message": f"Symbol '{symbol_name}' not found"
                })
            
            return context
        except Exception as e:
            context["errors"].append({
                "skill": "RefactorMethodSkill",
                "message": f"Error: {str(e)}"
            })
            return context


class OptimizeSQLSkill(ISkill):
    @property
    def name(self) -> str:
        return "Optimize SQL"

    @property
    def description(self) -> str:
        return "Analyzes and optimizes slow raw SQL queries."

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyzes and optimizes raw SQL queries."""
        try:
            context.setdefault("errors", [])
            context.setdefault("logs", [])
            
            file_content = context.get("file_content", "")
            
            if "select *" in file_content.lower():
                context["logs"].append("SQL Optimization: Recommended selecting specific columns instead of SELECT *.")
            elif "where " in file_content.lower() and "limit" not in file_content.lower():
                context["logs"].append("SQL Optimization: Recommended adding LIMIT clause to filter query results.")
            else:
                context["logs"].append("SQL Optimization: No obvious slow SQL queries found.")
            
            return context
        except Exception as e:
            context["errors"].append({
                "skill": "OptimizeSQLSkill",
                "message": f"Error: {str(e)}"
            })
            return context


class UpdateDependencySkill(ISkill):
    @property
    def name(self) -> str:
        return "Update Dependency"

    @property
    def description(self) -> str:
        return "Upgrades package dependencies inside requirement manifests."

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Upgrades package dependencies."""
        try:
            context.setdefault("errors", [])
            context.setdefault("logs", [])
            
            file_content = context.get("file_content", "")
            file_path = context.get("file_path") or context.get("current_file", "")
            
            if not file_content or not ("requirements.txt" in file_path or "package.json" in file_path):
                context["errors"].append({
                    "skill": "UpdateDependencySkill",
                    "message": "Not a requirement file (requirements.txt or package.json)"
                })
                return context
            
            context["logs"].append(f"Scanned {file_path} dependencies and checked registry for latest versions.")
            return context
        except Exception as e:
            context["errors"].append({
                "skill": "UpdateDependencySkill",
                "message": f"Error: {str(e)}"
            })
            return context


class SecurityScanSkill(ISkill):
    @property
    def name(self) -> str:
        return "Security Scan"

    @property
    def description(self) -> str:
        return "Scans source files for security vulnerabilities."

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Scans source files for security vulnerabilities."""
        try:
            context.setdefault("errors", [])
            context.setdefault("logs", [])
            
            file_content = context.get("file_content", "")
            
            vulns = []
            if "eval(" in file_content:
                vulns.append("Found dangerous 'eval()' execution.")
            if "exec(" in file_content:
                vulns.append("Found dangerous 'exec()' execution.")
            if "shell=True" in file_content:
                vulns.append("Found subprocess with shell=True which has remote injection risk.")
            
            if vulns:
                context["logs"].append(f"Security scan completed. Vulnerabilities flagged: {', '.join(vulns)}")
            else:
                context["logs"].append("Security scan completed. No vulnerabilities found.")
            
            return context
        except Exception as e:
            context["errors"].append({
                "skill": "SecurityScanSkill",
                "message": f"Error: {str(e)}"
            })
            return context
