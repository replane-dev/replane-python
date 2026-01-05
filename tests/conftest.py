"""Pytest fixtures for Replane SDK tests."""

from __future__ import annotations

import pytest

from .mock_server import MockSSEServer


@pytest.fixture
def mock_server():
    """Provide a mock SSE server for testing.

    The server is started before the test and stopped after.
    Each test gets a fresh server with reset state.

    Example:
        def test_something(mock_server):
            mock_server.send_init([{"name": "feature", "value": True}])
            replane = Replane(base_url=mock_server.url, sdk_key="test")
            replane.connect()
            assert replane.configs["feature"] is True
            replane.close()
    """
    server = MockSSEServer(port=0)  # Pick available port
    server.start()
    yield server
    # Stop the server (this will also disconnect clients)
    server.stop()


@pytest.fixture
def server_url(mock_server: MockSSEServer) -> str:
    """Provide just the URL of the mock server."""
    return mock_server.url
