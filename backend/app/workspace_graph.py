"""
workspace_graph.py — AST Dependency Graph & Architecture Visualizer for Antigravity.

Parses workspace files to construct a dependency node-edge graph tracking
file nodes, components, hooks, contexts, APIs, services, databases, imports, exports, and circular dependencies.
"""

import os
import sys
import re
import ast
import json
import hashlib
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple, Optional
from .state import config_manager

logger = logging.getLogger("antigravity.graph")

_SKIP_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__", ".devpilot",
    "dist", "build", ".next", "target", "out", ".cache", "coverage"
}


def extract_database_models(content: str, ext: str) -> List[Dict[str, Any]]:
    """
    Detect ORM models and schemas (SQLAlchemy, Django, Mongoose, Prisma) and return schema details.
    """
    models: List[Dict[str, Any]] = []

    if ext == ".py":
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    is_orm = any(
                        (isinstance(b, ast.Name) and b.id in ("Base", "DeclarativeBase", "Model", "SQLModel")) or
                        (isinstance(b, ast.Attribute) and b.attr in ("Base", "DeclarativeBase", "Model", "SQLModel"))
                        for b in node.bases
                    )
                    if is_orm:
                        table_name = node.name.lower()
                        fields: List[str] = []
                        for item in node.body:
                            if isinstance(item, ast.Assign):
                                for target in item.targets:
                                    if isinstance(target, ast.Name):
                                        if target.id == "__tablename__":
                                            if isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                                                table_name = item.value.value
                                            elif isinstance(item.value, ast.Str):
                                                table_name = item.value.s
                                        elif not target.id.startswith("_"):
                                            fields.append(target.id)
                            elif isinstance(item, ast.AnnAssign):
                                if isinstance(item.target, ast.Name) and not item.target.id.startswith("_"):
                                    fields.append(item.target.id)
                        models.append({
                            "model_name": node.name,
                            "table_name": table_name,
                            "fields": fields
                        })
        except Exception:
            pass

    elif ext in (".js", ".ts", ".tsx"):
        # Mongoose schema
        schema_matches = re.finditer(r'(?:const|let|var)\s+(\w+)\s*=\s*new\s+(?:mongoose\.)?Schema\(\s*\{([^}]+)\}', content)
        for m in schema_matches:
            model_name = m.group(1).replace('Schema', '') or 'Model'
            fields_raw = m.group(2)
            fields = [f.strip().split(':')[0].strip() for f in fields_raw.split(',') if ':' in f and not f.strip().startswith('//')]
            models.append({
                "model_name": model_name,
                "table_name": model_name.lower() + 's',
                "fields": fields
            })

        if not models:
            model_calls = re.findall(r'mongoose\.model\s*\(\s*[\'"](\w+)[\'"]', content)
            for m_name in model_calls:
                models.append({
                    "model_name": m_name,
                    "table_name": m_name.lower() + 's',
                    "fields": []
                })

    elif ext == ".prisma":
        prisma_models = re.finditer(r'model\s+(\w+)\s*\{([^}]+)\}', content)
        for pm in prisma_models:
            m_name = pm.group(1)
            body = pm.group(2)
            fields = [line.strip().split()[0] for line in body.splitlines() if line.strip() and not line.strip().startswith('//') and not line.strip().startswith('@@')]
            models.append({
                "model_name": m_name,
                "table_name": m_name.lower() + 's',
                "fields": fields
            })

    return models


