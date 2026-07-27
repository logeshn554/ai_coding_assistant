"""
workspace_graph.py — AST Dependency Graph & Architecture Visualizer for Antigravity.

Parses workspace files to construct a dependency node-edge graph tracking
file nodes, components, hooks, contexts, imports, exports, and circular dependencies.
"""

import os
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple

logger = logging.getLogger("antigravity.graph")

_SKIP_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__", ".devpilot",
    "dist", "build", ".next", "target", "out", ".cache", "coverage"
}


def build_workspace_graph(workspace_root: str) -> Dict[str, Any]:
    """
    Scans the workspace and builds a node/edge dependency graph.
    Detects circular imports and architectural hubs.
    """
    if not workspace_root or not os.path.isdir(workspace_root):
        return {"nodes": [], "edges": [], "circular_imports": [], "summary": {}}

    root_path = Path(workspace_root)
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    file_map: Dict[str, str] = {}  # rel_path -> node_id
    adjacency: Dict[str, Set[str]] = {}  # node_id -> set of target node_ids

    # 1. Collect all code files
    code_extensions = {".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".rs", ".java"}
    rel_files: List[str] = []

    for path in root_path.rglob("*"):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in code_extensions:
            rel = str(path.relative_to(root_path)).replace("\\", "/")
            rel_files.append(rel)

    # 2. Build nodes
    for idx, rel in enumerate(rel_files[:300]):  # Cap at 300 for optimal UI performance
        node_id = f"node_{idx}"
        file_map[rel] = node_id
        file_name = os.path.basename(rel)

        # Categorize node type
        node_type = "file"
        if "component" in rel.lower() or rel.endswith((".tsx", ".jsx")):
            node_type = "component"
        elif "context" in rel.lower():
            node_type = "context"
        elif "hook" in rel.lower() or file_name.startswith("use"):
            node_type = "hook"
        elif "route" in rel.lower() or "api" in rel.lower():
            node_type = "api"
        elif "service" in rel.lower():
            node_type = "service"

        nodes.append({
            "id": node_id,
            "label": file_name,
            "path": rel,
            "type": node_type,
            "extension": os.path.splitext(file_name)[1],
        })
        adjacency[node_id] = set()

    # 3. Parse imports to build edges
    import_regex = re.compile(r'(?:import|from)\s+[\'"]([^\'"]+)[\'"]')
    py_import_regex = re.compile(r'(?:from|import)\s+([\w\.]+)')

    for node in nodes:
        source_id = node["id"]
        rel_path = node["path"]
        abs_path = root_path / rel_path

        try:
            content = abs_path.read_text(encoding="utf-8", errors="ignore")[:5000]
        except Exception:
            continue

        imported_paths: List[str] = []
        if rel_path.endswith((".ts", ".tsx", ".js", ".jsx")):
            imported_paths = import_regex.findall(content)
            for imp in imported_paths:
                resolved_target = None
                if imp.startswith("."):
                    curr_dir = os.path.dirname(rel_path)
                    candidate = os.path.normpath(os.path.join(curr_dir, imp)).replace("\\", "/")
                    for ext in ["", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx"]:
                        test_p = candidate + ext
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
            py_matches = re.findall(r'(?:from|import)\s+([\.\w]+)', content)
            curr_dir = os.path.dirname(rel_path)
            for p_imp in py_matches:
                resolved_target = None
                if p_imp.startswith("."):
                    dots_count = len(p_imp) - len(p_imp.lstrip("."))
                    sub_mod = p_imp.lstrip(".")
                    mod_parts = sub_mod.split(".") if sub_mod else []
                    
                    target_dir = curr_dir
                    for _ in range(dots_count - 1):
                        target_dir = os.path.dirname(target_dir)
                    
                    rel_mod_path = os.path.normpath(os.path.join(target_dir, *mod_parts)).replace("\\", "/")
                    for ext in [".py", "/__init__.py"]:
                        test_p = rel_mod_path + ext
                        if test_p in file_map:
                            resolved_target = file_map[test_p]
                            break
                else:
                    # Absolute Python module import
                    mod_path = p_imp.replace(".", "/")
                    for test_p in [f"{mod_path}.py", f"{mod_path}/__init__.py"]:
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
                # Cycle found
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
        "circular_imports": circular_imports[:10],  # Return top 10 circular dependency chains
        "summary": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "circular_count": len(circular_imports),
        }
    }
