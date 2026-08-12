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
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),  # GitHub Token
    re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}"),  # JWT Token
    re.compile(r"-----\s*BEGIN\s+PRIVATE\s+KEY\s*-----[\s\S]*?-----\s*END\s+PRIVATE\s+KEY\s*-----"),  # RSA/PEM Key
    re.compile(r"(?:api_key|apikey|secret_key|private_key|password|passwd|token)\s*[:=]\s*[\"']?([A-Za-z0-9_\-\.\/]{8,})[\"']?", re.IGNORECASE),
    re.compile(r"postgres://[^:]+:([^@]+)@"),  # Database URL password
]

# Sensitive file patterns
PROTECTED_SECRET_FILES: Set[str] = {
    ".env", ".env.local", ".env.production", "secret.pem", "id_rsa", "id_ed25519", "credentials.json"
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
        if filename in PROTECTED_SECRET_FILES or filename.startswith(".env"):
            return True
        ext = os.path.splitext(filename)[1].lower()
        if ext in (".pem", ".key", ".p12", ".pkcs12"):
            return True
        return False
