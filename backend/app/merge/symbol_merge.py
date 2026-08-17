"""
Symbol Merge — AST-aware merging for Python source files to avoid duplicate definitions.
"""

from __future__ import annotations

import ast
import logging

logger = logging.getLogger("loopix.merge.symbol_merge")


class SymbolMerger:
    """AST-aware code merger."""

    @staticmethod
    def merge_python_sources(base_code: str, patch_code: str) -> str:
        """Merge new/updated AST top-level function/class definitions into base code."""
        try:
            base_tree = ast.parse(base_code)
            patch_tree = ast.parse(patch_code)
        except Exception as e:
            logger.warning(f"AST parse failed during symbol merge: {e}. Falling back to string append.")
            return base_code.strip() + "\n\n" + patch_code.strip()

        patch_funcs = {
            node.name: node
            for node in patch_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }

        if not patch_funcs:
            return base_code.strip() + "\n\n" + patch_code.strip()

        # Re-build base body by replacing definitions that exist in patch
        new_body = []
        replaced_names = set()

        for node in base_tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in patch_funcs:
                new_body.append(patch_funcs[node.name])
                replaced_names.add(node.name)
            else:
                new_body.append(node)

        # Append new patch functions not found in base
        for name, node in patch_funcs.items():
            if name not in replaced_names:
                new_body.append(node)

        base_tree.body = new_body
        try:
            return ast.unparse(base_tree)
        except Exception:
            return base_code.strip() + "\n\n" + patch_code.strip()


symbol_merger = SymbolMerger()
