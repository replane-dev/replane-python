"""Mock SSE server for integration testing.

This module provides a controllable HTTP server that simulates a Replane server
for testing the SDK clients without requiring a real server.
"""

from __future__ import annotations

import json
import queue
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from typing import Any


class MockSSEHandler(BaseHTTPRequestHandler):
    """HTTP request handler for mock SSE server."""

    # Disable logging to stderr during tests
    def log_message(self, format: str, *args: Any) -> None:
        pass

    def do_POST(self) -> None:
        """Handle POST requests to the SSE endpoint."""
        server: MockSSEServer = self.server  # type: ignore

        # Check path
        if not self.path.endswith("/api/sdk/v1/replication/stream"):
            self.send_error(404, "Not Found")
            return

        # Check authentication
        auth_header = self.headers.get("Authorization", "")
        if server.required_sdk_key:
            expected = f"Bearer {server.required_sdk_key}"
            if auth_header != expected:
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error": "Unauthorized"}')
                return

        # Check for forced status code
        if server.next_status_code != 200:
            status = server.next_status_code
            server.next_status_code = 200  # Reset for next request
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Status {status}"}).encode())
            return

        # Apply delay if configured
        if server.response_delay > 0:
            delay = server.response_delay
            server.response_delay = 0  # Reset for next request
            time.sleep(delay)

        # Send SSE response headers
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        # Track this connection
        server.active_connections += 1
        server.connection_event.set()

        try:
            # Stream events from the queue
            while not server.should_stop:
                # Check for disconnect signal
                if server.should_disconnect:
                    server.should_disconnect = False
                    break

                try:
                    event = server.events_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                # Format and send SSE event
                event_type = event.get("type", "message")
                data = event.get("data", {})

                sse_message = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
                try:
                    self.wfile.write(sse_message.encode())
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    break

        finally:
            server.active_connections -= 1


class MockSSEServer(ThreadingHTTPServer):
    """Controllable HTTP server for testing SSE clients.

    Example:
        >>> server = MockSSEServer()
        >>> server.start()
        >>> # Queue events before client connects
        >>> server.send_init([{"name": "feature", "value": True}])
        >>> # ... run client tests ...
        >>> server.stop()
    """

    # Use daemon threads so they don't block shutdown
    daemon_threads = True

    def __init__(self, port: int = 0):
        """Initialize the mock server.

        Args:
            port: Port to listen on. Use 0 to pick an available port.
        """
        # Allow address reuse to avoid "Address already in use" errors
        socketserver.TCPServer.allow_reuse_address = True

        super().__init__(("127.0.0.1", port), MockSSEHandler)

        self.events_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self.next_status_code = 200
        self.response_delay = 0.0
        self.should_disconnect = False
        self.should_stop = False
        self.required_sdk_key: str | None = None

        # Connection tracking
        self.active_connections = 0
        self.connection_event = threading.Event()

        # Server thread
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        """Get the actual port the server is listening on."""
        return self.server_address[1]

    @property
    def url(self) -> str:
        """Get the base URL for connecting to this server."""
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        """Start the server in a background thread."""
        self.should_stop = False
        self._thread = threading.Thread(
            target=self.serve_forever,
            daemon=True,
            name="mock-sse-server",
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop the server and wait for it to finish."""
        self.should_stop = True
        self.should_disconnect = True  # Force active handlers to exit
        self.shutdown()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def reset(self) -> None:
        """Reset server state for a new test."""
        # Clear event queue
        while not self.events_queue.empty():
            try:
                self.events_queue.get_nowait()
            except queue.Empty:
                break

        self.next_status_code = 200
        self.response_delay = 0.0
        self.should_disconnect = False
        self.required_sdk_key = None
        self.connection_event.clear()

    def wait_for_connection(self, timeout: float = 5.0) -> bool:
        """Wait for a client to connect.

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            True if a connection was made, False if timeout.
        """
        return self.connection_event.wait(timeout=timeout)

    def send_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Queue an SSE event to be sent to connected clients.

        Args:
            event_type: The SSE event type (e.g., "init", "config_change").
            data: The event data to send as JSON.
        """
        self.events_queue.put({"type": event_type, "data": data})

    def send_init(self, configs: list[dict[str, Any]]) -> None:
        """Send an init event with the given configs.

        Args:
            configs: List of config objects with name, value, and optional overrides.
        """
        self.send_event("init", {"type": "init", "configs": configs})

    def send_config_change(self, config: dict[str, Any]) -> None:
        """Send a config change event.

        Args:
            config: Config object with name, value, and optional overrides.
        """
        self.send_event("config_change", {"type": "config_change", "config": config})

    def set_status_code(self, code: int) -> None:
        """Set the HTTP status code for the next request.

        Args:
            code: HTTP status code (e.g., 401, 500).
        """
        self.next_status_code = code

    def set_delay(self, seconds: float) -> None:
        """Set a delay before responding to the next request.

        Args:
            seconds: Delay in seconds.
        """
        self.response_delay = seconds

    def disconnect(self) -> None:
        """Force disconnect the current SSE stream."""
        self.should_disconnect = True

    def set_auth_required(self, sdk_key: str) -> None:
        """Require a specific SDK key for authentication.

        Args:
            sdk_key: The SDK key to require.
        """
        self.required_sdk_key = sdk_key


def create_config(
    name: str,
    value: Any,
    overrides: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Helper to create a config object for testing.

    Args:
        name: Config name.
        value: Config value.
        overrides: Optional list of override rules.

    Returns:
        A config dict ready to send via SSE.
    """
    config: dict[str, Any] = {"name": name, "value": value}
    if overrides:
        config["overrides"] = overrides
    return config


def create_override(
    name: str,
    value: Any,
    conditions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Helper to create an override rule for testing.

    Args:
        name: Override name.
        value: Value when override matches.
        conditions: List of condition objects.

    Returns:
        An override dict.
    """
    return {"name": name, "value": value, "conditions": conditions}


def create_condition(
    operator: str,
    property: str,
    value: Any,
) -> dict[str, Any]:
    """Helper to create a condition for testing.

    Args:
        operator: Condition operator (e.g., "equals", "in").
        property: Context property to check.
        value: Expected value.

    Returns:
        A condition dict.
    """
    return {"operator": operator, "property": property, "value": value}