def categorize_node(rel_path: str, content: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Categorize node_type based on actual code structure:
    - database: ORM models/schemas with table names & fields
    - hook: React hooks
    - api: API routes (FastAPI, Flask, Express, Next.js)
    - component: React components
    - service: Services, Managers, Adapters
    - context: React Context
    - file: General fallback
    """
    ext = os.path.splitext(rel_path)[1].lower()
    file_name = os.path.basename(rel_path)

    # 1. Database Model Check
    db_models = extract_database_models(content, ext)
    if db_models:
        return "database", {"tables": db_models}

    # 2. React Hook Check
    is_hook_named = file_name.startswith("use") or "hook" in rel_path.lower()
    has_hook_calls = bool(re.search(r'\b(useState|useEffect|useContext|useCallback|useMemo|useRef|useReducer|useLayoutEffect|use[A-Z]\w*)\b', content))
    if is_hook_named and has_hook_calls:
        return "hook", None

    # 3. API Route Check
    has_py_api = bool(re.search(r'@(?:router|app|blueprint|api)\.(?:get|post|put|delete|patch|route)\b', content))
    has_js_api = bool(re.search(r'\b(?:router|app)\.(?:get|post|put|delete|patch|route)\b', content))
    has_next_api = bool(re.search(r'export\s+async\s+function\s+(?:GET|POST|PUT|DELETE|PATCH)\b', content))
    if has_py_api or has_js_api or has_next_api or ("route" in rel_path.lower() and (has_py_api or has_js_api)):
        return "api", None

    # 4. Context Check
    if "createContext" in content or "React.createContext" in content:
        return "context", None

    # 5. React Component Check
    if ext in (".tsx", ".jsx") or (ext in (".js", ".ts") and ("React" in content or "JSX" in content)):
        has_jsx_return = bool(re.search(r'return\s*\(\s*<[a-zA-Z]|return\s+<[a-zA-Z]|JSX\.Element|React\.FC|React\.FunctionComponent|React\.Component', content))
        has_jsx_tags = bool(re.search(r'<[A-Z]\w+[\s/>]', content))
        if has_jsx_return or has_jsx_tags or ext in (".tsx", ".jsx"):
            return "component", None

    # 6. Service Check
    has_service_class = bool(re.search(r'class\s+\w*(?:Service|Adapter|Manager|Repository|Controller)\b', content))
    has_service_methods = bool(re.search(r'async\s+(?:find|get|create|update|delete|execute|process)\w*\s*\(', content))
    if has_service_class or ("service" in rel_path.lower() and has_service_methods):
        return "service", None

    if is_hook_named:
        return "hook", None

    return "file", None


def parse_python_imports(content: str) -> List[Tuple[str, int, str]]:
    """
    Walk Python AST to extract all imports.
    Returns tuples of (module_name, level, imported_name).
    level > 0 indicates relative import (e.g. from . import x).
    """
    imports: List[Tuple[str, int, str]] = []
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append((alias.name, 0, ""))
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                level = node.level or 0
                for alias in node.names:
                    imports.append((mod, level, alias.name))
    except Exception:
        # Fallback to regex if syntax error in partial python file
        py_matches = re.findall(r'(?:from|import)\s+([\.\w]+)', content)
        for p in py_matches:
            if p.startswith("."):
                dots = len(p) - len(p.lstrip("."))
                imports.append((p.lstrip("."), dots, ""))
            else:
                imports.append((p, 0, ""))
    return imports


def parse_js_ts_imports_batch(workspace_root: str, js_ts_files: List[str]) -> Dict[str, List[str]]:
    """
    Invokes js_ast_parser.js Node script to get real AST imports + tsconfig path alias resolution.
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        js_parser_script = os.path.join(sys._MEIPASS, "backend", "app", "js_ast_parser.js")
    else:
        js_parser_script = os.path.join(os.path.dirname(__file__), "js_ast_parser.js")
    if not os.path.exists(js_parser_script):
        return {}

    payload = json.dumps({"workspace_root": workspace_root, "files": js_ts_files})
    from backend.app.agent.security.environment_isolation import EnvironmentIsolation
    env = EnvironmentIsolation.get_isolated_env()
    try:
        proc = subprocess.Popen(
            ["node", js_parser_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=workspace_root,
            env=env
        )
        stdout, stderr = proc.communicate(input=payload, timeout=10)
        if proc.returncode == 0 and stdout:
            data = json.loads(stdout)
            if isinstance(data, dict) and "error" not in data:
                return data
    except Exception as e:
        logger.warning(f"JS AST parser subprocess failed: {e}")

    return {}


def build_workspace_graph(workspace_root: str) -> Dict[str, Any]:
    """
    Scans the workspace and builds a node/edge dependency graph using real AST parsing.
    Detects circular imports and exposes content-based categorization & Database node types.
    Explicitly reports total files found and truncation status.
    """
    if not workspace_root or not os.path.isdir(workspace_root):
        return {
            "nodes": [],
            "edges": [],
            "circular_imports": [],
            "summary": {
                "total_nodes": 0,
                "total_edges": 0,
                "circular_count": 0,
                "total_files_found": 0,
                "truncated": False
            },
            "total_files_found": 0,
            "truncated": False
        }

    root_path = Path(workspace_root)
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    file_map: Dict[str, str] = {}  # rel_path -> node_id
    adjacency: Dict[str, Set[str]] = {}  # node_id -> set of target node_ids

    # 1. Collect all code files
    code_extensions = {".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".rs", ".java", ".prisma"}
    rel_files: List[str] = []

    for path in root_path.rglob("*"):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in code_extensions:
            rel = str(path.relative_to(root_path)).replace("\\", "/")
            rel_files.append(rel)

    total_files_found = len(rel_files)
    is_truncated = total_files_found > 300
    selected_files = rel_files[:300]

    # 2. Build nodes with structural categorization
    for idx, rel in enumerate(selected_files):
        node_id = f"node_{idx}"
        file_map[rel] = node_id
        file_name = os.path.basename(rel)
        abs_path = root_path / rel

        try:
            content = abs_path.read_text(encoding="utf-8", errors="ignore")[:10000]
        except Exception:
            content = ""

        node_type, db_info = categorize_node(rel, content)

        node_dict: Dict[str, Any] = {
            "id": node_id,
            "label": file_name,
            "path": rel,
            "type": node_type,
            "extension": os.path.splitext(file_name)[1],
        }
        if db_info:
            node_dict["db_info"] = db_info

        nodes.append(node_dict)
        adjacency[node_id] = set()

    # 3. Parse imports to build edges using AST parsers
    js_ts_files = [n["path"] for n in nodes if n["path"].endswith((".ts", ".tsx", ".js", ".jsx"))]
    js_ast_imports = parse_js_ts_imports_batch(workspace_root, js_ts_files)

    for node in nodes:
        source_id = node["id"]
        rel_path = node["path"]
        abs_path = root_path / rel_path

        try:
            content = abs_path.read_text(encoding="utf-8", errors="ignore")[:10000]
        except Exception:
            continue

        if rel_path.endswith((".ts", ".tsx", ".js", ".jsx")):
            imported_specifiers = js_ast_imports.get(rel_path, [])
            if not imported_specifiers:
                # Regex fallback if AST batch parser returned empty
                imported_specifiers = re.findall(r'(?:import|from)\s+[\'"]([^\'"]+)[\'"]', content)

            curr_dir = os.path.dirname(rel_path)
            for imp in imported_specifiers:
                resolved_target = None
                
                # Direct match if resolved by tsconfig alias to workspace rel_path
                if imp in file_map:
                    resolved_target = file_map[imp]
                else:
                    candidates: List[str] = []
                    if imp.startswith("."):
                        cand = os.path.normpath(os.path.join(curr_dir, imp)).replace("\\", "/")
                    else:
                        cand = imp.replace("\\", "/")

                    for ext in ["", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx", "/index.js"]:
                        candidates.append(cand + ext)

                    for test_p in candidates:
                        if test_p in file_map:
                            resolved_target = file_map[test_p]
                            break

                if resolved_target and resolved_target != source_id:
                    if resolved_target not in adjacency[source_id]:
                        adjacency[source_id].add(resolved_target)
                        edges.append({
                            "id": f"edge_{source_id}_{resolved_target}",
                            "source": source_id,
                            "target": resolved_target,
                        })

        elif rel_path.endswith(".py"):
            py_imports = parse_python_imports(content)
            curr_dir = os.path.dirname(rel_path)

            for mod, level, imported_name in py_imports:
                resolved_target = None

                if level > 0:
                    target_dir = curr_dir
                    for _ in range(level - 1):
                        target_dir = os.path.dirname(target_dir)

                    mod_parts = mod.split(".") if mod else []
                    rel_mod_path = os.path.normpath(os.path.join(target_dir, *mod_parts)).replace("\\", "/")
                    
                    test_candidates = [
                        f"{rel_mod_path}.py",
                        f"{rel_mod_path}/__init__.py",
                    ]
                    if imported_name:
                        test_candidates.extend([
                            f"{rel_mod_path}/{imported_name}.py",
                            f"{rel_mod_path}/{imported_name}/__init__.py"
                        ])

                    for test_p in test_candidates:
                        norm_p = os.path.normpath(test_p).replace("\\", "/")
                        if norm_p in file_map:
                            resolved_target = file_map[norm_p]
                            break
                else:
                    mod_path = mod.replace(".", "/")
                    test_candidates = [
                        f"{mod_path}.py",
                        f"{mod_path}/__init__.py",
                    ]
                    if imported_name:
                        test_candidates.extend([
                            f"{mod_path}/{imported_name}.py",
                            f"{mod_path}/{imported_name}/__init__.py"
                        ])

                    for test_p in test_candidates:
                        if test_p in file_map:
                            resolved_target = file_map[test_p]
                            break
                        # Search by suffix matching file_map keys
                        for fm_key, fm_id in file_map.items():
                            if fm_key.endswith(test_p):
                                resolved_target = fm_id
                                break
                        if resolved_target:
                            break

                if resolved_target and resolved_target != source_id:
                    if resolved_target not in adjacency[source_id]:
                        adjacency[source_id].add(resolved_target)
                        edges.append({
                            "id": f"edge_{source_id}_{resolved_target}",
                            "source": source_id,
                            "target": resolved_target,
                        })

    # 4. Detect Circular Imports (Tarjan / Cycle DFS)
    circular_imports: List[List[str]] = []
    visited: Set[str] = set()
    rec_stack: Set[str] = set()
    curr_path: List[str] = []

    def dfs(node_id: str):
        visited.add(node_id)
        rec_stack.add(node_id)
        curr_path.append(node_id)

        for neighbor in adjacency.get(node_id, set()):
            if neighbor not in visited:
                dfs(neighbor)
            elif neighbor in rec_stack:
                cycle_start_idx = curr_path.index(neighbor)
                cycle = curr_path[cycle_start_idx:]
                if len(cycle) > 1 and cycle not in circular_imports:
                    circular_imports.append(cycle)

        rec_stack.remove(node_id)
        curr_path.pop()

    for node in nodes:
        if node["id"] not in visited:
            dfs(node["id"])

    return {
        "nodes": nodes,
        "edges": edges,
        "circular_imports": circular_imports[:10],
        "summary": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "circular_count": len(circular_imports),
            "total_files_found": total_files_found,
            "truncated": is_truncated
        },
        "total_files_found": total_files_found,
        "truncated": is_truncated
    }


async def get_or_generate_node_summary(workspace_root: str, node_id: str) -> Dict[str, Any]:
    """
    Lazily generates a 1-2 sentence description for a node in the graph.
    Caches summary in .devpilot/graph_cache.json keyed by file content hash.
    Invalidates on file change.
    """
    graph = build_workspace_graph(workspace_root)
    node = next((n for n in graph["nodes"] if n["id"] == node_id), None)
    if not node:
        return {"error": f"Node {node_id} not found in workspace graph", "summary": ""}

    rel_path = node["path"]
    abs_path = Path(workspace_root) / rel_path
    if not abs_path.is_file():
        return {"error": f"File {rel_path} does not exist", "summary": ""}

    try:
        content = abs_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return {"error": f"Could not read file {rel_path}: {e}", "summary": ""}

    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    # Load cache file
    cache_dir = Path(workspace_root) / ".devpilot"
    cache_file = cache_dir / "graph_cache.json"
    cache_dir.mkdir(parents=True, exist_ok=True)

    cache_data: Dict[str, Any] = {}
    if cache_file.is_file():
        try:
            cache_data = json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            cache_data = {}

    summaries = cache_data.get("summaries", {})
    cached_entry = summaries.get(rel_path)

    if cached_entry and cached_entry.get("hash") == content_hash and cached_entry.get("summary"):
        return {
            "node_id": node_id,
            "path": rel_path,
            "summary": cached_entry["summary"],
            "cached": True
        }

    # Generate new summary via LLM Provider
    summary_text = ""
    try:
        profile = config_manager.get_active_profile()
        if profile and (profile.get("api_key") or "localhost" in profile.get("base_url", "")):
            from .adapters.router import ModelRouter
            router_inst = ModelRouter()
            sys_prompt = (
                "You are an expert software architect. Provide a concise, single-paragraph 1-2 sentence description of "
                "what this specific source code file does in the codebase. Do NOT use markdown code blocks, backticks, or extra meta-text."
            )
            messages = [{"role": "user", "content": f"File path: {rel_path}\n\nContent:\n{content[:3000]}"}]
            raw_summary = await router_inst.completion(profile, messages, system_prompt=sys_prompt)
            summary_text = raw_summary.strip().strip("`").strip('"').strip()
    except Exception as e:
        logger.warning(f"Failed to generate AI summary for {rel_path}: {e}")

    if not summary_text:
        node_type = node.get("type", "file")
        summary_text = f"Source {node_type} file '{node['label']}' providing workspace functionality."

    # Save to cache
    summaries[rel_path] = {
        "hash": content_hash,
        "summary": summary_text
    }
    cache_data["summaries"] = summaries
    try:
        cache_file.write_text(json.dumps(cache_data, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not save graph cache: {e}")

    return {
        "node_id": node_id,
        "path": rel_path,
        "summary": summary_text,
        "cached": False
    }
