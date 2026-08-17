"""Web Fetch tool â€“ retrieve any URL and return clean readable text.

Exposes ``web_fetch(session, args)`` as the agent-facing async function.

Primary:  Tavily Extract API â€“ purpose-built for structured web content
          extraction (same key as web search).
Fallback: Raw ``httpx`` request + HTML strip when Tavily is unavailable or
          the key is not configured.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

logger = logging.getLogger("loopix.tools.web_fetch")

MAX_CHARS = 40000   # Cap response to avoid flooding context
REQUEST_TIMEOUT = 20  # seconds for raw httpx fallback


# ---------------------------------------------------------------------------
# HTML stripping helper (used only in the httpx fallback path)
# ---------------------------------------------------------------------------

def _strip_html(html: str) -> str:
    """Basic HTML â†’ plaintext conversion."""
    html = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<[^>]+>", " ", html)
    html = html.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    html = html.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
    html = re.sub(r"[ \t]+", " ", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


# ---------------------------------------------------------------------------
# Primary: Tavily Extract
# ---------------------------------------------------------------------------

async def _fetch_via_tavily(url: str, api_key: str) -> str:
    """Use Tavily's extract endpoint to pull clean text from a URL.

    Tries the ``tavily-python`` SDK first; falls back to a direct HTTPS
    POST if the package is not installed.
    """
    import asyncio

    def _sync_extract() -> str:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=api_key)
            # extract() returns {"results": [{"url": ..., "raw_content": ...}]}
            response = client.extract(urls=[url])
            results = response.get("results", [])
            if results:
                return results[0].get("raw_content") or results[0].get("content") or ""
            failed = response.get("failed_results", [])
            if failed:
                raise ValueError(f"Tavily could not extract content from '{url}': {failed[0].get('error','unknown error')}")
            return ""
        except ImportError:
            # SDK not installed - fall back to direct HTTP
            import httpx
            payload = {"api_key": api_key, "urls": [url]}
            resp = httpx.post(
                "https://api.tavily.com/extract",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=REQUEST_TIMEOUT,
            )
            data = resp.json()
            results = data.get("results", [])
            if results:
                return results[0].get("raw_content") or results[0].get("content") or ""
            return ""

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_extract)


# ---------------------------------------------------------------------------
# Fallback: raw httpx fetch + HTML strip
# ---------------------------------------------------------------------------

async def _fetch_via_httpx(url: str) -> str:
    """Fallback: fetch URL via httpx and strip HTML tags."""
    try:
        import httpx
    except ImportError:
        raise RuntimeError(
            "Neither Tavily API key nor 'httpx' is available. "
            "Configure TAVILY_API_KEY or run: pip install httpx"
        )

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Loopix/1.0)",
        "Accept": "text/html,text/plain;q=0.9,*/*;q=0.8",
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=REQUEST_TIMEOUT, headers=headers) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        raw = resp.text

    if "html" in content_type.lower():
        return _strip_html(raw)
    return raw


# ---------------------------------------------------------------------------
# Public tool function
# ---------------------------------------------------------------------------

async def web_fetch(session: Any, args: dict[str, Any]) -> str:
    """Fetch a URL and return its content as readable text.

    Uses Tavily Extract as the primary engine (same API key as web search).
    Falls back to a raw HTTP request + HTML stripping when Tavily is
    unavailable or the API key is not configured.

    Args:
        session: Active AgentSession (unused, kept for API consistency).
        args:
            url (str, required): Full URL to fetch (must start with http/https).
            max_chars (int, optional): Max characters to return (default/max 40000).

    Returns:
        Cleaned text content of the page, or an error message.
    """
    url: str = (args.get("url") or "").strip()
    if not url:
        return "Error: 'url' argument is required for web_fetch."
    if not (url.startswith("http://") or url.startswith("https://")):
        return "Error: URL must start with http:// or https://"

    max_chars: int = min(int(args.get("max_chars") or MAX_CHARS), MAX_CHARS)

    # Resolve Tavily API key from config or environment
    try:
        from ..state import config_manager
        api_key: str = (config_manager.get_tavily_api_key() or "").strip()
    except Exception:
        api_key = ""
    if not api_key:
        api_key = os.environ.get("TAVILY_API_KEY", "").strip()

    # --- Primary: Tavily Extract ---
    if api_key:
        try:
            logger.info("web_fetch: using Tavily extract for '%s'", url)
            text = await _fetch_via_tavily(url, api_key)
            if text:
                if len(text) > max_chars:
                    text = text[:max_chars] + f"\n\n[Content truncated at {max_chars} chars.]"
                return f"## Content from {url} (via Tavily)\n\n{text}"
            logger.warning("web_fetch: Tavily returned empty content for '%s', falling back to httpx", url)
        except Exception as exc:
            logger.warning("web_fetch: Tavily extract failed for '%s': %s â€“ falling back to httpx", url, exc)

    # --- Fallback: raw httpx ---
    try:
        logger.info("web_fetch: using httpx fallback for '%s'", url)
        text = await _fetch_via_httpx(url)
    except Exception as exc:
        return f"Error fetching '{url}': {exc}"

    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n[Content truncated at {max_chars} chars.]"

    source_note = "" if api_key else " (Tavily key not configured â€“ using raw fetch)"
    return f"## Content from {url}{source_note}\n\n{text}"
