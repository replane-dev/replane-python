"""Testing utilities for the Replane Python SDK.

This module provides an in-memory client for testing applications that use
Replane without requiring a real server connection.
"""

from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar

from ._eval import evaluate_config
from .errors import ClientClosedError
from .types import Config, ContextValue, Override, parse_condition

T = TypeVar("T")
ConfigsT = TypeVar("ConfigsT")

# Sentinel value for detecting when no default was provided
_MISSING: Any = object()


class InMemoryConfigAccessor(Generic[ConfigsT]):
    """Config accessor for InMemoryReplaneClient."""

    def __init__(
        self,
        configs: dict[str, Config],
        context: dict[str, ContextValue],
        closed_check: Callable[[], bool],
        defaults: dict[str, Any] | None = None,
    ) -> None:
        self._configs = configs
        self._context = context
        self._closed_check = closed_check
        self._defaults = defaults or {}

    def __getitem__(self, name: str) -> Any:
        if self._closed_check():
            raise ClientClosedError()

        if name not in self._configs:
            if name in self._defaults:
                return self._defaults[name]
            raise KeyError(name)

        config = self._configs[name]
        return evaluate_config(config, self._context)

    def __contains__(self, name: str) -> bool:
        return name in self._configs or name in self._defaults

    def get(self, name: str, default: T = _MISSING) -> Any:  # type: ignore[assignment]
        """Get a config value with an optional default.

        If an explicit default is provided, it takes precedence over scoped defaults.
        """
        if self._closed_check():
            raise ClientClosedError()

        # Check actual configs first
        if name in self._configs:
            config = self._configs[name]
            return evaluate_config(config, self._context)

        # If explicit default provided, use it (takes precedence over scoped defaults)
        if default is not _MISSING:
            return default

        # Fall back to scoped defaults
        if name in self._defaults:
            return self._defaults[name]

        # No default - return None (standard dict.get behavior)
        return None

    def keys(self) -> list[str]:
        all_keys = set(self._configs.keys()) | set(self._defaults.keys())
        return list(all_keys)


class ContextualInMemoryClient(Generic[ConfigsT]):
    """A wrapper around InMemoryReplaneClient with scoped context/defaults."""

    def __init__(
        self,
        client: InMemoryReplaneClient[ConfigsT],
        context: dict[str, ContextValue],
        defaults: dict[str, Any] | None = None,
    ) -> None:
        self._client = client
        self._context = context
        self._defaults = defaults or {}

    @property
    def configs(self) -> ConfigsT:
        return InMemoryConfigAccessor(  # type: ignore[return-value]
            configs=self._client._configs,
            context=self._context,
            closed_check=lambda: self._client._closed,
            defaults=self._defaults,
        )

    def with_context(
        self,
        context: dict[str, ContextValue],
    ) -> ContextualInMemoryClient[ConfigsT]:
        merged_context = {**self._context, **context}
        return ContextualInMemoryClient(self._client, merged_context, self._defaults)

    def with_defaults(
        self,
        defaults: dict[str, Any],
    ) -> ContextualInMemoryClient[ConfigsT]:
        merged_defaults = {**self._defaults, **defaults}
        return ContextualInMemoryClient(self._client, self._context, merged_defaults)

    def subscribe(
        self,
        callback: Callable[[str, Config], None],
    ) -> Callable[[], None]:
        return self._client.subscribe(callback)

    def subscribe_config(
        self,
        name: str,
        callback: Callable[[Config], None],
    ) -> Callable[[], None]:
        return self._client.subscribe_config(name, callback)

    def is_initialized(self) -> bool:
        return self._client.is_initialized()


