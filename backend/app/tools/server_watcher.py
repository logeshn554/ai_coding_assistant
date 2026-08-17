"""ServerWatcher: Auto-detect running dev server from terminal output / ports.

Monitors terminal stdout for 'server ready' patterns (e.g. Local:, Listening on,
Uvicorn running, webpack compiled, ready in), debounces detections per URL,
and emits WebSocket events (`server_detected`) to clients.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any

from ..state import config_manager

logger = logging.getLogger("loopix.tools.server_watcher")

# Common dev server ready regex patterns
SERVER_READY_PATTERNS: list[re.Pattern] = [
    re.compile(r"https?://localhost:\d+", re.IGNORECASE),
    re.compile(r"https?://127\.0\.0\.1:\d+", re.IGNORECASE),
    re.compile(r"https?://\[::1\]:\d+", re.IGNORECASE),
    re.compile(r"\bLocal:\s+https?://\S+", re.IGNORECASE),
    re.compile(r"\bUvicorn running on\s+https?://\S+", re.IGNORECASE),
    re.compile(r"\b(webpack|vite|next|nuxt|astro|svelte|angular).*compiled", re.IGNORECASE),
    re.compile(r"\bready in\s+\d+", re.IGNORECASE),
    re.compile(r"\b(Listening|Serving) on\s+https?://\S+", re.IGNORECASE),
    re.compile(r"\bServer started on port\s+\d+", re.IGNORECASE),
]

# Standard dev server ports
COMMON_DEV_PORTS: list[int] = [3000, 5173, 8000, 8080, 4200, 5000, 5500, 8081]


class ServerWatcher:
    """Detects dev servers from stdout streams with debouncing and WS notification."""

    def __init__(self, debounce_interval: float = 15.0):
        self.debounce_interval = debounce_interval
        # Stores url -> timestamp of last detection
        self._detected_urls: dict[str, float] = {}

    def reset(self):
        """Clear detection history."""
        self._detected_urls.clear()

    def extract_url(self, line: str, default_port: int = 5173) -> str | None:
        """Extract a valid localhost URL from a log line, or construct one if matched."""
        # 1. Direct URL match
        url_match = re.search(r"https?://(?:localhost|127\.0\.0\.1|\[::1\]):\d+[/\w.-]*", line, re.IGNORECASE)
        if url_match:
            return url_match.group(0).rstrip("/")

        # 2. Port match (e.g. "port 3000", "running on :8000")
        port_match = re.search(r"\b(?:port|on)\s*:?\s*(\d{4,5})\b", line, re.IGNORECASE)
        if port_match:
            port = int(port_match.group(1))
            return f"http://localhost:{port}"

        # 3. Keyword match with default port fallback
        for pattern in SERVER_READY_PATTERNS:
            if pattern.search(line):
                return f"http://localhost:{default_port}"

        return None

    def check_log_line(self, line: str, session: Any = None) -> str | None:
        """Check a terminal log line for dev server activation.

        Returns detected URL if a NEW (non-debounced) server was found, else None.
        """
        if not line or not line.strip():
            return None

        url = self.extract_url(line)
        if not url:
            return None

        now = time.time()
        last_time = self._detected_urls.get(url, 0.0)

        # Debounce: skip if detected within debounce_interval
        if now - last_time < self.debounce_interval:
            logger.debug("ServerWatcher: debounced repeat url '%s'", url)
            return None

        self._detected_urls[url] = now
        logger.info("ServerWatcher: detected server running at '%s'", url)

        # Check opt-in setting gate
        auto_inspect_enabled = config_manager.get_auto_inspect_on_server_start()

        # Emit WebSocket event if session is available
        if session and hasattr(session, "send_ws_message"):
            evt = {
                "type": "server_detected",
                "url": url,
                "auto_inspect": auto_inspect_enabled,
                "timestamp": now,
            }
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(session.send_ws_message(evt))
            except RuntimeError:
                try:
                    res = session.send_ws_message(evt)
                    if asyncio.iscoroutine(res):
                        res.close()
                except Exception:
                    pass

        return url


# Global singleton instance
global_server_watcher = ServerWatcher()
