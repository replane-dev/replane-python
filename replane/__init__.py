"""Replane Python SDK - Dynamic configuration with real-time updates.

Replane is a configuration platform that enables applications to change
settings in real-time without deploying code.

Quick start (sync):
    >>> from replane import SyncReplaneClient
    >>>
    >>> with SyncReplaneClient(
    ...     base_url="https://replane.example.com",
    ...     sdk_key="sk_...",
    ... ) as client:
    ...     if client.get("new-feature-enabled"):
    ...         enable_new_feature()

Quick start (async):
    >>> from replane import AsyncReplaneClient
    >>>
    >>> async with AsyncReplaneClient(
    ...     base_url="https://replane.example.com",
    ...     sdk_key="sk_...",
    ... ) as client:
    ...     rate_limit = client.get("rate-limit", context={"plan": user.plan})

For testing:
    >>> from replane.testing import create_test_client
    >>>
    >>> client = create_test_client({
    ...     "feature-enabled": True,
    ...     "rate-limit": 100,
    ... })
"""

from .version import VERSION, VERSION_SHORT

# Core clients
from ._sync import SyncReplaneClient

# Types
from .types import (
    Config,
    Context,
    ContextValue,
    Override,
    Condition,
    PropertyCondition,
    SegmentationCondition,
    AndCondition,
    OrCondition,
    NotCondition,
)

# Errors
from .errors import (
    ReplaneError,
    ErrorCode,
    ConfigNotFoundError,
    TimeoutError,
    AuthenticationError,
    NetworkError,
    ClientClosedError,
    NotInitializedError,
    MissingDependencyError,
)

# Async client (lazy import to avoid httpx dependency)
def __getattr__(name: str):
    if name == "AsyncReplaneClient":
        from ._async import AsyncReplaneClient
        return AsyncReplaneClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Version
    "VERSION",
    "VERSION_SHORT",
    # Clients
    "SyncReplaneClient",
    "AsyncReplaneClient",
    # Types
    "Config",
    "Context",
    "ContextValue",
    "Override",
    "Condition",
    "PropertyCondition",
    "SegmentationCondition",
    "AndCondition",
    "OrCondition",
    "NotCondition",
    # Errors
    "ReplaneError",
    "ErrorCode",
    "ConfigNotFoundError",
    "TimeoutError",
    "AuthenticationError",
    "NetworkError",
    "ClientClosedError",
    "NotInitializedError",
    "MissingDependencyError",
]