class InMemoryReplaneClient(Generic[ConfigsT]):
    """An in-memory Replane client for testing.

    This client provides the same interface as Replane but stores
    all configs in memory. It's useful for unit tests where you don't want
    to connect to a real Replane server.

    Example:
        >>> client = InMemoryReplaneClient({
        ...     "feature-enabled": True,
        ...     "rate-limit": 100,
        ... })
        >>> assert client.configs["feature-enabled"] is True
        >>> assert client.configs["rate-limit"] == 100

    With overrides:
        >>> client = InMemoryReplaneClient()
        >>> client.set_config(
        ...     "feature",
        ...     value=False,
        ...     overrides=[{
        ...         "name": "beta",
        ...         "conditions": [{"operator": "equals", "property": "plan", "expected": "beta"}],
        ...         "value": True,
        ...     }],
        ... )
        >>> assert client.with_context({"plan": "free"}).configs["feature"] is False
        >>> assert client.with_context({"plan": "beta"}).configs["feature"] is True
    """

    def __init__(
        self,
        initial_configs: dict[str, Any] | None = None,
        *,
        context: dict[str, ContextValue] | None = None,
    ) -> None:
        """Initialize the in-memory client.

        Args:
            initial_configs: Optional dict of config name -> value.
            context: Default context for override evaluation.
        """
        self._configs: dict[str, Config] = {}
        self._context = context or {}
        self._closed = False

        # Subscription callbacks
        self._all_subscribers: list[Callable[[str, Config], None]] = []
        self._config_subscribers: dict[str, list[Callable[[Config], None]]] = {}

        # Initialize with provided configs
        if initial_configs:
            for name, value in initial_configs.items():
                self._configs[name] = Config(name=name, value=value)

    @property
    def configs(self) -> ConfigsT:
        """Dictionary-like accessor for configs."""
        return InMemoryConfigAccessor(  # type: ignore[return-value]
            configs=self._configs,
            context=self._context,
            closed_check=lambda: self._closed,
        )

    def with_context(
        self,
        context: dict[str, ContextValue],
    ) -> ContextualInMemoryClient[ConfigsT]:
        """Create a scoped client with additional context."""
        merged_context = {**self._context, **context}
        return ContextualInMemoryClient(self, merged_context, None)

    def with_defaults(
        self,
        defaults: dict[str, Any],
    ) -> ContextualInMemoryClient[ConfigsT]:
        """Create a scoped client with additional defaults."""
        return ContextualInMemoryClient(self, self._context, defaults)

    def set(self, name: str, value: Any) -> None:
        """Set a config value (simple form without overrides).

        Args:
            name: Config name.
            value: Config value.
        """
        self.set_config(name, value)

    def set_config(
        self,
        name: str,
        value: Any,
        *,
        overrides: list[dict[str, Any]] | None = None,
    ) -> None:
        """Set a config with optional overrides.

        Args:
            name: Config name.
            value: Base config value.
            overrides: Optional list of override rules.

        Example:
            >>> client.set_config(
            ...     "rate-limit",
            ...     value=100,
            ...     overrides=[{
            ...         "name": "premium-users",
            ...         "conditions": [
            ...             {"operator": "in", "property": "plan", "expected": ["pro", "enterprise"]}
            ...         ],
            ...         "value": 1000,
            ...     }],
            ... )
        """
        parsed_overrides: list[Override] = []

        if overrides:
            for override_data in overrides:
                parsed_overrides.append(
                    Override(
                        name=override_data["name"],
                        conditions=tuple(parse_condition(c) for c in override_data["conditions"]),
                        value=override_data["value"],
                    )
                )

        config = Config(
            name=name,
            value=value,
            overrides=tuple(parsed_overrides),
        )

        self._configs[name] = config

        # Notify subscribers
        for callback in self._all_subscribers:
            try:
                callback(name, config)
            except Exception:
                pass

        if name in self._config_subscribers:
            for config_callback in self._config_subscribers[name]:
                try:
                    config_callback(config)
                except Exception:
                    pass

    def delete(self, name: str) -> bool:
        """Delete a config.

        Args:
            name: Config name to delete.

        Returns:
            True if config was deleted, False if it didn't exist.
        """
        if name in self._configs:
            del self._configs[name]
            return True
        return False

    def subscribe(
        self,
        callback: Callable[[str, Config], None],
    ) -> Callable[[], None]:
        """Subscribe to all config changes.

        Args:
            callback: Function called with (config_name, config) on changes.

        Returns:
            Unsubscribe function.
        """
        self._all_subscribers.append(callback)

        def unsubscribe() -> None:
            if callback in self._all_subscribers:
                self._all_subscribers.remove(callback)

        return unsubscribe

    def subscribe_config(
        self,
        name: str,
        callback: Callable[[Config], None],
    ) -> Callable[[], None]:
        """Subscribe to changes for a specific config.

        Args:
            name: Config name to watch.
            callback: Function called with the new config on changes.

        Returns:
            Unsubscribe function.
        """
        if name not in self._config_subscribers:
            self._config_subscribers[name] = []
        self._config_subscribers[name].append(callback)

        def unsubscribe() -> None:
            if name in self._config_subscribers:
                if callback in self._config_subscribers[name]:
                    self._config_subscribers[name].remove(callback)

        return unsubscribe

    def close(self) -> None:
        """Close the client."""
        self._closed = True

    def is_initialized(self) -> bool:
        """Check if the client has finished initialization.

        For the in-memory client, this always returns True since
        configs are available immediately.

        Returns:
            True (always, for in-memory client).
        """
        return True

    def __enter__(self) -> InMemoryReplaneClient[ConfigsT]:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


def create_test_client(
    configs: dict[str, Any] | None = None,
    *,
    context: dict[str, ContextValue] | None = None,
) -> InMemoryReplaneClient:
    """Create an in-memory client for testing.

    This is a convenience function for creating test clients.

    Args:
        configs: Optional dict of config name -> value.
        context: Default context for override evaluation.

    Returns:
        An InMemoryReplaneClient instance.

    Example:
        >>> client = create_test_client({
        ...     "feature-enabled": True,
        ...     "max-items": 50,
        ... })
    """
    return InMemoryReplaneClient(configs, context=context)
