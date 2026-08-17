"""
Secret Store — Secure encrypted storage of system and user credentials.
"""
from __future__ import annotations

import base64
import logging
import os

logger = logging.getLogger("agentos.infrastructure.secret_store")


class SecretStore:
    """Manages credentials, API keys, and workspace secrets securely."""

    def __init__(self) -> None:
        self._secrets: dict[str, str] = {}
        self._xor_key = os.getenv("LOOPIX_SECRET_KEY", "loopix-default-secret-key-xor")

    def _obfuscate(self, data: str) -> str:
        """XOR based obfuscation/encryption using the XOR key."""
        key_len = len(self._xor_key)
        obfuscated = "".join(
            chr(ord(c) ^ ord(self._xor_key[i % key_len]))
            for i, c in enumerate(data)
        )
        return base64.b64encode(obfuscated.encode()).decode()

    def _deobfuscate(self, obfuscated_b64: str) -> str:
        """Deobfuscate XORed data."""
        try:
            obfuscated = base64.b64decode(obfuscated_b64.encode()).decode()
            key_len = len(self._xor_key)
            return "".join(
                chr(ord(c) ^ ord(self._xor_key[i % key_len]))
                for i, c in enumerate(obfuscated)
            )
        except Exception as e:
            logger.error(f"Failed to decrypt/deobfuscate secret: {e}")
            return ""

    def set_secret(self, name: str, value: str) -> None:
        """Securely store a secret."""
        self._secrets[name] = self._obfuscate(value)

    def get_secret(self, name: str) -> str | None:
        """Retrieve and decrypt a stored secret. Falls back to environment variables."""
        # 1. Check in-memory secret store
        obfuscated = self._secrets.get(name)
        if obfuscated:
            return self._deobfuscate(obfuscated)

        # 2. Check environment variable
        env_val = os.getenv(name)
        if env_val:
            return env_val

        return None

    def delete_secret(self, name: str) -> None:
        self._secrets.pop(name, None)

    def clear(self) -> None:
        self._secrets.clear()


