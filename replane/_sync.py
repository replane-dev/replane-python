"""Synchronous client implementation for the Replane Python SDK.

This module provides a thread-safe sync client using only stdlib (urllib).
SSE streaming is handled in a background thread.
"""

from __future__ import annotations

import http.client
import json
import logging
import socket
import ssl
import threading
import time
import uuid
from typing import Any, Callable, Generic, TypeVar
from urllib.parse import urlparse

from ._eval import evaluate_config
from ._sse import SSEParser
from .errors import (
    AuthenticationError,
    ClientClosedError,
    ConfigNotFoundError,
    NetworkError,
    ReplaneError,
    TimeoutError,
    from_http_status,
)
from .types import Config, ContextValue, parse_config
from .version import VERSION

#: The context key for the auto-generated client ID.
#: This key is automatically set by the SDK and can be used for segmentation.
#: User-provided values for this key take precedence over the auto-generated value.
REPLANE_CLIENT_ID_KEY = "replaneClientId"

T = TypeVar("T")

#: Type variable for the optional Configs TypedDict type parameter.
#: When provided, enables better type inference for config values.
ConfigsT = TypeVar("ConfigsT")

# Sentinel value for detecting when no default was provided
_MISSING: Any = object()


class ConfigAccessor(Generic[ConfigsT]):
    """Dictionary-like accessor for configuration values.

    Provides bracket notation access to configs with override evaluation.
    The type parameter ``ConfigsT`` should be a TypedDict for full type safety.

    Example:
        >>> config_value = client.configs["my-feature-flag"]
        >>> print(config_value["enabled"])  # Access typed properties
    """

    def __init__(
        self,
        configs: dict[str, Config],
        context: dict[str, ContextValue],
        lock: threading.RLock,
        closed_check: Callable[[], bool],
        defaults: dict[str, Any] | None = None,
    ) -> None:
        self._configs = configs
        self._context = context
        self._lock = lock
        self._closed_check = closed_check
        self._defaults = defaults or {}

    def __getitem__(self, name: str) -> Any:
        """Get a config value by name with override evaluation.

        Args:
            name: The config name to retrieve.

        Returns:
            The config value with overrides applied.

        Raises:
            KeyError: If the config doesn't exist and no scoped default is set.
            ClientClosedError: If the client has been closed.
        """
        if self._closed_check():
            raise ClientClosedError()

        logger.debug("configs[%r] with context: %s", name, self._context or "(none)")

        with self._lock:
            if name not in self._configs:
                # Check scoped defaults
                if name in self._defaults:
                    logger.debug(
                        "Config %r not found, using scoped default: %r", name, self._defaults[name]
                    )
                    return self._defaults[name]
                logger.debug("Config %r not found", name)
                raise KeyError(name)

            config = self._configs[name]
            result = evaluate_config(config, self._context)
            logger.debug(
                "Config %r: base_value=%r, overrides=%d, result=%r",
                name,
                config.value,
                len(config.overrides),
                result,
            )
            return result

    def __contains__(self, name: str) -> bool:
        """Check if a config exists (including scoped defaults).

        Args:
            name: The config name to check.

        Returns:
            True if the config exists or has a scoped default, False otherwise.
        """
        with self._lock:
            return name in self._configs or name in self._defaults

    def get(self, name: str, default: T = _MISSING) -> Any:  # type: ignore[assignment]
        """Get a config value with an optional default.

        If an explicit default is provided, it takes precedence over scoped defaults.

        Args:
            name: The config name to retrieve.
            default: Value to return if config doesn't exist (overrides scoped defaults).

        Returns:
            The config value or default.
        """
        if self._closed_check():
            raise ClientClosedError()

        with self._lock:
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
        """Return all config names (including scoped defaults)."""
        with self._lock:
            all_keys = set(self._configs.keys()) | set(self._defaults.keys())
            return list(all_keys)


