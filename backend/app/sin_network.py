from __future__ import annotations

import hashlib
import logging
import os
from typing import Any

logger = logging.getLogger("loopix.sin_network")

_STUB_WARNING = (
    "SoftwareIntelligenceNetwork is returning SIMULATED stub data. "
    "This module is not yet connected to real symbol graphs or cross-repo analysis."
)


class SoftwareIntelligenceNetwork:
    """SIN engine bridging stubs with real AST workspace graph metadata."""

    def query_global_intelligence(self, symbol_query: str) -> dict[str, Any]:
        """Search global code intelligence (STUB — not yet implemented)."""
        logger.warning(_STUB_WARNING)
        return {
            "implemented": False,
            "stub_note": "Real symbol graph traversal is not yet implemented.",
            "query": symbol_query,
            "matched_symbols": [],
            "cross_repo_links": [],
        }

    def get_engineering_genome(self, workspace_root: str = "") -> dict[str, Any]:
        """Extract engineering genome profile dynamically using build_workspace_graph."""
        if not workspace_root or not os.path.isdir(workspace_root):
            logger.warning(_STUB_WARNING)
            return {
                "implemented": False,
                "stub_note": "Real engineering genome extraction is not yet implemented.",
                "genome_id": None,
                "architecture_style": None,
                "primary_stack": [],
                "workspace_root": workspace_root,
            }

        # Perform actual architecture / stack analysis using the built graph
        from .workspace_graph import build_workspace_graph
        try:
            graph = build_workspace_graph(workspace_root)
            nodes = graph.get("nodes", [])
            node_types = [n.get("type") for n in nodes]
            api_count = node_types.count("api")
            db_count = node_types.count("database")
            comp_count = node_types.count("component")

            # Infer architecture style from AST categorization counts
            style = "Modular Monolith"
            if api_count > 5:
                style = "Microservices / API-driven"
            elif comp_count > 10:
                style = "Component-based Web App"

            # Detect stack from node file paths
            stack = set()
            for n in nodes:
                path = n.get("path", "")
                if path.endswith(".py"):
                    stack.add("Python")
                elif path.endswith(".ts") or path.endswith(".tsx"):
                    stack.add("TypeScript")
                elif path.endswith(".js") or path.endswith(".jsx"):
                    stack.add("JavaScript")

            return {
                "implemented": True,
                "genome_id": hashlib.sha256(workspace_root.encode("utf-8")).hexdigest()[:12],
                "architecture_style": style,
                "primary_stack": list(stack),
                "workspace_root": workspace_root,
                "stats": {
                    "total_files": len(nodes),
                    "apis": api_count,
                    "databases": db_count,
                    "components": comp_count
                }
            }
        except Exception as e:
            logger.error(f"Genome extraction failed: {e}")
            return {
                "implemented": False,
                "error": str(e),
                "workspace_root": workspace_root
            }

    def evaluate_ai_quality_score(self, diff_code: str) -> dict[str, Any]:
        """Evaluate AI-generated code quality (STUB — not yet implemented)."""
        logger.warning(_STUB_WARNING)
        return {
            "implemented": False,
            "stub_note": (
                "Real AI code quality scoring is not yet implemented. "
                "Do not use this verdict for merge decisions."
            ),
            "quality_score": None,
            "verdict": "STUB_ONLY — not production analysis",
        }


sin_network = SoftwareIntelligenceNetwork()
