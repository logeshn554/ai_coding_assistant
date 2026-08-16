"""Tavily web search tool for recurring error fallback.

Uses Tavily API (tavily-python) to search the web for solutions to recurring errors.
Reads `tavily_api_key` from config_manager or TAVILY_API_KEY environment variable.
Fails gracefully with empty result list if key is missing or search fails.
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from ..state import config_manager

logger = logging.getLogger("devpilot.tools.web_search")


@dataclass
class SearchResult:
    """Structured result of a Tavily web search query."""

    title: str
    url: str
    snippet: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


async def search_web(query: str, max_results: int = 5) -> List[SearchResult]:
    """Execute a web search using Tavily API for the given query.

    Args:
        query: Cleaned search query string (e.g. normalized error message).
        max_results: Maximum number of search results to return.

    Returns:
        List of SearchResult objects. If API key is missing or search fails,
        returns an empty list.
    """
    if not query or not query.strip():
        return []

    api_key = config_manager.get_tavily_api_key().strip() or os.environ.get("TAVILY_API_KEY", "").strip()

    if not api_key:
        logger.warning("Tavily web search: TAVILY_API_KEY not configured. Skipping search.")
        return []

    try:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=api_key)
            response = client.search(query=query, max_results=max_results)
            raw_results = response.get("results", [])
        except ImportError:
            # Fallback to direct HTTP request if tavily-python is not installed
            import httpx

            req_payload = {
                "api_key": api_key,
                "query": query,
                "max_results": max_results
            }

            resp = httpx.post(
                "https://api.tavily.com/search",
                json=req_payload,
                headers={"Content-Type": "application/json"},
                timeout=10.0
            )
            data = resp.json()
            raw_results = data.get("results", [])

        results: List[SearchResult] = []
        for item in raw_results:
            results.append(
                SearchResult(
                    title=item.get("title", "Search Result"),
                    url=item.get("url", ""),
                    snippet=item.get("content", item.get("snippet", "")),
                )
            )

        logger.info("Tavily web search: Found %d results for query '%s'", len(results), query[:50])
        return results
    except Exception as exc:
        logger.warning("Tavily web search failed for query '%s': %s. Returning empty fallback.", query[:50], exc)
        return []
