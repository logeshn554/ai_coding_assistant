"""
API Graph — Maps REST and WebSocket endpoints to controller methods and validation models.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger("devpilot.brain.api_graph")


@dataclass
class APIEndpoint:
    path: str
    method: str                         # GET | POST | PUT | DELETE | WEBSOCKET
    handler_func: str
    request_schema: Optional[str] = None
    response_schema: Optional[str] = None


class APIGraph:
    """Graph database matching endpoint URLs to application controllers."""

    def __init__(self) -> None:
        self.endpoints: Dict[str, APIEndpoint] = {}

    def register_endpoint(
        self,
        path: str,
        method: str,
        handler_func: str,
        req_schema: Optional[str] = None,
        resp_schema: Optional[str] = None,
    ) -> None:
        key = f"{method}:{path}"
        self.endpoints[key] = APIEndpoint(
            path=path,
            method=method,
            handler_func=handler_func,
            request_schema=req_schema,
            response_schema=resp_schema,
        )
        logger.debug(f"Registered API endpoint in brain index: {key} -> {handler_func}")

    def find_handler(self, method: str, path: str) -> Optional[APIEndpoint]:
        """Lookup endpoint handler function by HTTP path and method."""
        key = f"{method}:{path}"
        return self.endpoints.get(key)

    def get_endpoints(self) -> List[APIEndpoint]:
        return list(self.endpoints.values())


# ── Singleton ───────────────────────────────────────────────────────────────

api_graph = APIGraph()
