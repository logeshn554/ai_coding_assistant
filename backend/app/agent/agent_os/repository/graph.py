import os
from typing import Any

from agent_os.repository.interfaces import IRepositoryKnowledgeGraph
from agent_os.repository.repository import RepositoryKernel


class RepositoryKnowledgeGraph(IRepositoryKnowledgeGraph):
    """Repository Knowledge Graph extracting dependency and call-graph relationships from SQLite."""
    def __init__(self, kernel: RepositoryKernel) -> None:
        self.kernel = kernel
        self.db = kernel.db

    def _get_all_functions(self) -> list[dict[str, Any]]:
        with self.db._get_connection() as conn:
            rows = conn.execute("""
                SELECT s.*, f.path as file_path
                FROM symbols s
                JOIN files f ON s.file_id = f.id
                WHERE s.type = 'function';
            """).fetchall()
            return [dict(r) for r in rows]

    def _get_all_classes(self) -> list[dict[str, Any]]:
        with self.db._get_connection() as conn:
            rows = conn.execute("""
                SELECT s.*, f.path as file_path
                FROM symbols s
                JOIN files f ON s.file_id = f.id
                WHERE s.type = 'class';
            """).fetchall()
            return [dict(r) for r in rows]

    def get_dependencies(self, path: str) -> dict[str, list[str]]:
        """Finds files imported by the target file, and files importing it."""
        with self.db._get_connection() as conn:
            file_row = conn.execute("SELECT id FROM files WHERE path = ?;", (path,)).fetchone()
            if not file_row:
                return {"imports": [], "imported_by": []}
            file_id = file_row["id"]

            all_files = [dict(r) for r in conn.execute("SELECT id, path FROM files;").fetchall()]
            import_symbols = conn.execute("SELECT name FROM symbols WHERE file_id = ? AND type = 'import';", (file_id,)).fetchall()
            import_names = {r["name"] for r in import_symbols}

            imports_list = []
            for f in all_files:
                if f["path"] == path:
                    continue
                basename = os.path.basename(f["path"]).split(".")[0]
                # Check for direct import match or sub-import match
                if basename in import_names or any(name.endswith(f".{basename}") or name.startswith(f"{basename}.") for name in import_names):
                    imports_list.append(f["path"])

            imported_by_list = []
            basename_this = os.path.basename(path).split(".")[0]
            for f in all_files:
                if f["path"] == path:
                    continue
                imports_other = conn.execute("""
                    SELECT 1 FROM symbols
                    WHERE file_id = ? AND type = 'import' AND (name = ? OR name LIKE ? OR name LIKE ?);
                """, (f["id"], basename_this, f"%.{basename_this}", f"{basename_this}.%")).fetchone()
                if imports_other:
                    imported_by_list.append(f["path"])

            return {
                "imports": sorted(list(set(imports_list))),
                "imported_by": sorted(list(set(imported_by_list)))
            }

    def get_call_graph(self, function_name: str) -> dict[str, list[dict[str, Any]]]:
        """Finds functions called by the target function and functions calling it."""
        calls = []
        called_by = []

        with self.db._get_connection() as conn:
            func_rows = conn.execute("""
                SELECT s.*, f.path as file_path
                FROM symbols s
                JOIN files f ON s.file_id = f.id
                WHERE s.name = ? AND s.type = 'function';
            """, (function_name,)).fetchall()
            
            all_known_funcs = {r["name"] for r in conn.execute("SELECT name FROM symbols WHERE type = 'function';").fetchall()}

            for f_row in func_rows:
                ref_rows = conn.execute("""
                    SELECT symbol_name, line FROM symbol_references
                    WHERE file_id = ? AND line >= ? AND line <= ?;
                """, (f_row["file_id"], f_row["start_line"], f_row["end_line"])).fetchall()

                for r in ref_rows:
                    ref_name = r["symbol_name"]
                    if ref_name in all_known_funcs and ref_name != function_name:
                        def_file = conn.execute("""
                            SELECT f.path FROM symbols s
                            JOIN files f ON s.file_id = f.id
                            WHERE s.name = ? AND s.type = 'function' LIMIT 1;
                        """, (ref_name,)).fetchone()
                        calls.append({
                            "name": ref_name,
                            "file": def_file["path"] if def_file else "unknown",
                            "line": r["line"]
                        })

            all_func_defs = conn.execute("""
                SELECT s.*, f.path as file_path FROM symbols s
                JOIN files f ON s.file_id = f.id
                WHERE s.type = 'function';
            """).fetchall()

            for f_def in all_func_defs:
                if f_def["name"] == function_name:
                    continue
                called_ref = conn.execute("""
                    SELECT line FROM symbol_references
                    WHERE file_id = ? AND symbol_name = ? AND line >= ? AND line <= ? LIMIT 1;
                """, (f_def["file_id"], function_name, f_def["start_line"], f_def["end_line"])).fetchone()
                if called_ref:
                    called_by.append({
                        "name": f_def["name"],
                        "file": f_def["file_path"],
                        "line": called_ref["line"]
                    })

        dedup_calls = {f"{c['name']}:{c['file']}:{c['line']}": c for c in calls}
        dedup_called_by = {f"{c['name']}:{c['file']}:{c['line']}": c for c in called_by}
        return {
            "calls": sorted(list(dedup_calls.values()), key=lambda x: x["name"]),
            "called_by": sorted(list(dedup_called_by.values()), key=lambda x: x["name"])
        }

    def get_impact_analysis(self, symbol_name: str) -> dict[str, list[str]]:
        """Finds the transitive closure of all symbols and files depending directly or indirectly on the symbol."""
        affected_symbols: set[str] = set()
        affected_files: set[str] = set()
        visited: set[str] = set()

        def dfs(sym: str) -> None:
            if sym in visited:
                return
            visited.add(sym)

            with self.db._get_connection() as conn:
                def_rows = conn.execute("""
                    SELECT f.path FROM symbols s
                    JOIN files f ON s.file_id = f.id
                    WHERE s.name = ?;
                """, (sym,)).fetchall()
                for r in def_rows:
                    affected_files.add(r["path"])

                referencing_symbols = conn.execute("""
                    SELECT DISTINCT s.name, f.path as file_path
                    FROM symbols s
                    JOIN files f ON s.file_id = f.id
                    JOIN symbol_references r ON r.file_id = f.id
                    WHERE r.symbol_name = ? AND r.line >= s.start_line AND r.line <= s.end_line;
                """, (sym,)).fetchall()

                for ref in referencing_symbols:
                    ref_name = ref["name"]
                    if ref_name != sym:
                        affected_symbols.add(ref_name)
                        affected_files.add(ref["file_path"])
                        dfs(ref_name)

        dfs(symbol_name)
        return {
            "symbols": sorted(list(affected_symbols)),
            "files": sorted(list(affected_files))
        }

    def get_related_symbols(self, symbol_name: str) -> list[str]:
        """Finds classes, functions, or imports defined in the same file, or explicitly linked by usage."""
        related = set()
        with self.db._get_connection() as conn:
            file_rows = conn.execute("""
                SELECT file_id FROM symbols WHERE name = ?;
            """, (symbol_name,)).fetchall()

            for r in file_rows:
                fid = r["file_id"]
                siblings = conn.execute("SELECT name FROM symbols WHERE file_id = ?;", (fid,)).fetchall()
                for sib in siblings:
                    if sib["name"] != symbol_name:
                        related.add(sib["name"])

            for r in conn.execute("SELECT file_id, start_line, end_line FROM symbols WHERE name = ?;", (symbol_name,)).fetchall():
                refs = conn.execute("""
                    SELECT symbol_name FROM symbol_references
                    WHERE file_id = ? AND line >= ? AND line <= ?;
                """, (r["file_id"], r["start_line"], r["end_line"])).fetchall()
                for ref in refs:
                    if ref["symbol_name"] != symbol_name:
                        related.add(ref["symbol_name"])

        return sorted(list(related))

    # camelCase compatibility aliases
    def getDependencies(self, path: str) -> dict[str, list[str]]:
        return self.get_dependencies(path)

    def getCallGraph(self, function_name: str) -> dict[str, list[dict[str, Any]]]:
        return self.get_call_graph(function_name)

    def getImpactAnalysis(self, symbol_name: str) -> dict[str, list[str]]:
        return self.get_impact_analysis(symbol_name)

    def getRelatedSymbols(self, symbol_name: str) -> list[str]:
        return self.get_related_symbols(symbol_name)
