"""Testing utilities for the Replane Python SDK.

This module provides an in-memory client for testing applications that use
Replane without requiring a real server connection.
"""

from __future__ import annotations

from typing import Any, Callable, TypeVar

from ._eval import evaluate_config
from .errors import ClientClosedError, ConfigNotFoundError
from .types import Config, ContextValue, Override, parse_condition

T = TypeVar("T")


class InMemoryReplaneClient:
    """An in-memory Replane client for testing.

    This client provides the same interface as SyncReplaneClient but stores
    all configs in memory. It's useful for unit tests where you don't want
    to connect to a real Replane server.

    Example:
        >>> client = InMemoryReplaneClient({
        ...     "feature-enabled": True,
        ...     "rate-limit": 100,
        ... })
        >>> assert client.get("feature-enabled") is True
        >>> assert client.get("rate-limit") == 100

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
        >>> assert client.get("feature", context={"plan": "free"}) is False
        >>> assert client.get("feature", context={"plan": "beta"}) is True
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

    def get(
        self,
        name: str,
        *,
        context: dict[str, ContextValue] | None = None,
        default: T | None = None,
    ) -> Any:
        """Get a config value.

        Args:
            name: Config name to retrieve.
            context: Context for override evaluation (merged with default).
            default: Default value if config doesn't exist.

        Returns:
            The config value with overrides applied.

        Raises:
            ConfigNotFoundError: If config doesn't exist and no default provided.
            ClientClosedError: If the client has been closed.
        """
        if self._closed:
            raise ClientClosedError()

        merged_context = {**self._context, **(context or {})}

        if name not in self._configs:
            if default is not None:
                return default
            raise ConfigNotFoundError(name)

        config = self._configs[name]
        return evaluate_config(config, merged_context)

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
                        conditions=tuple(
                            parse_condition(c) for c in override_data["conditions"]
                        ),
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

    def __enter__(self) -> InMemoryReplaneClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    @property
    def configs(self) -> dict[str, Config]:
        """Access to internal configs for testing inspection."""
        return self._configs.copy()


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
