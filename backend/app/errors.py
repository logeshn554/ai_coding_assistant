"""Custom exception classes for DevPilot IDE Backend."""

class DevPilotError(Exception):
    """Base exception for all DevPilot errors."""
    def __init__(self, code: str, message: str, status_code: int = 500, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class FileNotFoundError(DevPilotError):
    """Raised when a requested file or directory does not exist."""
    def __init__(self, path: str):
        super().__init__(
            code="FILE_NOT_FOUND",
            message=f"File or directory not found: {path}",
            status_code=404,
            details={"path": path}
        )


class InvalidPathError(DevPilotError):
    """Raised when an illegal or path-traversal path is specified."""
    def __init__(self, path: str, reason: str = "Invalid path specification"):
        super().__init__(
            code="INVALID_PATH",
            message=f"Invalid path '{path}': {reason}",
            status_code=400,
            details={"path": path, "reason": reason}
        )


class AccessDeniedError(DevPilotError):
    """Raised when an operation violates workspace access control."""
    def __init__(self, resource: str = "workspace"):
        super().__init__(
            code="ACCESS_DENIED",
            message=f"Access denied to resource: {resource}",
            status_code=403,
            details={"resource": resource}
        )


class RateLimitError(DevPilotError):
    """Raised when request rate limits are exceeded."""
    def __init__(self, limit: str):
        super().__init__(
            code="RATE_LIMIT_EXCEEDED",
            message=f"Rate limit exceeded: {limit}",
            status_code=429,
            details={"limit": limit}
        )
