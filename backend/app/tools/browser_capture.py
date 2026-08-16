"""BrowserCapture: Headless browser automation for dev server page inspection & QA.

Uses Playwright (async API) to navigate to a local dev server URL, listen to console
logs and network responses, capture failed requests, take a full-page screenshot,
and return a structured CaptureResult dataclass.

Guardrails:
- Hard-blocks any non-localhost / non-127.0.0.1 URLs.
- Enforces a 10-second navigation timeout to prevent hanging on open socket streams.
- Caps console and network log entries before returning to protect context window size.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger("devpilot.tools.browser_capture")


@dataclass
class CaptureResult:
    """Structured result of browser visual and runtime QA capture."""

    screenshot_path: str
    console_messages: List[Dict[str, Any]] = field(default_factory=list)
    network_requests: List[Dict[str, Any]] = field(default_factory=list)
    failed_requests: List[Dict[str, Any]] = field(default_factory=list)
    page_title: str = ""
    final_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def is_localhost_url(url: str) -> bool:
    """Return True if url targets a local dev server (localhost, 127.0.0.1, ::1).

    Raises:
        ValueError: If url is not a valid http(s) URL or points outside localhost.
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string.")

    # Prepend scheme if missing
    if not url.startswith(("http://", "https://")):
        url = "http://" + url

    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()

    allowed_hosts = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}  # nosec B104
    if hostname not in allowed_hosts:
        raise ValueError(
            f"Access denied: auto-inspection is restricted to local dev servers "
            f"(localhost / 127.0.0.1). Provided URL: '{url}'"
        )
    return True


def get_artifacts_dir(workspace_root: Optional[str] = None) -> str:
    """Resolve artifacts directory for storing QA screenshots."""
    if workspace_root and os.path.isdir(workspace_root):
        target = os.path.join(workspace_root, "artifacts")
    else:
        target = os.path.join(os.path.expanduser("~"), ".devpilot", "artifacts")

    os.makedirs(target, exist_ok=True)
    return target


def get_async_playwright():
    """Retrieve async_playwright context manager from playwright library."""
    try:
        from playwright.async_api import async_playwright
        return async_playwright
    except ImportError as err:
        logger.error("Playwright package not installed: %s", err)
        raise RuntimeError(
            "Playwright is not installed. Please install it via `pip install playwright` "
            "and `playwright install chromium`."
        ) from err


async def capture_page(
    url: str,
    workspace_root: str = "",
    max_log_entries: int = 50,
    timeout_ms: int = 10000,
) -> CaptureResult:
    """Navigate to a local dev server URL, record console/network QA data, and take a screenshot.

    Args:
        url: Dev server URL (must be localhost or 127.0.0.1).
        workspace_root: Path to workspace root for saving screenshot artifact.
        max_log_entries: Maximum number of console/network logs to keep.
        timeout_ms: Maximum wait time for page navigation (default 10,000ms).

    Returns:
        Structured CaptureResult object.

    Raises:
        ValueError: If url is non-localhost.
        RuntimeError: If Playwright fails to launch.
    """
    # Guardrail check
    is_localhost_url(url)

    async_pw_fn = get_async_playwright()

    console_messages: List[Dict[str, Any]] = []
    network_requests: List[Dict[str, Any]] = []
    failed_requests: List[Dict[str, Any]] = []
    page_title = ""
    final_url = url
    screenshot_path = ""

    artifacts_dir = get_artifacts_dir(workspace_root)
    timestamp = int(time.time())
    screenshot_file = os.path.join(artifacts_dir, f"qa_screenshot_{timestamp}.png")

    async with async_pw_fn() as p:
        try:
            browser = await p.chromium.launch(headless=True)
        except Exception as exc:
            logger.error("Failed to launch headless Chromium: %s", exc)
            raise RuntimeError(f"Playwright browser launch failed: {exc}") from exc

        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            ignore_https_errors=True,
        )
        page = await context.new_page()

        # Listen to console events
        def on_console(msg):
            console_messages.append({
                "type": msg.type,
                "text": msg.text,
                "location": {
                    "url": msg.location.get("url", ""),
                    "line_number": msg.location.get("lineNumber", 0),
                    "column_number": msg.location.get("columnNumber", 0),
                } if msg.location else {},
            })

        # Listen to network response events
        def on_response(response):
            req = response.request
            entry = {
                "url": response.url,
                "method": req.method,
                "status": response.status,
                "status_text": response.status_text,
            }
            network_requests.append(entry)
            if response.status >= 400:
                failed_requests.append(entry)

        # Listen to failed request events (e.g. connection refused, CORS errors)
        def on_request_failed(request):
            entry = {
                "url": request.url,
                "method": request.method,
                "status": 0,
                "failure": request.failure or "Failed / Network Error",
            }
            failed_requests.append(entry)
            network_requests.append(entry)

        page.on("console", on_console)
        page.on("response", on_response)
        page.on("requestfailed", on_request_failed)

        # Navigate with networkidle or fallback timeout
        try:
            await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        except Exception as nav_err:
            logger.warning("Page goto timed out or partially loaded: %s", nav_err)
            # Try waiting for domcontentloaded if networkidle timed out
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=3000)
            except Exception:
                pass

        try:
            page_title = await page.title()
        except Exception:
            page_title = "Local Dev Server Preview"

        try:
            final_url = page.url
        except Exception:
            final_url = url

        # Take full-page screenshot
        try:
            await page.screenshot(path=screenshot_file, full_page=True)
            screenshot_path = screenshot_file
        except Exception as ss_err:
            logger.error("Screenshot capture failed: %s", ss_err)
            screenshot_path = ""

        await context.close()
        await browser.close()

    # Priority sort console messages: errors first, then warnings, then info
    priority_order = {"error": 0, "warning": 1, "warn": 1, "info": 2, "log": 3}
    console_messages.sort(key=lambda m: priority_order.get(m.get("type", "").lower(), 4))

    # Cap log size to protect context window
    console_messages = console_messages[:max_log_entries]
    network_requests = network_requests[:max_log_entries]
    failed_requests = failed_requests[:max_log_entries]

    return CaptureResult(
        screenshot_path=screenshot_path,
        console_messages=console_messages,
        network_requests=network_requests,
        failed_requests=failed_requests,
        page_title=page_title,
        final_url=final_url,
    )
