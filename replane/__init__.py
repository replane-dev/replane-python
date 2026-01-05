"""Replane Python SDK - Dynamic configuration with real-time updates.

Replane is a configuration platform that enables applications to change
settings in real-time without deploying code.

Quick start (sync):
    >>> from replane import Replane
    >>>
    >>> with Replane(
    ...     base_url="https://cloud.replane.dev",
    ...     sdk_key="rp_...",
    ... ) as replane:
    ...     if replane.configs["new-feature-enabled"]:
    ...         enable_new_feature()

Quick start (async):
    >>> from replane import AsyncReplane
    >>>
    >>> async with AsyncReplane(
    ...     base_url="https://cloud.replane.dev",
    ...     sdk_key="rp_...",
    ... ) as replane:
    ...     user_client = replane.with_context({"plan": user.plan})
    ...     rate_limit = user_client.configs["rate-limit"]

With generated TypedDict types for better type safety (recommended):
    >>> from replane import Replane
    >>> from replane_types import Configs
    >>>
    >>> with Replane[Configs](
    ...     base_url="https://cloud.replane.dev",
    ...     sdk_key="rp_...",
    ... ) as replane:
    ...     config = replane.configs["my-feature"]  # fully typed dict access
    ...     print(config["enabled"])  # type-safe property access

For testing:
    >>> from replane.testing import create_test_client
    >>>
    >>> replane = create_test_client({
    ...     "feature-enabled": True,
    ...     "rate-limit": 100,
    ... })
"""

from ._sync import REPLANE_CLIENT_ID_KEY, Replane
from .errors import (
    AuthenticationError,
    ClientClosedError,
    ConfigNotFoundError,
    ErrorCode,
    MissingDependencyError,
    NetworkError,
    NotInitializedError,
    ReplaneError,
    TimeoutError,
)
from .types import (
    AndCondition,
    Condition,
    Config,
    Context,
    ContextValue,
    NotCondition,
    OrCondition,
    Override,
    PropertyCondition,
    SegmentationCondition,
)
from .version import VERSION, VERSION_SHORT


# Async client (lazy import to avoid httpx dependency)
def __getattr__(name: str):
    if name == "AsyncReplane":
        from ._async import AsyncReplane

        return AsyncReplane
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Version
    "VERSION",
    "VERSION_SHORT",
    # Clients
    "Replane",
    "AsyncReplane",
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
