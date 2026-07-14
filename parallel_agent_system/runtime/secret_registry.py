import os

class SecretRegistry:
    """Manages secure resolution of API keys and credentials."""
    
    _secrets: dict[str, str] = {}

    @classmethod
    def get(cls, key: str) -> str:
        """Retrieves a secret, falling back to environment variables."""
        return cls._secrets.get(key) or os.environ.get(key) or ""

    @classmethod
    def register(cls, key: str, value: str) -> None:
        """Registers a secret value dynamically."""
        cls._secrets[key] = value
