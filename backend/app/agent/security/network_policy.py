"""
Network Policy Engine — Step 17 requirement.

Enforces network access modes (BLOCKED, ALLOWLIST, FULL) and validates outbound requests
against configured domain allowlists.
"""

from __future__ import annotations

from enum import Enum
from typing import Set, Tuple
from urllib.parse import urlparse


class NetworkMode(str, Enum):
    BLOCKED = "BLOCKED"
    ALLOWLIST = "ALLOWLIST"
    FULL = "FULL"


# Default domain allowlist for software development dependencies
DEFAULT_ALLOWLIST: Set[str] = {
    "pypi.org", "files.pythonhosted.org", "registry.npmjs.org",
    "github.com", "raw.githubusercontent.com", "crates.io", "proxy.golang.org",
}


class NetworkPolicyEngine:
    """Validates outbound network domain requests against safety policies."""

    def __init__(self, mode: NetworkMode = NetworkMode.ALLOWLIST, allowlist: Optional[Set[str]] = None) -> None:
        self.mode = mode
        self.allowlist = allowlist or DEFAULT_ALLOWLIST

    def is_url_allowed(self, url: str) -> Tuple[bool, str]:
        """Check if an outbound network URL is authorized under policy."""
        if self.mode == NetworkMode.FULL:
            return True, "Full network access permitted"

        if self.mode == NetworkMode.BLOCKED:
            return False, "Network access is BLOCKED by policy"

        try:
            parsed = urlparse(url)
            hostname = parsed.hostname or url.split("/")[0].split(":")[0]
            hostname_lower = hostname.lower()

            for allowed in self.allowlist:
                if hostname_lower == allowed.lower() or hostname_lower.endswith("." + allowed.lower()):
                    return True, f"Domain '{hostname}' allowed by policy allowlist"

            return False, f"Outbound domain '{hostname}' is not in network allowlist"
        except Exception as e:
            return False, f"Invalid URL format: {e}"
