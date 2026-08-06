"""
Symbol Merge — Performs AST-aware merging of python symbols to prevent syntactic breakage.
"""
from __future__ import annotations

import ast
import logging
from typing import Dict, List

logger = logging.getLogger("devpilot.merge.symbol_merge")


class SymbolMerge:
    """AST symbol-based merge tool that prevents textual collisions on formatting changes."""

    def merge_class_definition(self, original_code: str, proposed_code: str, target_class: str) -> str:
        """Merge a specific class definition from proposed_code into original_code using AST substitution."""
        try:
            orig_tree = ast.parse(original_code)
            prop_tree = ast.parse(proposed_code)

            # Heuristic parser extraction
            orig_lines = original_code.splitlines()
            prop_lines = proposed_code.splitlines()

            # Find line ranges
            orig_range = self._find_class_range(orig_tree, target_class)
            prop_range = self._find_class_range(prop_tree, target_class)

            if orig_range and prop_range:
                o_start, o_end = orig_range
                p_start, p_end = prop_range

                # Replace class definition
                merged_lines = orig_lines[:o_start] + prop_lines[p_start:p_end] + orig_lines[o_end:]
                logger.info(f"Successfully merged AST node class '{target_class}' using structural ranges.")
                return "\n".join(merged_lines)

        except Exception as e:
            logger.error(f"Failed to merge AST for class '{target_class}': {e}")
        
        # Textual fallback
        return proposed_code

    def _find_class_range(self, tree: ast.AST, class_name: str) -> Optional[Tuple[int, int]]:
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                # 1-indexed to 0-indexed adjustment
                start = node.lineno - 1
                end = node.end_lineno if hasattr(node, "end_lineno") else node.lineno
                return (start, end)
        return None


# ── Singleton ───────────────────────────────────────────────────────────────

symbol_merge = SymbolMerge()
