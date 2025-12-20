"""Integration tests for SyncReplaneClient."""

from __future__ import annotations

import threading
import time

import pytest

from replane import SyncReplaneClient
from replane.errors import (
    AuthenticationError,
    ClientClosedError,
    ConfigNotFoundError,
    TimeoutError,
)

from .mock_server import (
    MockSSEServer,
    create_condition,
    create_config,
    create_override,
)


class TestSyncClientConnection:
    """Test connection and initialization scenarios."""

    def test_connect_and_get_config(self, mock_server: MockSSEServer):
        """Client connects, receives init event, and retrieves config."""
        mock_server.send_init([
            create_config("feature-flag", True),
            create_config("rate-limit", 100),
        ])

        client = SyncReplaneClient(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        )
        try:
            client.connect()
            assert client.is_initialized()
            assert client.get("feature-flag") is True
            assert client.get("rate-limit") == 100
        finally:
            client.close()

    def test_context_manager(self, mock_server: MockSSEServer):
        """Client works as context manager."""
        mock_server.send_init([create_config("value", 42)])

        with SyncReplaneClient(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            assert client.get("value") == 42

    def test_initialization_timeout(self, mock_server: MockSSEServer):
        """Client raises TimeoutError when init takes too long."""
        # Don't send any events - let it timeout
        client = SyncReplaneClient(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            initialization_timeout_ms=500,
        )

        with pytest.raises(TimeoutError) as exc_info:
            client.connect()

        assert "500ms" in str(exc_info.value)
        client.close()

    def test_authentication_failure(self, mock_server: MockSSEServer):
        """Client raises AuthenticationError on 401 response."""
        mock_server.set_auth_required("correct_key")

        client = SyncReplaneClient(
            base_url=mock_server.url,
            sdk_key="wrong_key",
            initialization_timeout_ms=2000,
        )

        with pytest.raises(AuthenticationError):
            client.connect()

        client.close()

    def test_authentication_success(self, mock_server: MockSSEServer):
        """Client connects successfully with correct SDK key."""
        mock_server.set_auth_required("rp_correct_key")
        mock_server.send_init([create_config("feature", True)])

        with SyncReplaneClient(
            base_url=mock_server.url,
            sdk_key="rp_correct_key",
        ) as client:
            assert client.get("feature") is True

    def test_connect_without_wait(self, mock_server: MockSSEServer):
        """Client can connect without waiting for init."""
        mock_server.send_init([create_config("feature", True)])

        client = SyncReplaneClient(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        )
        try:
            client.connect(wait=False)
            # Should not be initialized immediately
            # Wait for initialization
            client.wait_for_init()
            assert client.is_initialized()
            assert client.get("feature") is True
        finally:
            client.close()


class TestSyncClientConfigRetrieval:
    """Test config retrieval scenarios."""

    def test_get_missing_config_raises(self, mock_server: MockSSEServer):
        """Getting a missing config raises ConfigNotFoundError."""
        mock_server.send_init([create_config("existing", True)])

        with SyncReplaneClient(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            with pytest.raises(ConfigNotFoundError):
                client.get("nonexistent")

    def test_get_with_default(self, mock_server: MockSSEServer):
        """Getting a missing config with default returns the default."""
        mock_server.send_init([])

        with SyncReplaneClient(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            value = client.get("missing", default="fallback")
            assert value == "fallback"

    def test_fallback_configs(self, mock_server: MockSSEServer):
        """Fallback configs are used when server doesn't have them."""
        mock_server.send_init([create_config("from-server", "server")])

        with SyncReplaneClient(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            fallbacks={"fallback-config": "fallback-value"},
        ) as client:
            assert client.get("from-server") == "server"
            assert client.get("fallback-config") == "fallback-value"

    def test_server_overrides_fallback(self, mock_server: MockSSEServer):
        """Server config overrides fallback when present."""
        mock_server.send_init([create_config("config", "from-server")])

        with SyncReplaneClient(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            fallbacks={"config": "from-fallback"},
        ) as client:
            assert client.get("config") == "from-server"

    def test_required_configs_present(self, mock_server: MockSSEServer):
        """Required configs pass when all are present."""
        mock_server.send_init([
            create_config("required1", True),
            create_config("required2", True),
        ])

        with SyncReplaneClient(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            required=["required1", "required2"],
        ) as client:
            assert client.get("required1") is True

    def test_required_configs_missing(self, mock_server: MockSSEServer):
        """Missing required configs raises error."""
        mock_server.send_init([create_config("required1", True)])

        client = SyncReplaneClient(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            required=["required1", "required2", "required3"],
        )

        with pytest.raises(ConfigNotFoundError) as exc_info:
            client.connect()

        assert "required2" in str(exc_info.value)
        assert "required3" in str(exc_info.value)
        client.close()

    def test_closed_client_raises(self, mock_server: MockSSEServer):
        """Accessing closed client raises ClientClosedError."""
        mock_server.send_init([create_config("feature", True)])

        client = SyncReplaneClient(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        )
        client.connect()
        client.close()

        with pytest.raises(ClientClosedError):
            client.get("feature")


class TestSyncClientOverrides:
    """Test context-based override evaluation."""

    def test_context_override_evaluation(self, mock_server: MockSSEServer):
        """Override is applied when context matches."""
        mock_server.send_init([
            create_config(
                "rate-limit",
                100,
                overrides=[
                    create_override(
                        "premium-users",
                        1000,
                        [create_condition("equals", "plan", "premium")],
                    ),
                ],
            ),
        ])

        with SyncReplaneClient(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            # Default value
            assert client.get("rate-limit") == 100
            # With context that doesn't match
            assert client.get("rate-limit", context={"plan": "free"}) == 100
            # With context that matches override
            assert client.get("rate-limit", context={"plan": "premium"}) == 1000

    def test_default_context(self, mock_server: MockSSEServer):
        """Default context is applied to all gets."""
        mock_server.send_init([
            create_config(
                "feature",
                False,
                overrides=[
                    create_override(
                        "beta-users",
                        True,
                        [create_condition("equals", "beta", True)],
                    ),
                ],
            ),
        ])

        with SyncReplaneClient(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            context={"beta": True},
        ) as client:
            # Default context applied
            assert client.get("feature") is True

    def test_get_context_overrides_default(self, mock_server: MockSSEServer):
        """Context in get() overrides default context."""
        mock_server.send_init([
            create_config(
                "value",
                "default",
                overrides=[
                    create_override(
                        "region-override",
                        "eu-value",
                        [create_condition("equals", "region", "eu")],
                    ),
                    create_override(
                        "region-override-us",
                        "us-value",
                        [create_condition("equals", "region", "us")],
                    ),
                ],
            ),
        ])

        with SyncReplaneClient(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            context={"region": "eu"},
        ) as client:
            # Default context applied
            assert client.get("value") == "eu-value"
            # Override with different region
            assert client.get("value", context={"region": "us"}) == "us-value"


class TestSyncClientSubscriptions:
    """Test subscription callbacks."""

    def test_subscribe_all_configs(self, mock_server: MockSSEServer):
        """Subscribe to all config changes."""
        mock_server.send_init([create_config("feature", False)])

        changes: list[tuple[str, bool]] = []

        with SyncReplaneClient(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            def on_change(name, config):
                changes.append((name, config.value))

            client.subscribe(on_change)

            # Send a config change
            mock_server.send_config_change(create_config("feature", True))

            # Wait for the change to be processed
            time.sleep(0.3)

            assert len(changes) == 1
            assert changes[0] == ("feature", True)

    def test_subscribe_specific_config(self, mock_server: MockSSEServer):
        """Subscribe to a specific config."""
        mock_server.send_init([
            create_config("feature1", False),
            create_config("feature2", False),
        ])

        changes: list[bool] = []

        with SyncReplaneClient(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            def on_feature1_change(config):
                changes.append(config.value)

            client.subscribe_config("feature1", on_feature1_change)

            # Send changes to both configs
            mock_server.send_config_change(create_config("feature2", True))
            mock_server.send_config_change(create_config("feature1", True))

            # Wait for changes to be processed
            time.sleep(0.3)

            # Only feature1 change should be recorded
            assert len(changes) == 1
            assert changes[0] is True

    def test_unsubscribe(self, mock_server: MockSSEServer):
        """Unsubscribe stops receiving changes."""
        mock_server.send_init([create_config("feature", False)])

        changes: list[bool] = []

        with SyncReplaneClient(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            def on_change(name, config):
                changes.append(config.value)

            unsubscribe = client.subscribe(on_change)

            # First change
            mock_server.send_config_change(create_config("feature", True))
            time.sleep(0.2)

            # Unsubscribe
            unsubscribe()

            # Second change - should not be recorded
            mock_server.send_config_change(create_config("feature", False))
            time.sleep(0.2)

            assert len(changes) == 1


class TestSyncClientReconnection:
    """Test reconnection and retry behavior."""

    def test_reconnect_on_disconnect(self, mock_server: MockSSEServer):
        """Client reconnects when server disconnects."""
        mock_server.send_init([create_config("feature", True)])

        with SyncReplaneClient(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            retry_delay_ms=100,
        ) as client:
            assert client.get("feature") is True

            # Disconnect and queue new init for reconnection
            mock_server.disconnect()
            mock_server.send_init([create_config("feature", False)])

            # Wait for reconnection
            time.sleep(0.5)

            # Should have the new value after reconnect
            assert client.get("feature") is False

    def test_retry_on_server_error(self, mock_server: MockSSEServer):
        """Client retries on server error during connection."""
        # First request returns 500, second succeeds
        mock_server.set_status_code(500)

        # Queue events for the successful connection
        def send_init_after_retry():
            time.sleep(0.3)  # Wait for first request to fail
            mock_server.send_init([create_config("feature", True)])

        threading.Thread(target=send_init_after_retry, daemon=True).start()

        with SyncReplaneClient(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            retry_delay_ms=100,
            initialization_timeout_ms=3000,
        ) as client:
            assert client.get("feature") is True


class TestSyncClientJsonValues:
    """Test complex JSON values."""

    def test_object_value(self, mock_server: MockSSEServer):
        """Config can have object values."""
        mock_server.send_init([
            create_config("settings", {"theme": "dark", "fontSize": 14}),
        ])

        with SyncReplaneClient(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            settings = client.get("settings")
            assert settings == {"theme": "dark", "fontSize": 14}
            assert settings["theme"] == "dark"

    def test_array_value(self, mock_server: MockSSEServer):
        """Config can have array values."""
        mock_server.send_init([
            create_config("allowed-origins", ["example.com", "test.com"]),
        ])

        with SyncReplaneClient(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            origins = client.get("allowed-origins")
            assert origins == ["example.com", "test.com"]
            assert "example.com" in origins
