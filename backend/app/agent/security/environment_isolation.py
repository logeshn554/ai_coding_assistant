"""
Environment Isolation Engine — Step 11 requirement.

Filters host process environment variables to prevent host secret leaks
to child subprocesses or model context.
"""

from __future__ import annotations

import os
from typing import Dict, Set

# Safe environment variables permitted for subprocess execution
SAFE_ENV_VARS: Set[str] = {
    "PATH", "HOME", "USER", "USERNAME", "LANG", "LC_ALL", "TERM",
    "PYTHONPATH", "NODE_ENV", "TEMP", "TMP", "SYSTEMROOT", "COMSPEC",
    "PWD", "SHELL", "VIRTUAL_ENV",
}

# Explicitly blocked secret environment variables
BLOCKED_ENV_PATTERNS: Set[str] = {
    "SECRET", "TOKEN", "PASSWORD", "KEY", "CREDENTIAL", "AUTH",
    "AWS", "GITHUB", "OPENAI", "ANTHROPIC", "AZURE",
}


class EnvironmentIsolation:
    """Filters host environment variables for child processes."""

    @classmethod
    def get_isolated_env(cls, extra_vars: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Produce an isolated environment dict free of host secrets."""
        isolated = {}
        for k, v in os.environ.items():
            k_upper = k.upper()

            # Allow if in safe list and not matching blocked pattern
            if k in SAFE_ENV_VARS or k_upper in SAFE_ENV_VARS:
                if not any(blk in k_upper for blk in BLOCKED_ENV_PATTERNS):
                    isolated[k] = v

        if extra_vars:
            for k, v in extra_vars.items():
                if not any(blk in k.upper() for blk in BLOCKED_ENV_PATTERNS):
                    isolated[k] = v

        return isolated
