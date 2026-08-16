"""
Gateway Auth — Unified authentication middleware for the Agentic OS.

Supports:
  - JWT bearer tokens (session auth)
  - API key authentication (programmatic access)
  - WebSocket token validation (real-time channels)
  - Multi-tenant isolation via tenant context
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("agentos.gateway.auth")

# Import centralized settings — single source of truth for JWT secret and environment
# Imported lazily inside classes to avoid circular import at module load time.



# ── Data Models ─────────────────────────────────────────────────────────────

class AuthMethod(str, Enum):
    JWT = "jwt"
    API_KEY = "api_key"
    WEBSOCKET_TOKEN = "websocket_token"
    ANONYMOUS = "anonymous"


@dataclass
class TenantContext:
    """Isolation context for multi-tenant deployments."""
    tenant_id: str
    org_name: str = ""
    tier: str = "free"                # free | pro | enterprise
    rate_limit_multiplier: float = 1.0
    allowed_models: list[str] = field(default_factory=list)
    max_concurrent_sessions: int = 5
    sandbox_root: str = ""            # workspace root for this tenant
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthIdentity:
    """Authenticated user/service identity."""
    user_id: str
    auth_method: AuthMethod
    tenant: TenantContext
    roles: list[str] = field(default_factory=list)       # admin, developer, viewer
    permissions: list[str] = field(default_factory=list)  # tool:execute, file:write, etc.
    session_id: str = ""
    issued_at: float = 0.0
    expires_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.expires_at <= 0:
            return False
        return time.time() > self.expires_at

    def has_permission(self, permission: str) -> bool:
        if "admin" in self.roles:
            return True
        return permission in self.permissions

    def has_role(self, role: str) -> bool:
        return role in self.roles


# ── Auth Provider Interface ─────────────────────────────────────────────────

class AuthProvider:
    """Base class for authentication providers."""

    def authenticate(self, credentials: dict[str, Any]) -> AuthIdentity | None:
        raise NotImplementedError


class JWTAuthProvider(AuthProvider):
    """JWT-based authentication using HMAC-SHA256 signature verification.

    The secret and environment are sourced exclusively from the centralized
    ``settings`` object (pydantic-settings), which validates them at startup.
    There is NO fallback to a hard-coded secret — if the secret is absent in
    production the application will have already failed to start.
    """

    def __init__(self, secret: str = "", environment: str = ""):
        # Use centralized settings as the single source of truth.
        # A caller may supply overrides (e.g. in unit tests) but in normal
        # operation settings is always the authority.
        from backend.app.config import settings as _settings
        self._secret = secret or _settings.JWT_SECRET
        self._environment = environment or _settings.ENVIRONMENT

        if self._environment.lower() == "production" and not self._secret:
            raise RuntimeError(
                "JWT_SECRET must be configured in settings before starting in production. "
                "Set JWT_SECRET in your .env or environment variables."
            )
        if not self._secret:
            # Development mode: generate a stable in-process secret via settings
            # (settings already calls keyring / secrets.token_hex for dev).
            raise RuntimeError(
                "JWT_SECRET is empty. Ensure settings loaded correctly before "
                "constructing JWTAuthProvider."
            )


    def authenticate(self, credentials: dict[str, Any]) -> AuthIdentity | None:
        token = credentials.get("token", "")
        if not token:
            return None

        payload = self._decode_jwt(token)
        if payload is None:
            return None

        tenant = TenantContext(
            tenant_id=payload.get("tenant_id", "default"),
            org_name=payload.get("org_name", ""),
            tier=payload.get("tier", "free"),
        )

        return AuthIdentity(
            user_id=payload.get("sub", "unknown"),
            auth_method=AuthMethod.JWT,
            tenant=tenant,
            roles=payload.get("roles", ["developer"]),
            permissions=payload.get("permissions", []),
            session_id=payload.get("session_id", ""),
            issued_at=payload.get("iat", 0),
            expires_at=payload.get("exp", 0),
        )

    def generate_token(self, identity: AuthIdentity, ttl_seconds: int = 86400) -> str:
        """Generate a JWT token for the given identity."""
        now = time.time()
        payload = {
            "sub": identity.user_id,
            "tenant_id": identity.tenant.tenant_id,
            "org_name": identity.tenant.org_name,
            "tier": identity.tenant.tier,
            "roles": identity.roles,
            "permissions": identity.permissions,
            "session_id": identity.session_id,
            "iat": now,
            "exp": now + ttl_seconds,
        }
        return self._encode_jwt(payload)

    def _encode_jwt(self, payload: dict[str, Any]) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        header_b64 = self._b64url_encode(json.dumps(header, separators=(",", ":")))
        payload_b64 = self._b64url_encode(json.dumps(payload, separators=(",", ":")))
        signing_input = f"{header_b64}.{payload_b64}"
        signature = hmac.new(
            self._secret.encode(), signing_input.encode(), hashlib.sha256
        ).digest()
        sig_b64 = self._b64url_encode_bytes(signature)
        return f"{signing_input}.{sig_b64}"

    def _decode_jwt(self, token: str) -> dict[str, Any] | None:
        parts = token.split(".")
        if len(parts) != 3:
            logger.warning("Invalid JWT format")
            return None

        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}"

        expected_sig = hmac.new(
            self._secret.encode(), signing_input.encode(), hashlib.sha256
        ).digest()
        actual_sig = self._b64url_decode_bytes(sig_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            logger.warning("JWT signature verification failed")
            return None

        try:
            payload = json.loads(self._b64url_decode(payload_b64))
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"JWT payload decode error: {e}")
            return None

        if payload.get("exp", 0) > 0 and time.time() > payload["exp"]:
            logger.info("JWT token expired")
            return None

        return payload

    @staticmethod
    def _b64url_encode(data: str) -> str:
        import base64
        return base64.urlsafe_b64encode(data.encode()).rstrip(b"=").decode()

    @staticmethod
    def _b64url_encode_bytes(data: bytes) -> str:
        import base64
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    @staticmethod
    def _b64url_decode(data: str) -> str:
        import base64
        padding = 4 - len(data) % 4
        if padding != 4:
            data += "=" * padding
        return base64.urlsafe_b64decode(data).decode()

    @staticmethod
    def _b64url_decode_bytes(data: str) -> bytes:
        import base64
        padding = 4 - len(data) % 4
        if padding != 4:
            data += "=" * padding
        return base64.urlsafe_b64decode(data)


class APIKeyAuthProvider(AuthProvider):
    """API key-based authentication for programmatic access."""

    def __init__(self):
        self._keys: dict[str, AuthIdentity] = {}
        self._load_keys()

    def _load_keys(self) -> None:
        """Load API keys from environment or config."""
        master_key = os.getenv("DEVPILOT_API_KEY", "")
        if master_key:
            self._keys[master_key] = AuthIdentity(
                user_id="api-user",
                auth_method=AuthMethod.API_KEY,
                tenant=TenantContext(tenant_id="default", tier="enterprise"),
                roles=["admin"],
                permissions=["*"],
            )

    def register_key(self, key: str, identity: AuthIdentity) -> None:
        self._keys[key] = identity

    def authenticate(self, credentials: dict[str, Any]) -> AuthIdentity | None:
        api_key = credentials.get("api_key", "")
        if not api_key:
            return None

        identity = self._keys.get(api_key)
        if identity is None:
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:12]
            logger.warning(f"Unknown API key (hash: {key_hash})")
            return None

        return identity


class WebSocketTokenProvider(AuthProvider):
    """WebSocket connection token validation.

    Tokens are strictly one-time: a token MUST have been pre-registered via
    ``generate_ws_token()`` before it will be accepted.  Any JWT that was not
    pre-registered is rejected immediately, even if its signature is valid.
    This prevents regular long-lived JWTs from being used as WebSocket tokens.
    """

    # Maximum number of pending tickets held in memory — prevents exhaustion attacks.
    _MAX_PENDING_TOKENS = 5_000

    def __init__(self, jwt_provider: JWTAuthProvider):
        self._jwt = jwt_provider
        self._one_time_tokens: dict[str, float] = {}

    def generate_ws_token(self, identity: AuthIdentity) -> str:
        """Generate a short-lived one-time-use WebSocket token."""
        # Evict expired tokens first to bound memory usage.
        self._evict_expired()
        if len(self._one_time_tokens) >= self._MAX_PENDING_TOKENS:
            # Evict oldest 10 % when at capacity to prevent DoS.
            items = sorted(self._one_time_tokens.items(), key=lambda kv: kv[1])
            for k, _ in items[: len(items) // 10 + 1]:
                del self._one_time_tokens[k]
        token = self._jwt.generate_token(identity, ttl_seconds=300)
        self._one_time_tokens[token] = time.time() + 300
        return token

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [k for k, exp in self._one_time_tokens.items() if exp <= now]
        for k in expired:
            del self._one_time_tokens[k]

    def authenticate(self, credentials: dict[str, Any]) -> AuthIdentity | None:
        token = credentials.get("ws_token", "")
        if not token:
            return None

        # Strictly one-time: reject tokens that were never pre-registered.
        # This prevents long-lived JWTs from being used as WebSocket tokens.
        if token not in self._one_time_tokens:
            logger.warning("WebSocket token not in one-time registry — rejected")
            return None

        if time.time() > self._one_time_tokens[token]:
            del self._one_time_tokens[token]
            logger.info("WebSocket token expired")
            return None

        # Consume the token (one-time use enforced)
        del self._one_time_tokens[token]

        # Verify JWT signature after confirming pre-registration
        identity = self._jwt.authenticate({"token": token})
        if identity:
            identity.auth_method = AuthMethod.WEBSOCKET_TOKEN
        return identity


# ── Auth Gateway (Unified Entry Point) ──────────────────────────────────────

class AuthGateway:
    """Unified authentication gateway that chains multiple auth providers."""

    def __init__(self):
        self._jwt_provider = JWTAuthProvider()
        self._api_key_provider = APIKeyAuthProvider()
        self._ws_provider = WebSocketTokenProvider(self._jwt_provider)
        self._default_identity = AuthIdentity(
            user_id="default-user",
            auth_method=AuthMethod.JWT,
            tenant=TenantContext(tenant_id="default-org", tier="free"),
            roles=["developer"],
            permissions=["workspace:read", "workspace:write", "terminal:execute"],
        )

    @property
    def jwt_provider(self) -> JWTAuthProvider:
        return self._jwt_provider

    @property
    def ws_provider(self) -> WebSocketTokenProvider:
        return self._ws_provider

    def authenticate(self, headers: dict[str, str] = None, query_params: dict[str, str] = None) -> AuthIdentity | None:
        """Authenticate a request using available credentials.

        Priority order:
          1. Authorization: Bearer <JWT> header
          2. X-API-Key header
          3. Development fallback (non-production only)

        Query-parameter tokens (?token=) are intentionally NOT supported.
        Tokens in URLs leak through access logs, browser history, and reverse
        proxies. WebSocket connections must use the one-time ticket system
        (state.create_ws_ticket / state.verify_ws_ticket).
        """
        from backend.app.config import settings as _settings
        headers = headers or {}

        # 1. Try JWT from Authorization header (Bearer scheme only)
        auth_header = headers.get("authorization", headers.get("Authorization", ""))
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            identity = self._jwt_provider.authenticate({"token": token})
            if identity:
                logger.debug(f"Authenticated via JWT: user={identity.user_id}")
                return identity

        # 2. Try API key (X-API-Key header only)
        api_key = headers.get("x-api-key", headers.get("X-API-Key", ""))
        if api_key:
            identity = self._api_key_provider.authenticate({"api_key": api_key})
            if identity:
                logger.debug(f"Authenticated via API key: user={identity.user_id}")
                return identity

        # 3. No valid credentials found
        # Production: return None (caller must return 401)
        # Development/desktop: fall back to local developer identity
        if _settings.ENVIRONMENT.lower() == "production":
            return None

        logger.debug("No credentials found, using default local developer identity")
        return self._default_identity


# ── Singleton ───────────────────────────────────────────────────────────────

auth_gateway = AuthGateway()
