"""Custom exceptions for the Replane Python SDK."""

from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    """Error codes for ReplaneError."""

    NOT_FOUND = "not_found"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    AUTH_ERROR = "auth_error"
    FORBIDDEN = "forbidden"
    SERVER_ERROR = "server_error"
    CLIENT_ERROR = "client_error"
    CLOSED = "closed"
    NOT_INITIALIZED = "not_initialized"
    MISSING_DEPENDENCY = "missing_dependency"
    UNKNOWN = "unknown"


class ReplaneError(Exception):
    """Base exception for all Replane SDK errors.

    Attributes:
        code: Error code identifying the type of error.
        message: Human-readable error description.
        cause: Optional underlying exception that caused this error.

    Example:
        try:
            value = client.get("my-config")
        except ReplaneError as e:
            if e.code == ErrorCode.NOT_FOUND:
                # Handle missing config
                pass
            elif e.code == ErrorCode.TIMEOUT:
                # Handle timeout
                pass
    """

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.__cause__ = cause

    def __str__(self) -> str:
        result = f"[{self.code.value}] {self.message}"
        if self.__cause__:
            result += f" (caused by: {self.__cause__})"
        return result

    def __repr__(self) -> str:
        return f"ReplaneError(code={self.code!r}, message={self.message!r})"


class ConfigNotFoundError(ReplaneError):
    """Raised when a requested config does not exist."""

    def __init__(self, config_name: str, *, cause: BaseException | None = None) -> None:
        super().__init__(
            ErrorCode.NOT_FOUND,
            f"Config '{config_name}' not found",
            cause=cause,
        )
        self.config_name = config_name


class TimeoutError(ReplaneError):
    """Raised when an operation times out."""

    def __init__(
        self,
        message: str = "Operation timed out",
        *,
        timeout_ms: int | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(ErrorCode.TIMEOUT, message, cause=cause)
        self.timeout_ms = timeout_ms


class AuthenticationError(ReplaneError):
    """Raised when authentication fails (invalid SDK key)."""

    def __init__(
        self,
        message: str = "Authentication failed - check your SDK key",
        *,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(ErrorCode.AUTH_ERROR, message, cause=cause)


class NetworkError(ReplaneError):
    """Raised when a network request fails."""

    def __init__(
        self,
        message: str = "Network request failed",
        *,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(ErrorCode.NETWORK_ERROR, message, cause=cause)


class ClientClosedError(ReplaneError):
    """Raised when attempting operations on a closed client."""

    def __init__(self, *, cause: BaseException | None = None) -> None:
        super().__init__(
            ErrorCode.CLOSED,
            "Client has been closed",
            cause=cause,
        )


class NotInitializedError(ReplaneError):
    """Raised when the client hasn't finished initialization."""

    def __init__(self, *, cause: BaseException | None = None) -> None:
        super().__init__(
            ErrorCode.NOT_INITIALIZED,
            "Client has not been initialized - await the client creation first",
            cause=cause,
        )


class MissingDependencyError(ReplaneError):
    """Raised when an optional dependency is required but not installed."""

    def __init__(self, dependency: str, feature: str) -> None:
        super().__init__(
            ErrorCode.MISSING_DEPENDENCY,
            f"The '{dependency}' package is required for {feature}. "
            f"Install it with: pip install replane[async]",
        )
        self.dependency = dependency
        self.feature = feature


def from_http_status(
    status: int,
    message: str | None = None,
    *,
    cause: BaseException | None = None,
) -> ReplaneError:
    """Create an appropriate ReplaneError from an HTTP status code.

    Args:
        status: HTTP status code.
        message: Optional error message from the response.
        cause: Optional underlying exception.

    Returns:
        A ReplaneError subclass appropriate for the status code.
    """
    if status == 401:
        return AuthenticationError(message or "Invalid SDK key", cause=cause)
    elif status == 403:
        return ReplaneError(
            ErrorCode.FORBIDDEN,
            message or "Access forbidden",
            cause=cause,
        )
    elif status == 404:
        return ReplaneError(
            ErrorCode.NOT_FOUND,
            message or "Resource not found",
            cause=cause,
        )
    elif 400 <= status < 500:
        return ReplaneError(
            ErrorCode.CLIENT_ERROR,
            message or f"Client error (HTTP {status})",
            cause=cause,
        )
    elif status >= 500:
        return ReplaneError(
            ErrorCode.SERVER_ERROR,
            message or f"Server error (HTTP {status})",
            cause=cause,
        )
    else:
        return ReplaneError(
            ErrorCode.UNKNOWN,
            message or f"Unexpected HTTP status: {status}",
            cause=cause,
        )
