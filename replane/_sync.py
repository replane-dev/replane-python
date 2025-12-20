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
from typing import Any, Callable, TypeVar
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

T = TypeVar("T")

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


class SyncReplaneClient:
    """Synchronous Replane client with background SSE streaming.

    This client maintains a persistent SSE connection to receive real-time
    config updates. Config reads are synchronous and return immediately
    from the local cache.

    Example:
        >>> client = SyncReplaneClient(
        ...     base_url="https://replane.example.com",
        ...     sdk_key="sk_...",
        ... )
        >>> client.connect()
        >>> value = client.get("feature-flag")
        >>> client.close()

    For simpler usage, prefer the context manager:
        >>> with SyncReplaneClient(...) as client:
        ...     value = client.get("feature-flag")
    """

    def __init__(
        self,
        base_url: str,
        sdk_key: str,
        *,
        context: dict[str, ContextValue] | None = None,
        fallbacks: dict[str, Any] | None = None,
        required: list[str] | None = None,
        request_timeout_ms: int = 2000,
        initialization_timeout_ms: int = 5000,
        retry_delay_ms: int = 200,
        inactivity_timeout_ms: int = 30000,
        debug: bool = False,
    ) -> None:
        """Initialize the Replane client.

        Args:
            base_url: Base URL of the Replane server.
            sdk_key: SDK key for authentication.
            context: Default context for override evaluation.
            fallbacks: Fallback values for configs if not loaded from server.
            required: List of config names that must be present on init.
            request_timeout_ms: Timeout for HTTP requests in milliseconds.
            initialization_timeout_ms: Timeout for initial connection.
            retry_delay_ms: Initial delay between retries.
            inactivity_timeout_ms: Max time without SSE events before reconnect.
            debug: Enable debug logging to see all client activity.
        """
        # Configure debug logging
        self._debug = debug
        if debug:
            _setup_debug_logging()
            logger.debug(
                "Initializing SyncReplaneClient: base_url=%s, "
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
            if fallbacks:
                logger.debug("Fallback configs: %s", list(fallbacks.keys()))
            if required:
                logger.debug("Required configs: %s", required)
        self._base_url = base_url.rstrip("/")
        self._sdk_key = sdk_key
        self._context = context or {}
        self._fallbacks = fallbacks or {}
        self._required = set(required or [])
        self._request_timeout = request_timeout_ms / 1000.0
        self._init_timeout = initialization_timeout_ms / 1000.0
        self._retry_delay = retry_delay_ms / 1000.0
        self._inactivity_timeout = inactivity_timeout_ms / 1000.0

        # Config storage
        self._configs: dict[str, Config] = {}
        self._lock = threading.RLock()

        # Initialize fallbacks
        for name, value in self._fallbacks.items():
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

    def get(
        self,
        name: str,
        *,
        context: dict[str, ContextValue] | None = None,
        default: T | None = None,
    ) -> Any:
        """Get a config value.

        This is a synchronous read from the local cache. Override evaluation
        happens locally using the provided context.

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
        logger.debug("get(%r) with context: %s", name, merged_context or "(none)")

        with self._lock:
            if name not in self._configs:
                if default is not None:
                    logger.debug("Config %r not found, returning default: %r", name, default)
                    return default
                logger.debug("Config %r not found, no default provided", name)
                raise ConfigNotFoundError(name)

            config = self._configs[name]
            result = evaluate_config(config, merged_context)
            logger.debug(
                "Config %r: base_value=%r, overrides=%d, result=%r",
                name,
                config.value,
                len(config.overrides),
                result,
            )
            return result

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

    def close(self) -> None:
        """Close the client and stop the SSE connection."""
        logger.debug("close() called")
        self._closed = True
        self._stop_event.set()
        if self._stream_thread and self._stream_thread.is_alive():
            logger.debug("Waiting for SSE thread to stop...")
            self._stream_thread.join(timeout=2.0)
            logger.debug("SSE thread stopped")

    def __enter__(self) -> SyncReplaneClient:
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _run_stream(self) -> None:
        """Background thread that maintains the SSE connection."""
        retry_count = 0
        max_retries = 10

        while not self._stop_event.is_set():
            try:
                self._connect_stream()
                retry_count = 0  # Reset on successful connection
            except ReplaneError as e:
                if not self._initialized.is_set():
                    self._init_error = e
                    self._initialized.set()
                    return

                logger.warning("SSE connection error: %s", e)

            except Exception as e:
                error = NetworkError(str(e), cause=e)
                if not self._initialized.is_set():
                    self._init_error = error
                    self._initialized.set()
                    return

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

        # Create connection
        # Note: SSE connections are long-lived, so we use the inactivity timeout
        # rather than the short request timeout. The inactivity timeout is used
        # for detecting dead connections during streaming.
        conn: http.client.HTTPConnection
        if is_https:
            context = ssl.create_default_context()
            conn = http.client.HTTPSConnection(
                host,
                port,
                timeout=self._inactivity_timeout,
                context=context,
            )
        else:
            conn = http.client.HTTPConnection(
                host,
                port,
                timeout=self._inactivity_timeout,
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

        # Set socket timeout for inactivity detection
        # Access internal socket for timeout - implementation detail
        sock = response.fp.raw._sock if hasattr(response.fp, "raw") else None  # type: ignore[attr-defined]
        if sock:
            sock.settimeout(self._inactivity_timeout)

        buffer_size = 4096

        while not self._stop_event.is_set():
            try:
                chunk = response.read(buffer_size)
                if not chunk:
                    logger.debug("SSE stream ended")
                    break

                last_event_time = time.monotonic()
                text = chunk.decode("utf-8", errors="replace")

                for event in parser.feed(text):
                    self._handle_event(event)

            except socket.timeout:
                elapsed = time.monotonic() - last_event_time
                if elapsed > self._inactivity_timeout:
                    logger.debug("SSE inactivity timeout, reconnecting...")
                    break

            except Exception as e:
                if self._stop_event.is_set():
                    break
                raise NetworkError(f"Stream read error: {e}", cause=e)

    def _handle_event(self, event: Any) -> None:
        """Handle a parsed SSE event."""
        logger.debug("SSE event received: type=%s", event.event)
        if event.event == "init":
            self._handle_init(event.data)
        elif event.event == "config_change":
            self._handle_config_change(event.data)
        else:
            logger.debug("Unknown event type: %s, data=%s", event.event, event.data)

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
