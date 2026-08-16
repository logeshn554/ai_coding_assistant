import ast
import re

# Optional Tree-sitter integration placeholders
HAS_TREE_SITTER = False
try:
    import tree_sitter  # noqa: F401
    HAS_TREE_SITTER = True
except ImportError:
    pass

class SymbolInfo:
    def __init__(self, name: str, sym_type: str, start_line: int, start_col: int, end_line: int, end_col: int, signature: str = "") -> None:
        self.name = name
        self.sym_type = sym_type
        self.start_line = start_line
        self.start_col = start_col
        self.end_line = end_line
        self.end_col = end_col
        self.signature = signature

class ReferenceInfo:
    def __init__(self, name: str, line: int, col: int) -> None:
        self.name = name
        self.line = line
        self.col = col

def detect_language(path: str) -> str:
    ext = path.split(".")[-1].lower() if "." in path else ""
    mapping = {
        "py": "python",
        "js": "javascript",
        "jsx": "javascript",
        "ts": "typescript",
        "tsx": "typescript",
        "go": "go",
        "rs": "rust",
        "java": "java",
        "cpp": "cpp",
        "c": "c",
        "h": "c",
        "hpp": "cpp",
        "html": "html",
        "css": "css",
        "sh": "shell",
        "bat": "batch",
        "ps1": "powershell",
        "md": "markdown",
        "json": "json",
        "yaml": "yaml",
        "yml": "yaml",
        "toml": "toml",
    }
    return mapping.get(ext, "unknown")

def parse_python(code: str) -> tuple[list[SymbolInfo], list[ReferenceInfo]]:
    symbols: list[SymbolInfo] = []
    references: list[ReferenceInfo] = []
    
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return symbols, references

    class PythonVisitor(ast.NodeVisitor):
        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            symbols.append(SymbolInfo(
                name=node.name,
                sym_type="class",
                start_line=node.lineno,
                start_col=node.col_offset,
                end_line=getattr(node, "end_lineno", node.lineno),
                end_col=getattr(node, "end_col_offset", node.col_offset),
                signature=f"class {node.name}"
            ))
            self.generic_visit(node)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            symbols.append(SymbolInfo(
                name=node.name,
                sym_type="function",
                start_line=node.lineno,
                start_col=node.col_offset,
                end_line=getattr(node, "end_lineno", node.lineno),
                end_col=getattr(node, "end_col_offset", node.col_offset),
                signature=f"def {node.name}(...)"
            ))
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            symbols.append(SymbolInfo(
                name=node.name,
                sym_type="function",
                start_line=node.lineno,
                start_col=node.col_offset,
                end_line=getattr(node, "end_lineno", node.lineno),
                end_col=getattr(node, "end_col_offset", node.col_offset),
                signature=f"async def {node.name}(...)"
            ))
            self.generic_visit(node)

        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                symbols.append(SymbolInfo(
                    name=alias.name,
                    sym_type="import",
                    start_line=node.lineno,
                    start_col=node.col_offset,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    end_col=getattr(node, "end_col_offset", node.col_offset),
                    signature=f"import {alias.name}"
                ))
            self.generic_visit(node)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            module = node.module or ""
            for alias in node.names:
                symbols.append(SymbolInfo(
                    name=alias.name,
                    sym_type="import",
                    start_line=node.lineno,
                    start_col=node.col_offset,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    end_col=getattr(node, "end_col_offset", node.col_offset),
                    signature=f"from {module} import {alias.name}"
                ))
            self.generic_visit(node)

        def visit_Name(self, node: ast.Name) -> None:
            if isinstance(node.ctx, ast.Load):
                references.append(ReferenceInfo(
                    name=node.id,
                    line=node.lineno,
                    col=node.col_offset
                ))
            self.generic_visit(node)

        def visit_Attribute(self, node: ast.Attribute) -> None:
            if isinstance(node.ctx, ast.Load):
                references.append(ReferenceInfo(
                    name=node.attr,
                    line=node.lineno,
                    col=node.col_offset
                ))
            self.generic_visit(node)

    PythonVisitor().visit(tree)
    return symbols, references

def parse_regex_based(code: str) -> tuple[list[SymbolInfo], list[ReferenceInfo]]:
    """Generic fallback parsing using regexes."""
    symbols: list[SymbolInfo] = []
    references: list[ReferenceInfo] = []

    lines = code.splitlines()

    class_pattern = re.compile(r'\bclass\s+([A-Za-z0-9_]+)')
    function_pattern = re.compile(r'\b(?:function|def|fn)\s+([A-Za-z0-9_]+)\b|([A-Za-z0-9_]+)\s*\([^)]*\)\s*\{|const\s+([A-Za-z0-9_]+)\s*=\s*(?:\([^)]*\)|[A-Za-z0-9_]+)\s*=>')
    import_pattern = re.compile(r'\bimport\s+(?:[^;]+from\s+)?[\'"]([^\'"]+)[\'"]|\bimport\s+([A-Za-z0-9_,\s{}*]+)\b|\brequire\s*\([\'"]([^\'"]+)[\'"]\)')
    export_pattern = re.compile(r'\bexport\s+(?:default\s+)?(?:const|class|let|function)\s+([A-Za-z0-9_]+)\b')
    word_pattern = re.compile(r'\b([A-Za-z0-9_]+)\b')

    for idx, line in enumerate(lines, start=1):
        line_clean = re.sub(r'//.*|/\*.*\*/', '', line)
        
        # 1. Classes
        match = class_pattern.search(line_clean)
        if match:
            name = match.group(1)
            symbols.append(SymbolInfo(name, "class", idx, match.start(1), idx, match.end(1), signature=f"class {name}"))
            continue

        # 2. Functions
        match = function_pattern.search(line_clean)
        if match:
            name = next((g for g in match.groups() if g is not None), None)
            if name:
                symbols.append(SymbolInfo(name, "function", idx, line_clean.find(name), idx, line_clean.find(name) + len(name), signature=f"function {name}"))
                continue

        # 3. Imports
        match = import_pattern.search(line_clean)
        if match:
            name = next((g for g in match.groups() if g is not None), None)
            if name:
                symbols.append(SymbolInfo(name, "import", idx, line_clean.find(name), idx, line_clean.find(name) + len(name), signature=f"import {name}"))
                continue

        # 4. Exports
        match = export_pattern.search(line_clean)
        if match:
            name = match.group(1)
            symbols.append(SymbolInfo(name, "export", idx, match.start(1), idx, match.end(1), signature=f"export {name}"))
            continue

        # 5. References (generic word tokens)
        for m in word_pattern.finditer(line_clean):
            word = m.group(1)
            if word not in {"if", "for", "while", "return", "const", "let", "var", "import", "export", "class", "function", "def", "async", "await", "self", "this", "true", "false", "null", "undefined"}:
                references.append(ReferenceInfo(word, idx, m.start(1)))

    return symbols, references

def parse_code(code: str, language: str) -> tuple[list[SymbolInfo], list[ReferenceInfo]]:
    # Fallback structure matching tree-sitter integration requirement
    if HAS_TREE_SITTER:
        pass

    if language == "python":
        return parse_python(code)
    else:
        return parse_regex_based(code)
