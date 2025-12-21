"""Asynchronous client implementation for the Replane Python SDK.

This module provides an async client using httpx for non-blocking operations.
Requires the 'async' extra: pip install replane[async]
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, TypeVar

from ._eval import evaluate_config
from ._sse import SSEParser
from .errors import (
    AuthenticationError,
    ClientClosedError,
    ConfigNotFoundError,
    MissingDependencyError,
    NetworkError,
    ReplaneError,
    TimeoutError,
    from_http_status,
)
from .types import Config, ContextValue, parse_config

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

T = TypeVar("T")

# Sentinel value for detecting when no default was provided
_MISSING: Any = object()

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


class AsyncReplane:
    """Asynchronous Replane client with background SSE streaming.

    This client maintains a persistent SSE connection to receive real-time
    config updates. All operations are async and non-blocking.

    Requires httpx: pip install replane[async]

    Example:
        >>> async with AsyncReplane(
        ...     base_url="https://replane.example.com",
        ...     sdk_key="sk_...",
        ... ) as client:
        ...     value = client.get("feature-flag")

    Or with manual lifecycle:
        >>> client = AsyncReplane(...)
        >>> await client.connect()
        >>> value = client.get("feature-flag")
        >>> await client.close()
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
        """Initialize the async Replane client.

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

        Raises:
            MissingDependencyError: If httpx is not installed.
        """
        if httpx is None:
            raise MissingDependencyError("httpx", "async client")

        # Configure debug logging
        self._debug = debug
        if debug:
            _setup_debug_logging()
            logger.debug(
                "Initializing AsyncReplane: base_url=%s, "
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
        self._lock = asyncio.Lock()

        # Initialize fallbacks
        for name, value in self._fallbacks.items():
            self._configs[name] = Config(name=name, value=value)

        # Subscription callbacks
        self._all_subscribers: list[Callable[[str, Config], None | Awaitable[None]]] = []
        self._config_subscribers: dict[str, list[Callable[[Config], None | Awaitable[None]]]] = {}

        # Connection state
        self._closed = False
        self._initialized = asyncio.Event()
        self._init_error: ReplaneError | None = None
        self._stream_task: asyncio.Task[None] | None = None
        self._http_client: httpx.AsyncClient | None = None

    async def connect(self, *, wait: bool = True) -> None:
        """Connect to the Replane server and start receiving updates.

        This starts a background task that maintains the SSE connection.

        Args:
            wait: If True, wait until initial configs are loaded.

        Raises:
            ReplaneError: If connection fails or required configs are missing.
        """
        if self._closed:
            raise ClientClosedError()

        logger.debug("connect() called, wait=%s", wait)

        # Use request_timeout for the handshake (server should respond quickly).
        # read=None means no read timeout (for SSE streaming).
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._request_timeout, read=None),
        )

        self._stream_task = asyncio.create_task(
            self._run_stream(),
            name="replane-sse",
        )
        logger.debug("SSE background task started")

        if wait:
            await self.wait_for_init()

    async def wait_for_init(self) -> None:
        """Wait for the client to finish initialization.

        Raises:
            TimeoutError: If initialization takes too long.
            ReplaneError: If initialization fails.
        """
        try:
            await asyncio.wait_for(
                self._initialized.wait(),
                timeout=self._init_timeout,
            )
        except asyncio.TimeoutError:
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
        default: T = _MISSING,
    ) -> Any:
        """Get a config value.

        This is a synchronous read from the local cache. Override evaluation
        happens locally using the provided context.

        Note: This method is intentionally sync since it only reads from
        the local cache and doesn't perform any I/O.

        Args:
            name: Config name to retrieve.
            context: Context for override evaluation (merged with default).
            default: Default value if config doesn't exist (can be None).

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

        if name not in self._configs:
            if default is not _MISSING:
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
        callback: Callable[[str, Config], None | Awaitable[None]],
    ) -> Callable[[], None]:
        """Subscribe to all config changes.

        The callback can be sync or async.

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
        callback: Callable[[Config], None | Awaitable[None]],
    ) -> Callable[[], None]:
        """Subscribe to changes for a specific config.

        The callback can be sync or async.

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

    def is_initialized(self) -> bool:
        """Check if the client has finished initialization.

        Returns:
            True if the client has received initial configs from the server.
        """
        return self._initialized.is_set()

    async def close(self) -> None:
        """Close the client and stop the SSE connection."""
        logger.debug("close() called")
        self._closed = True

        if self._stream_task:
            logger.debug("Cancelling SSE task...")
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass
            logger.debug("SSE task cancelled")

        if self._http_client:
            logger.debug("Closing HTTP client...")
            await self._http_client.aclose()
            logger.debug("HTTP client closed")

    async def __aenter__(self) -> AsyncReplane:
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def _run_stream(self) -> None:
        """Background task that maintains the SSE connection.

        During initialization: retries until init succeeds or wait_for_init times out.
        After initialization: retries indefinitely until close() is called.
        """
        retry_count = 0
        max_retries = 10

        while not self._closed:
            try:
                await self._connect_stream()
                retry_count = 0
            except asyncio.CancelledError:
                break
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

            if self._closed:
                break

            # Exponential backoff
            retry_count += 1
            if retry_count > max_retries:
                retry_count = max_retries

            delay = self._retry_delay * (2 ** (retry_count - 1))
            delay = min(delay, 30.0)
            logger.debug("Reconnecting in %.1f seconds...", delay)

            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                break

    async def _connect_stream(self) -> None:
        """Establish SSE connection and process events."""
        if not self._http_client:
            raise ClientClosedError()

        url = f"{self._base_url}/api/sdk/v1/replication/stream"
        headers = {
            "Authorization": f"Bearer {self._sdk_key}",
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
        }

        logger.debug("Connecting to SSE: %s", url)

        async with self._http_client.stream(
            "POST",
            url,
            json={},
            headers=headers,
        ) as response:
            logger.debug("Response status: %d", response.status_code)
            if response.status_code == 401:
                logger.debug("Authentication failed (401)")
                raise AuthenticationError()
            elif response.status_code != 200:
                body = await response.aread()
                logger.debug("Error response body: %s", body[:500])
                raise from_http_status(
                    response.status_code,
                    body.decode("utf-8", errors="replace"),
                )

            logger.debug("SSE connection established, processing stream...")
            await self._process_stream(response)

    async def _process_stream(self, response: httpx.Response) -> None:
        """Process SSE events from the response stream."""
        parser = SSEParser()
        iterator = response.aiter_text().__aiter__()

        loop = asyncio.get_running_loop()
        last_event_time = loop.time()

        # Use a short timeout (1s) to allow checking _closed frequently.
        # We track elapsed time separately for the real inactivity timeout.
        check_timeout = 1.0

        while not self._closed:
            try:
                chunk = await asyncio.wait_for(
                    iterator.__anext__(),
                    timeout=check_timeout,
                )
                last_event_time = loop.time()
            except asyncio.TimeoutError:
                # Check if we've exceeded the inactivity timeout
                elapsed = loop.time() - last_event_time
                if elapsed > self._inactivity_timeout:
                    logger.debug("SSE inactivity timeout, reconnecting...")
                    break
                # Otherwise, just loop and check _closed again
                continue
            except StopAsyncIteration:
                logger.debug("SSE stream ended")
                break

            for event in parser.feed(chunk):
                await self._handle_event(event)

    async def _handle_event(self, event: Any) -> None:
        """Handle a parsed SSE event."""
        # Event type can be in SSE 'event:' field or in data.type
        event_type = event.event
        if event_type is None and isinstance(event.data, dict):
            event_type = event.data.get("type")

        logger.debug("SSE event received: type=%s", event_type)

        if event_type == "init":
            await self._handle_init(event.data)
        elif event_type == "config_change":
            await self._handle_config_change(event.data)
        else:
            logger.debug("Unknown event type: %s, data=%s", event_type, event.data)

    async def _handle_init(self, data: dict[str, Any]) -> None:
        """Handle the init event with all configs."""
        configs_data = data.get("configs", [])
        logger.debug("Processing init event with %d configs", len(configs_data))

        async with self._lock:
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

    async def _handle_config_change(self, data: dict[str, Any]) -> None:
        """Handle a config change event."""
        config_data = data.get("config", data)
        config = parse_config(config_data)

        async with self._lock:
            self._configs[config.name] = config

        # Notify subscribers (outside lock to avoid deadlocks)
        for callback in self._all_subscribers:
            try:
                result = callback(config.name, config)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.exception("Subscriber callback error: %s", e)

        if config.name in self._config_subscribers:
            for config_callback in self._config_subscribers[config.name]:
                try:
                    result = config_callback(config)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.exception("Subscriber callback error: %s", e)

        logger.debug("Config updated: %s", config.name)
