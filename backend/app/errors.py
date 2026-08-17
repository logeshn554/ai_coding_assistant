"""Custom exception classes for Loopix IDE Backend."""



class LoopixError(Exception):
    """Base exception for all Loopix errors."""
    def __init__(self, code: str, message: str, status_code: int = 500, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class FileNotFoundError(LoopixError):
    """Raised when a requested file or directory does not exist."""
    def __init__(self, path: str):
        super().__init__(
            code="FILE_NOT_FOUND",
            message=f"File or directory not found: {path}",
            status_code=404,
            details={"path": path}
        )


class InvalidPathError(LoopixError):
    """Raised when an illegal or path-traversal path is specified."""
    def __init__(self, path: str, reason: str = "Invalid path specification"):
        super().__init__(
            code="INVALID_PATH",
            message=f"Invalid path '{path}': {reason}",
            status_code=400,
            details={"path": path, "reason": reason}
        )


class AccessDeniedError(LoopixError):
    """Raised when an operation violates workspace access control."""
    def __init__(self, resource: str = "workspace"):
        super().__init__(
            code="ACCESS_DENIED",
            message=f"Access denied to resource: {resource}",
            status_code=403,
            details={"resource": resource}
        )


class RateLimitError(LoopixError):
    """Raised when request rate limits are exceeded."""
    def __init__(self, limit: str):
        super().__init__(
            code="RATE_LIMIT_EXCEEDED",
            message=f"Rate limit exceeded: {limit}",
            status_code=429,
            details={"limit": limit}
        )


# ── LLM Provider Errors ──────────────────────────────────────────────────────
# These are raised by the LLM adapter layer and must NEVER be silently
# converted to a normal assistant text response. The agent loop must catch
# these and either retry (rate limit / timeout) or stop with LLM_ERROR state.

class LLMProviderError(LoopixError):
    """Base class for all LLM provider failures.

    Attributes:
        provider: The provider name (e.g. 'openai', 'anthropic').
        error_type: Machine-readable error category.
        retryable: Whether the agent loop should retry this call.
    """
    def __init__(
        self,
        code: str,
        message: str,
        provider: str = "",
        retryable: bool = False,
        status_code: int = 500,
        details: dict | None = None,
    ):
        super().__init__(code=code, message=message, status_code=status_code, details=details or {})
        self.provider = provider
        self.retryable = retryable
        self.details.setdefault("provider", provider)
        self.details.setdefault("retryable", retryable)


class LLMAuthError(LLMProviderError):
    """Raised when the API key is missing, invalid, or revoked."""
    def __init__(self, provider: str = "", message: str | None = None):
        super().__init__(
            code="LLM_AUTH_ERROR",
            message=message or f"Authentication failed for provider '{provider}'. Check API key.",
            provider=provider,
            retryable=False,
            status_code=401,
        )


class LLMRateLimitError(LLMProviderError):
    """Raised when the provider's rate limit (RPM/TPM) is exceeded."""
    def __init__(self, provider: str = "", retry_after_seconds: float = 0.0, message: str | None = None):
        super().__init__(
            code="LLM_RATE_LIMIT",
            message=message or f"Rate limit exceeded for provider '{provider}'.",
            provider=provider,
            retryable=True,
            status_code=429,
            details={"retry_after_seconds": retry_after_seconds},
        )
        self.retry_after_seconds = retry_after_seconds


class LLMTimeoutError(LLMProviderError):
    """Raised when the provider request times out."""
    def __init__(self, provider: str = "", timeout_seconds: float = 0.0, message: str | None = None):
        super().__init__(
            code="LLM_TIMEOUT",
            message=message or f"Request to provider '{provider}' timed out after {timeout_seconds:.0f}s.",
            provider=provider,
            retryable=True,
            status_code=504,
            details={"timeout_seconds": timeout_seconds},
        )


class LLMBudgetExceededError(LLMProviderError):
    """Raised when account balance, credits, or max_tokens budget is exceeded."""
    def __init__(self, provider: str = "", message: str | None = None):
        super().__init__(
            code="LLM_BUDGET_EXCEEDED",
            message=message or f"Credit balance or token budget exceeded for provider '{provider}'.",
            provider=provider,
            retryable=False,
            status_code=402,
        )


class LLMThoughtSignatureError(LLMProviderError):
    """Raised when a thought_signature or tool reasoning format issue occurs."""
    def __init__(self, provider: str = "", message: str | None = None):
        super().__init__(
            code="LLM_THOUGHT_SIGNATURE_ERROR",
            message=message or f"Missing or invalid thought signature for provider '{provider}'.",
            provider=provider,
            retryable=False,
            status_code=400,
        )


class LLMNetworkError(LLMProviderError):
    """Raised for network/connectivity failures reaching the provider."""
    def __init__(self, provider: str = "", message: str | None = None):
        super().__init__(
            code="LLM_NETWORK_ERROR",
            message=message or f"Network error connecting to provider '{provider}'.",
            provider=provider,
            retryable=True,
            status_code=503,
        )


class LLMInvalidResponseError(LLMProviderError):
    """Raised when the provider returns a malformed or unparseable response."""
    def __init__(self, provider: str = "", message: str | None = None):
        super().__init__(
            code="LLM_INVALID_RESPONSE",
            message=message or f"Provider '{provider}' returned an invalid/unparseable response.",
            provider=provider,
            retryable=False,
            status_code=502,
        )


class LLMConfigurationError(LLMProviderError):
    """Raised when the LLM adapter is misconfigured (missing base URL, model, etc.)."""
    def __init__(self, provider: str = "", message: str | None = None):
        super().__init__(
            code="LLM_CONFIGURATION_ERROR",
            message=message or f"Provider '{provider}' is not correctly configured.",
            provider=provider,
            retryable=False,
            status_code=500,
        )


# ── Agent Execution Errors ───────────────────────────────────────────────────

class AgentMaxIterationsError(LoopixError):
    """Raised when the agent loop hits the max iteration limit."""
    def __init__(self, max_iterations: int):
        super().__init__(
            code="AGENT_MAX_ITERATIONS",
            message=f"Agent reached the maximum limit of {max_iterations} iterations without completing.",
            status_code=500,
            details={"max_iterations": max_iterations},
        )


class AgentVerificationError(LoopixError):
    """Raised when task verification fails after the agent reports completion."""
    def __init__(self, reason: str = ""):
        super().__init__(
            code="AGENT_VERIFICATION_FAILED",
            message=f"Agent task verification failed: {reason}",
            status_code=500,
            details={"reason": reason},
        )


class NeedsUserApprovalError(LoopixError):
    """Raised when a tool requires explicit user approval before executing."""
    def __init__(self, tool_name: str, risk: str = "HIGH"):
        super().__init__(
            code="NEEDS_USER_APPROVAL",
            message=f"Tool '{tool_name}' requires user approval (risk: {risk}).",
            status_code=202,
            details={"tool_name": tool_name, "risk": risk},
        )

