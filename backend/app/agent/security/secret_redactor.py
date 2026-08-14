"""
Secret Detection & Output Redactor — Step 9, 10 requirements.

Scans text and tool outputs for sensitive credentials (API keys, JWTs, private keys,
passwords, cloud secrets) and replaces them with [REDACTED].
Denies access to protected secret files (.env, .pem, .key, id_rsa, etc.).
"""

from __future__ import annotations

import os
import re
from typing import List, Set

# Regex patterns matching secrets
SECRET_PATTERNS: List[re.Pattern] = [
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS Access Key ID
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),  # GitHub Personal Access Token
    re.compile(r"gho_[a-zA-Z0-9]{36}"),  # GitHub OAuth Token
    re.compile(r"glpat-[a-zA-Z0-9\-=_]{20,32}"),  # GitLab Personal Access Token
    re.compile(r"xox[baprs]-[0-9a-zA-Z]{10,48}"),  # Slack Token
    re.compile(r"sk-[a-zA-Z0-9]{32,64}"),  # OpenAI API Key
    re.compile(r"sk-ant-[a-zA-Z0-9_\-]{32,128}"),  # Anthropic API Key
    re.compile(r"AIza[0-9A-Za-z-_]{35}"),  # Google API Key
    re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}"),  # JWT Token
    re.compile(r"-----\s*BEGIN\s+(?:RSA|DSA|EC|OPENSSH|PGP|ENCRYPTED)?\s*PRIVATE\s+KEY\s*-----[\s\S]*?-----\s*END\s+(?:RSA|DSA|EC|OPENSSH|PGP|ENCRYPTED)?\s*PRIVATE\s+KEY\s*-----"),
    re.compile(r"(?:api_key|apikey|secret_key|private_key|password|passwd|token|auth_token)\s*[:=]\s*[\"']?([A-Za-z0-9_\-\.\/]{8,})[\"']?", re.IGNORECASE),
    re.compile(r"(?:postgres|postgresql|mysql|mongodb|redis|amqp):\/\/[^:]+:([^@]+)@"),  # DB connection string password
]

# Sensitive file patterns
PROTECTED_SECRET_FILES: Set[str] = {
    ".env", ".env.local", ".env.production", ".env.development", "secret.pem", "id_rsa", "id_ed25519", "credentials.json", "service_account.json"
}


class SecretRedactor:
    """Detects secrets and redacts them from string outputs."""

    @classmethod
    def redact_secrets(cls, text: str) -> str:
        """Replace all detected secret patterns with [REDACTED]."""
        if not text or not isinstance(text, str):
            return text

        redacted = text
        for pattern in SECRET_PATTERNS:
            redacted = pattern.sub("[REDACTED]", redacted)

        return redacted

    @classmethod
    def is_secret_file(cls, relative_path: str) -> bool:
        """Check if a file path is a protected secret file."""
        filename = os.path.basename(relative_path.replace("\\", "/")).strip("/")
        if filename in (".env.example", "env.example"):
            return False
        if filename in {".env", ".env.local", ".env.development", ".env.production", ".env.test"} or (filename.startswith(".env") and not filename.endswith(".example")):
            return True
        ext = os.path.splitext(filename)[1].lower()
        if ext in (".pem", ".key", ".p12", ".pkcs12"):
            return True
        return False
