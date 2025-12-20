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

logger = logging.getLogger("replane")


class AsyncReplaneClient:
    """Asynchronous Replane client with background SSE streaming.

    This client maintains a persistent SSE connection to receive real-time
    config updates. All operations are async and non-blocking.

    Requires httpx: pip install replane[async]

    Example:
        >>> async with AsyncReplaneClient(
        ...     base_url="https://replane.example.com",
        ...     sdk_key="sk_...",
        ... ) as client:
        ...     value = client.get("feature-flag")

    Or with manual lifecycle:
        >>> client = AsyncReplaneClient(...)
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

        Raises:
            MissingDependencyError: If httpx is not installed.
        """
        if httpx is None:
            raise MissingDependencyError("httpx", "async client")

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

        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._request_timeout, read=None),
        )

        self._stream_task = asyncio.create_task(
            self._run_stream(),
            name="replane-sse",
        )

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
        default: T | None = None,
    ) -> Any:
        """Get a config value.

        This is a synchronous read from the local cache. Override evaluation
        happens locally using the provided context.

        Note: This method is intentionally sync since it only reads from
        the local cache and doesn't perform any I/O.

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

    async def close(self) -> None:
        """Close the client and stop the SSE connection."""
        self._closed = True

        if self._stream_task:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass

        if self._http_client:
            await self._http_client.aclose()

    async def __aenter__(self) -> AsyncReplaneClient:
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def _run_stream(self) -> None:
        """Background task that maintains the SSE connection."""
        retry_count = 0
        max_retries = 10

        while not self._closed:
            try:
                await self._connect_stream()
                retry_count = 0
            except asyncio.CancelledError:
                break
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

        async with self._http_client.stream(
            "POST",
            url,
            json={},
            headers=headers,
        ) as response:
            if response.status_code == 401:
                raise AuthenticationError()
            elif response.status_code != 200:
                body = await response.aread()
                raise from_http_status(
                    response.status_code,
                    body.decode("utf-8", errors="replace"),
                )

            await self._process_stream(response)

    async def _process_stream(self, response: httpx.Response) -> None:
        """Process SSE events from the response stream."""
        parser = SSEParser()

        async for chunk in response.aiter_text():
            if self._closed:
                break

            for event in parser.feed(chunk):
                await self._handle_event(event)

    async def _handle_event(self, event: Any) -> None:
        """Handle a parsed SSE event."""
        if event.event == "init":
            await self._handle_init(event.data)
        elif event.event == "config_change":
            await self._handle_config_change(event.data)

    async def _handle_init(self, data: dict[str, Any]) -> None:
        """Handle the init event with all configs."""
        configs_data = data.get("configs", [])

        async with self._lock:
            for config_data in configs_data:
                config = parse_config(config_data)
                self._configs[config.name] = config

            # Check required configs
            missing = self._required - set(self._configs.keys())
            if missing:
                self._init_error = ConfigNotFoundError(
                    f"Missing required configs: {', '.join(sorted(missing))}"
                )

        self._initialized.set()
        logger.debug("Initialized with %d configs", len(configs_data))

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
