from __future__ import annotations

import os

# Safe environment variables permitted for subprocess execution
SAFE_ENV_VARS: set[str] = {
    "PATH", "HOME", "USER", "USERNAME", "LANG", "LC_ALL", "TERM",
    "PYTHONPATH", "NODE_ENV", "TEMP", "TMP", "SYSTEMROOT", "COMSPEC",
    "PWD", "SHELL", "VIRTUAL_ENV", "CI", "npm_config_yes",
    "SYSTEMDRIVE", "WINDIR", "USERPROFILE", "LOCALAPPDATA", "APPDATA",
    "COMMONPROGRAMFILES", "PROGRAMFILES", "PROGRAMFILES(X86)", "PUBLIC",
    "ALLUSERSPROFILE", "OS", "PATHEXT", "COMPUTERNAME"
}

# Explicitly blocked secret environment variables
BLOCKED_ENV_PATTERNS: set[str] = {
    "SECRET", "TOKEN", "PASSWORD", "KEY", "CREDENTIAL", "AUTH",
    "AWS", "GITHUB", "OPENAI", "ANTHROPIC", "AZURE", "PRIVATE", "SIGNING"
}


class EnvironmentIsolation:
    """Filters host environment variables for child processes."""

    @classmethod
    def get_isolated_env(cls, extra_vars: dict[str, str] | None = None) -> dict[str, str]:
        """Produce an isolated environment dict free of host secrets."""
        isolated = {}
        for k, v in os.environ.items():
            k_upper = k.upper()

            # Allow if in safe list and not matching blocked pattern
            if k in SAFE_ENV_VARS or k_upper in SAFE_ENV_VARS:
                if not any(blk in k_upper for blk in BLOCKED_ENV_PATTERNS):
                    isolated[k] = v

        if extra_vars and isinstance(extra_vars, dict):
            for k, v in extra_vars.items():
                k_upper = k.upper()
                if not any(blk in k_upper for blk in BLOCKED_ENV_PATTERNS):
                    isolated[k] = str(v)

        return isolated