class ContextualReplane(Generic[ConfigsT]):
    """A wrapper around Replane that provides scoped context and defaults.

    This class is returned by ``Replane.with_context()`` or ``Replane.with_defaults()``
    and provides the same interface as ``Replane``, but with merged context/defaults.

    Example:
        >>> with Replane(...) as client:
        ...     # Create a scoped client for a specific user
        ...     user_client = client.with_context({"user_id": "123", "plan": "premium"})
        ...     rate_limit = user_client.configs["rate-limit"]  # Uses merged context
        ...
        ...     # Create a scoped client with additional defaults
        ...     safe_client = client.with_defaults({"timeout": 30})
        ...     timeout = safe_client.configs["timeout"]  # Returns 30 if not configured
    """

    def __init__(
        self,
        client: Replane[ConfigsT],
        context: dict[str, ContextValue],
        defaults: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the contextual wrapper.

        Args:
            client: The underlying Replane client.
            context: The merged context for this wrapper.
            defaults: Additional defaults for this wrapper.
        """
        self._client = client
        self._context = context
        self._defaults = defaults or {}

    @property
    def configs(self) -> ConfigsT:
        """Dictionary-like accessor using the scoped context and defaults."""
        return ConfigAccessor(  # type: ignore[return-value]
            configs=self._client._configs,
            context=self._context,
            lock=self._client._lock,
            closed_check=lambda: self._client._closed,
            defaults=self._defaults,
        )

    def with_context(
        self,
        context: dict[str, ContextValue],
    ) -> ContextualReplane[ConfigsT]:
        """Create a new contextual wrapper with additional context.

        Args:
            context: Additional context to merge.

        Returns:
            A new ContextualReplane with the merged context.
        """
        merged_context = {**self._context, **context}
        return ContextualReplane(self._client, merged_context, self._defaults)

    def with_defaults(
        self,
        defaults: dict[str, Any],
    ) -> ContextualReplane[ConfigsT]:
        """Create a new contextual wrapper with additional defaults.

        Args:
            defaults: Additional defaults to merge.

        Returns:
            A new ContextualReplane with the merged defaults.
        """
        merged_defaults = {**self._defaults, **defaults}
        return ContextualReplane(self._client, self._context, merged_defaults)

    def subscribe(
        self,
        callback: Callable[[str, Config], None],
    ) -> Callable[[], None]:
        """Subscribe to all config changes (delegates to underlying client)."""
        return self._client.subscribe(callback)

    def subscribe_config(
        self,
        name: str,
        callback: Callable[[Config], None],
    ) -> Callable[[], None]:
        """Subscribe to changes for a specific config (delegates to underlying client)."""
        return self._client.subscribe_config(name, callback)

    def is_initialized(self) -> bool:
        """Check if the underlying client has finished initialization."""
        return self._client.is_initialized()


# Default agent identifier
DEFAULT_AGENT = f"replane-python/{VERSION}"

logger = logging.getLogger("replane")


def _setup_debug_logging() -> None:
    """Configure the replane logger for debug output."""
    logger.setLevel(logging.DEBUG)
    # Only add handler if none exist to avoid duplicates
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)


class Replane(Generic[ConfigsT]):
    """Synchronous Replane client with background SSE streaming.

    This client maintains a persistent SSE connection to receive real-time
    config updates. Config reads are synchronous and return immediately
    from the local cache.

    The optional type parameter ``ConfigsT`` can be a TypedDict generated by
    Replane's codegen feature. When provided, it enables better type inference
    for config values accessed via the ``configs`` property.

    Example:
        >>> client = Replane(
        ...     base_url="https://replane.example.com",
        ...     sdk_key="rp_...",
        ... )
        >>> client.connect()
        >>> value = client.get("feature-flag")
        >>> client.close()

    For simpler usage, prefer the context manager:
        >>> with Replane(...) as client:
        ...     value = client.get("feature-flag")

    With generated types for better type safety (recommended):
        >>> from replane_types import Configs
        >>> with Replane[Configs](...) as client:
        ...     config = client.configs["feature-flag"]  # fully typed
        ...     print(config["enabled"])  # type-safe property access
    """

    def __init__(
        self,
        base_url: str,
        sdk_key: str,
        *,
        context: dict[str, ContextValue] | None = None,
        defaults: dict[str, Any] | None = None,
        required: list[str] | None = None,
        request_timeout_ms: int = 2000,
        initialization_timeout_ms: int = 5000,
        retry_delay_ms: int = 200,
        inactivity_timeout_ms: int = 30000,
        agent: str | None = None,
        debug: bool = False,
    ) -> None:
        """Initialize the Replane client.

        Args:
            base_url: Base URL of the Replane server.
            sdk_key: SDK key for authentication.
            context: Default context for override evaluation.
            defaults: Default values for configs if not loaded from server.
            required: List of config names that must be present on init.
            request_timeout_ms: Timeout for HTTP requests in milliseconds.
            initialization_timeout_ms: Timeout for initial connection.
            retry_delay_ms: Initial delay between retries.
            inactivity_timeout_ms: Max time without SSE events before reconnect.
            agent: Agent identifier sent in User-Agent header. Defaults to SDK identifier.
            debug: Enable debug logging to see all client activity.
        """
        # Configure debug logging
        self._debug = debug
        if debug:
            _setup_debug_logging()
            logger.debug(
                "Initializing Replane: base_url=%s, "
                "request_timeout_ms=%d, initialization_timeout_ms=%d, "
                "retry_delay_ms=%d, inactivity_timeout_ms=%d",
                base_url,
                request_timeout_ms,
                initialization_timeout_ms,
                retry_delay_ms,
                inactivity_timeout_ms,
            )
            if context:
                logger.debug("Default context: %s", context)
            if defaults:
                logger.debug("Default configs: %s", list(defaults.keys()))
            if required:
                logger.debug("Required configs: %s", required)
        self._base_url = base_url.rstrip("/")
        self._sdk_key = sdk_key
        # Generate replaneClientId and set it as base context.
        # User-provided context values take precedence (merged on top).
        auto_generated_context: dict[str, ContextValue] = {
            REPLANE_CLIENT_ID_KEY: str(uuid.uuid4()),
        }
        self._context = {**auto_generated_context, **(context or {})}
        self._defaults = defaults or {}
        self._required = set(required or [])
        self._request_timeout = request_timeout_ms / 1000.0
        self._init_timeout = initialization_timeout_ms / 1000.0
        self._retry_delay = retry_delay_ms / 1000.0
        self._inactivity_timeout = inactivity_timeout_ms / 1000.0
        self._agent = agent or DEFAULT_AGENT

        # Config storage
        self._configs: dict[str, Config] = {}
        self._lock = threading.RLock()

        # Initialize defaults
        for name, value in self._defaults.items():
            self._configs[name] = Config(name=name, value=value)

        # Subscription callbacks
        self._all_subscribers: list[Callable[[str, Config], None]] = []
        self._config_subscribers: dict[str, list[Callable[[Config], None]]] = {}

        # Connection state
        self._closed = False
        self._initialized = threading.Event()
        self._init_error: ReplaneError | None = None
        self._stream_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def connect(self, *, wait: bool = True) -> None:
        """Connect to the Replane server and start receiving updates.

        This starts a background thread that maintains the SSE connection.

        Args:
            wait: If True, block until initial configs are loaded.

        Raises:
            ReplaneError: If connection fails or required configs are missing.
        """
        if self._closed:
            raise ClientClosedError()

        logger.debug("connect() called, wait=%s", wait)

        self._stream_thread = threading.Thread(
            target=self._run_stream,
            daemon=True,
            name="replane-sse",
        )
        self._stream_thread.start()
        logger.debug("SSE background thread started")

        if wait:
            self.wait_for_init()

    def wait_for_init(self) -> None:
        """Wait for the client to finish initialization.

        Raises:
            TimeoutError: If initialization takes too long.
            ReplaneError: If initialization fails.
        """
        if not self._initialized.wait(timeout=self._init_timeout):
            raise TimeoutError(
                f"Initialization timed out after {self._init_timeout * 1000:.0f}ms",
                timeout_ms=int(self._init_timeout * 1000),
            )

        if self._init_error:
            raise self._init_error

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
        with self._lock:
            self._all_subscribers.append(callback)

        def unsubscribe() -> None:
            with self._lock:
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
        with self._lock:
            if name not in self._config_subscribers:
                self._config_subscribers[name] = []
            self._config_subscribers[name].append(callback)

        def unsubscribe() -> None:
            with self._lock:
                if name in self._config_subscribers:
                    if callback in self._config_subscribers[name]:
                        self._config_subscribers[name].remove(callback)

        return unsubscribe

    def is_initialized(self) -> bool:
        """Check if the client has finished initialization.

        Returns:
            True if the client has received initial configs from the server.
        """
        return self._initialized.is_set()

    @property
    def configs(self) -> ConfigsT:
        """Dictionary-like accessor for configuration values.

        Provides bracket notation access to configs with override evaluation.
        When using generated TypedDict types, provides full type safety.

        Example:
            >>> config = client.configs["my-feature-flag"]
            >>> print(config["enabled"])

        Returns:
            A ConfigAccessor that behaves like a typed dictionary.
        """
        return ConfigAccessor(  # type: ignore[return-value]
            configs=self._configs,
            context=self._context,
            lock=self._lock,
            closed_check=lambda: self._closed,
        )

    def with_context(
        self,
        context: dict[str, ContextValue],
    ) -> ContextualReplane[ConfigsT]:
        """Create a contextual wrapper with additional context.

        Returns a new object that wraps this client and uses the merged context
        for all operations. The original client is unaffected.

        This is useful for creating scoped clients for specific users or requests:

        Example:
            >>> with Replane(...) as client:
            ...     # Create a scoped client for a specific user
            ...     user_client = client.with_context({
            ...         "user_id": user.id,
            ...         "plan": user.plan,
            ...     })
            ...     # All operations use the merged context
            ...     rate_limit = user_client.get("rate-limit")
            ...     settings = user_client.configs["app-settings"]

        Args:
            context: Additional context to merge with the client's default context.

        Returns:
            A ContextualReplane wrapper with the merged context.
        """
        merged_context = {**self._context, **context}
        return ContextualReplane(self, merged_context, None)

    def with_defaults(
        self,
        defaults: dict[str, Any],
    ) -> ContextualReplane[ConfigsT]:
        """Create a contextual wrapper with additional defaults.

        Returns a new object that wraps this client and uses the merged defaults
        for all operations. The original client is unaffected.

        This is useful for providing fallback values for specific use cases:

        Example:
            >>> with Replane(...) as client:
            ...     # Create a scoped client with additional defaults
            ...     safe_client = client.with_defaults({
            ...         "timeout": 30,
            ...         "max-retries": 3,
            ...     })
            ...     # Returns 30 if "timeout" is not configured
            ...     timeout = safe_client.get("timeout")

        Args:
            defaults: Additional defaults to use when configs are not found.

        Returns:
            A ContextualReplane wrapper with the additional defaults.
        """
        return ContextualReplane(self, self._context, defaults)

    def close(self) -> None:
        """Close the client and stop the SSE connection."""
        logger.debug("close() called")
        self._closed = True
        self._stop_event.set()
        if self._stream_thread and self._stream_thread.is_alive():
            logger.debug("Waiting for SSE thread to stop...")
            self._stream_thread.join(timeout=2.0)
            logger.debug("SSE thread stopped")

    def __enter__(self) -> Replane[ConfigsT]:
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _run_stream(self) -> None:
        """Background thread that maintains the SSE connection.

        During initialization: retries until init succeeds or wait_for_init times out.
        After initialization: retries indefinitely until close() is called.
        """
        retry_count = 0
        max_retries = 10

        while not self._stop_event.is_set():
            try:
                self._connect_stream()
                retry_count = 0  # Reset on successful connection
            except AuthenticationError as e:
                # Auth errors are permanent - don't retry
                if not self._initialized.is_set():
                    self._init_error = e
                    self._initialized.set()
                return

            except ReplaneError as e:
                # During init: log and retry (wait_for_init will timeout if needed)
                # After init: log and retry indefinitely
                logger.warning("SSE connection error: %s", e)

            except Exception as e:
                error = NetworkError(str(e), cause=e)
                logger.warning("SSE connection error: %s", error)

            if self._stop_event.is_set():
                break

            # Exponential backoff
            retry_count += 1
            if retry_count > max_retries:
                retry_count = max_retries

            delay = self._retry_delay * (2 ** (retry_count - 1))
            delay = min(delay, 30.0)  # Cap at 30 seconds
            logger.debug("Reconnecting in %.1f seconds...", delay)
            self._stop_event.wait(delay)

    def _connect_stream(self) -> None:
        """Establish SSE connection and process events."""
        parsed = urlparse(self._base_url)
        is_https = parsed.scheme == "https"
        host = parsed.hostname or "localhost"
        port = parsed.port or (443 if is_https else 80)

        logger.debug(
            "Connecting to SSE: host=%s, port=%d, https=%s",
            host,
            port,
            is_https,
        )

        # Use request_timeout for the initial handshake (server should respond
        # with headers within this time). After headers are received, we set
        # the socket timeout to inactivity_timeout for streaming.
        conn: http.client.HTTPConnection
        if is_https:
            context = ssl.create_default_context()
            conn = http.client.HTTPSConnection(
                host,
                port,
                timeout=self._request_timeout,
                context=context,
            )
        else:
            conn = http.client.HTTPConnection(
                host,
                port,
                timeout=self._request_timeout,
            )

        try:
            # Prepare request
            path = f"{parsed.path}/api/sdk/v1/replication/stream"
            body = json.dumps({})
            headers = {
                "Authorization": f"Bearer {self._sdk_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "Cache-Control": "no-cache",
                "User-Agent": self._agent,
            }

            logger.debug("Sending POST request to %s", path)
            conn.request("POST", path, body=body, headers=headers)
            response = conn.getresponse()
            logger.debug("Response status: %d %s", response.status, response.reason)

            if response.status == 401:
                logger.debug("Authentication failed (401)")
                raise AuthenticationError()
            elif response.status != 200:
                error_body = response.read().decode("utf-8", errors="replace")
                logger.debug("Error response body: %s", error_body[:500])
                raise from_http_status(response.status, error_body)

            logger.debug("SSE connection established, processing stream...")
            # Process SSE stream
            self._process_stream(response)

        finally:
            logger.debug("Closing HTTP connection")
            conn.close()

    def _process_stream(self, response: http.client.HTTPResponse) -> None:
        """Process SSE events from the response stream."""
        parser = SSEParser()
        last_event_time = time.monotonic()

        # Use a short socket timeout (1s) to allow checking _stop_event frequently.
        # We track elapsed time separately for the real inactivity timeout.
        socket_timeout = 1.0
        sock = response.fp.raw._sock if hasattr(response.fp, "raw") else None  # type: ignore[attr-defined]
        if sock:
            sock.settimeout(socket_timeout)

        buffer_size = 4096

        while not self._stop_event.is_set():
            try:
                # Use read1() to get available data without blocking for full buffer.
                # This is essential for SSE where data arrives in small chunks.
                # read1() returns data as soon as it's available from the socket.
                if hasattr(response.fp, "read1"):
                    chunk = response.fp.read1(buffer_size)  # type: ignore[union-attr]
                else:
                    # Default for environments where read1 isn't available
                    chunk = response.read(buffer_size)

                if not chunk:
                    logger.debug("SSE stream ended")
                    break

                last_event_time = time.monotonic()
                text = chunk.decode("utf-8", errors="replace")
                logger.debug("Received chunk: %d bytes", len(chunk))

                for event in parser.feed(text):
                    self._handle_event(event)

            except socket.timeout:
                # Check if we've exceeded the inactivity timeout
                elapsed = time.monotonic() - last_event_time
                if elapsed > self._inactivity_timeout:
                    logger.debug("SSE inactivity timeout, reconnecting...")
                    break
                # Otherwise, just loop and check _stop_event again

            except Exception as e:
                if self._stop_event.is_set():
                    break
                raise NetworkError(f"Stream read error: {e}", cause=e)

    def _handle_event(self, event: Any) -> None:
        """Handle a parsed SSE event."""
        # Event type can be in SSE 'event:' field or in data.type
        event_type = event.event
        if event_type is None and isinstance(event.data, dict):
            event_type = event.data.get("type")

        logger.debug("SSE event received: type=%s", event_type)

        if event_type == "init":
            self._handle_init(event.data)
        elif event_type == "config_change":
            self._handle_config_change(event.data)
        else:
            logger.debug("Unknown event type: %s, data=%s", event_type, event.data)

    def _handle_init(self, data: dict[str, Any]) -> None:
        """Handle the init event with all configs."""
        configs_data = data.get("configs", [])
        logger.debug("Processing init event with %d configs", len(configs_data))

        with self._lock:
            for config_data in configs_data:
                config = parse_config(config_data)
                self._configs[config.name] = config
                logger.debug(
                    "Loaded config: %s (value=%r, overrides=%d)",
                    config.name,
                    config.value,
                    len(config.overrides),
                )

            # Check required configs
            missing = self._required - set(self._configs.keys())
            if missing:
                logger.debug("Missing required configs: %s", sorted(missing))
                self._init_error = ConfigNotFoundError(
                    f"Missing required configs: {', '.join(sorted(missing))}"
                )

        self._initialized.set()
        logger.debug(
            "Initialization complete: %d configs loaded, config names: %s",
            len(self._configs),
            list(self._configs.keys()),
        )

    def _handle_config_change(self, data: dict[str, Any]) -> None:
        """Handle a config change event."""
        config_data = data.get("config", data)
        config = parse_config(config_data)

        with self._lock:
            self._configs[config.name] = config

            # Notify subscribers
            for callback in self._all_subscribers:
                try:
                    callback(config.name, config)
                except Exception as e:
                    logger.exception("Subscriber callback error: %s", e)

            if config.name in self._config_subscribers:
                for config_callback in self._config_subscribers[config.name]:
                    try:
                        config_callback(config)
                    except Exception as e:
                        logger.exception("Subscriber callback error: %s", e)

        logger.debug("Config updated: %s", config.name)
