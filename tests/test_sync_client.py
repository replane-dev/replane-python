"""Integration tests for Replane."""

from __future__ import annotations

import threading
import time

import pytest

from replane import Replane
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
        mock_server.send_init(
            [
                create_config("feature-flag", True),
                create_config("rate-limit", 100),
            ]
        )

        client = Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        )
        try:
            client.connect()
            assert client.is_initialized()
            assert client.configs["feature-flag"] is True
            assert client.configs["rate-limit"] == 100
        finally:
            client.close()

    def test_context_manager(self, mock_server: MockSSEServer):
        """Client works as context manager."""
        mock_server.send_init([create_config("value", 42)])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            assert client.configs["value"] == 42

    def test_initialization_timeout(self, mock_server: MockSSEServer):
        """Client raises TimeoutError when init takes too long."""
        # Don't send any events - let it timeout
        client = Replane(
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

        client = Replane(
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

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_correct_key",
        ) as client:
            assert client.configs["feature"] is True

    def test_connect_without_wait(self, mock_server: MockSSEServer):
        """Client can connect without waiting for init."""
        mock_server.send_init([create_config("feature", True)])

        client = Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        )
        try:
            client.connect(wait=False)
            # Should not be initialized immediately
            # Wait for initialization
            client.wait_for_init()
            assert client.is_initialized()
            assert client.configs["feature"] is True
        finally:
            client.close()


class TestSyncClientConfigRetrieval:
    """Test config retrieval scenarios."""

    def test_get_missing_config_raises(self, mock_server: MockSSEServer):
        """Getting a missing config raises KeyError."""
        mock_server.send_init([create_config("existing", True)])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            with pytest.raises(KeyError):
                client.configs["nonexistent"]

    def test_get_with_default(self, mock_server: MockSSEServer):
        """Getting a missing config with default returns the default."""
        mock_server.send_init([])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            value = client.configs.get("missing", "fallback")
            assert value == "fallback"

    def test_get_with_none_default(self, mock_server: MockSSEServer):
        """Getting a missing config with default=None returns None."""
        mock_server.send_init([])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            value = client.configs.get("missing", None)
            assert value is None

    def test_get_with_false_default(self, mock_server: MockSSEServer):
        """Getting a missing config with default=False returns False."""
        mock_server.send_init([])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            value = client.configs.get("missing", False)
            assert value is False

    def test_get_with_zero_default(self, mock_server: MockSSEServer):
        """Getting a missing config with default=0 returns 0."""
        mock_server.send_init([])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            value = client.configs.get("missing", 0)
            assert value == 0

    def test_fallback_configs(self, mock_server: MockSSEServer):
        """Fallback configs are used when server doesn't have them."""
        mock_server.send_init([create_config("from-server", "server")])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            defaults={"fallback-config": "fallback-value"},
        ) as client:
            assert client.configs["from-server"] == "server"
            assert client.configs["fallback-config"] == "fallback-value"

    def test_server_overrides_fallback(self, mock_server: MockSSEServer):
        """Server config overrides fallback when present."""
        mock_server.send_init([create_config("config", "from-server")])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            defaults={"config": "from-fallback"},
        ) as client:
            assert client.configs["config"] == "from-server"

    def test_required_configs_present(self, mock_server: MockSSEServer):
        """Required configs pass when all are present."""
        mock_server.send_init(
            [
                create_config("required1", True),
                create_config("required2", True),
            ]
        )

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            required=["required1", "required2"],
        ) as client:
            assert client.configs["required1"] is True

    def test_required_configs_missing(self, mock_server: MockSSEServer):
        """Missing required configs raises error."""
        mock_server.send_init([create_config("required1", True)])

        client = Replane(
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

        client = Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        )
        client.connect()
        client.close()

        with pytest.raises(ClientClosedError):
            client.configs["feature"]


class TestSyncClientOverrides:
    """Test context-based override evaluation."""

    def test_context_override_evaluation(self, mock_server: MockSSEServer):
        """Override is applied when context matches."""
        mock_server.send_init(
            [
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
            ]
        )

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            # Default value
            assert client.configs["rate-limit"] == 100
            # With context that doesn't match
            assert client.with_context({"plan": "free"}).configs["rate-limit"] == 100
            # With context that matches override
            assert client.with_context({"plan": "premium"}).configs["rate-limit"] == 1000

    def test_default_context(self, mock_server: MockSSEServer):
        """Default context is applied to all gets."""
        mock_server.send_init(
            [
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
            ]
        )

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            context={"beta": True},
        ) as client:
            # Default context applied
            assert client.configs["feature"] is True

    def test_get_context_overrides_default(self, mock_server: MockSSEServer):
        """Context in get() overrides default context."""
        mock_server.send_init(
            [
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
            ]
        )

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            context={"region": "eu"},
        ) as client:
            # Default context applied
            assert client.configs["value"] == "eu-value"
            # Override with different region
            assert client.with_context({"region": "us"}).configs["value"] == "us-value"


class TestSyncClientSubscriptions:
    """Test subscription callbacks."""

    def test_subscribe_all_configs(self, mock_server: MockSSEServer):
        """Subscribe to all config changes."""
        mock_server.send_init([create_config("feature", False)])

        changes: list[tuple[str, bool]] = []

        with Replane(
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
        mock_server.send_init(
            [
                create_config("feature1", False),
                create_config("feature2", False),
            ]
        )

        changes: list[bool] = []

        with Replane(
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

        with Replane(
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

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            retry_delay_ms=100,
        ) as client:
            assert client.configs["feature"] is True

            # Disconnect and queue new init for reconnection
            mock_server.disconnect()
            mock_server.send_init([create_config("feature", False)])

            # Wait for reconnection
            time.sleep(0.5)

            # Should have the new value after reconnect
            assert client.configs["feature"] is False

    def test_retry_on_server_error(self, mock_server: MockSSEServer):
        """Client retries on server error during connection."""
        # First request returns 500, second succeeds
        mock_server.set_status_code(500)

        # Queue events for the successful connection
        def send_init_after_retry():
            time.sleep(0.3)  # Wait for first request to fail
            mock_server.send_init([create_config("feature", True)])

        threading.Thread(target=send_init_after_retry, daemon=True).start()

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            retry_delay_ms=100,
            initialization_timeout_ms=3000,
        ) as client:
            assert client.configs["feature"] is True


class TestSyncClientJsonValues:
    """Test complex JSON values."""

    def test_object_value(self, mock_server: MockSSEServer):
        """Config can have object values."""
        mock_server.send_init(
            [
                create_config("settings", {"theme": "dark", "fontSize": 14}),
            ]
        )

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            settings = client.configs["settings"]
            assert settings == {"theme": "dark", "fontSize": 14}
            assert settings["theme"] == "dark"

    def test_array_value(self, mock_server: MockSSEServer):
        """Config can have array values."""
        mock_server.send_init(
            [
                create_config("allowed-origins", ["example.com", "test.com"]),
            ]
        )

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            origins = client.configs["allowed-origins"]
            assert origins == ["example.com", "test.com"]
            assert "example.com" in origins


class TestSyncClientConnectionEdgeCases:
    """Test connection edge cases."""

    def test_connect_on_already_closed_client(self, mock_server: MockSSEServer):
        """Connecting a closed client raises error."""
        mock_server.send_init([create_config("feature", True)])

        client = Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        )
        client.close()

        with pytest.raises(ClientClosedError):
            client.connect()

    def test_close_twice_is_safe(self, mock_server: MockSSEServer):
        """Calling close() twice doesn't raise."""
        mock_server.send_init([create_config("feature", True)])

        client = Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        )
        client.connect()
        client.close()
        client.close()  # Should not raise

    def test_close_without_connect_is_safe(self, mock_server: MockSSEServer):
        """Calling close() without connect() doesn't raise."""
        client = Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        )
        client.close()  # Should not raise

    def test_is_initialized_before_connect(self, mock_server: MockSSEServer):
        """is_initialized() returns False before connect."""
        client = Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        )
        assert client.is_initialized() is False
        client.close()

    def test_empty_init_event(self, mock_server: MockSSEServer):
        """Client handles empty init event (no configs)."""
        mock_server.send_init([])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            assert client.is_initialized()
            # All gets should fail since no configs
            with pytest.raises(KeyError):
                client.configs["any-config"]

    def test_many_configs_in_init(self, mock_server: MockSSEServer):
        """Client handles many configs in init event."""
        configs = [create_config(f"config-{i}", i) for i in range(100)]
        mock_server.send_init(configs)

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            for i in range(100):
                assert client.configs[f"config-{i}"] == i

    def test_server_delay_within_timeout(self, mock_server: MockSSEServer):
        """Client succeeds when server responds within timeout."""
        mock_server.set_delay(0.5)  # 500ms delay
        mock_server.send_init([create_config("feature", True)])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            initialization_timeout_ms=3000,
        ) as client:
            assert client.configs["feature"] is True


class TestSyncClientConfigValueEdgeCases:
    """Test edge cases for config values."""

    def test_null_value(self, mock_server: MockSSEServer):
        """Config with null value."""
        mock_server.send_init([create_config("nullable", None)])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            assert client.configs["nullable"] is None

    def test_empty_string_value(self, mock_server: MockSSEServer):
        """Config with empty string value."""
        mock_server.send_init([create_config("empty", "")])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            assert client.configs["empty"] == ""

    def test_zero_value(self, mock_server: MockSSEServer):
        """Config with zero value (falsy but valid)."""
        mock_server.send_init([create_config("zero", 0)])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            assert client.configs["zero"] == 0

    def test_false_value(self, mock_server: MockSSEServer):
        """Config with false value (falsy but valid)."""
        mock_server.send_init([create_config("disabled", False)])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            assert client.configs["disabled"] is False

    def test_unicode_value(self, mock_server: MockSSEServer):
        """Config with unicode characters."""
        mock_server.send_init(
            [
                create_config("greeting", "Hello, 世界! 🌍"),
                create_config("emoji", "🚀🎉✨"),
            ]
        )

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            assert client.configs["greeting"] == "Hello, 世界! 🌍"
            assert client.configs["emoji"] == "🚀🎉✨"

    def test_special_characters_in_name(self, mock_server: MockSSEServer):
        """Config names with special characters."""
        mock_server.send_init(
            [
                create_config("config-with-dashes", 1),
                create_config("config_with_underscores", 2),
                create_config("config.with.dots", 3),
                create_config("config:with:colons", 4),
            ]
        )

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            assert client.configs["config-with-dashes"] == 1
            assert client.configs["config_with_underscores"] == 2
            assert client.configs["config.with.dots"] == 3
            assert client.configs["config:with:colons"] == 4

    def test_float_value(self, mock_server: MockSSEServer):
        """Config with float value."""
        mock_server.send_init([create_config("ratio", 3.14159)])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            assert abs(client.configs["ratio"] - 3.14159) < 0.0001

    def test_negative_number(self, mock_server: MockSSEServer):
        """Config with negative number."""
        mock_server.send_init([create_config("offset", -42)])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            assert client.configs["offset"] == -42

    def test_large_string_value(self, mock_server: MockSSEServer):
        """Config with large string value."""
        large_value = "x" * 10000
        mock_server.send_init([create_config("large", large_value)])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            assert client.configs["large"] == large_value
            assert len(client.configs["large"]) == 10000

    def test_nested_object_value(self, mock_server: MockSSEServer):
        """Config with deeply nested object."""
        nested = {"level1": {"level2": {"level3": {"value": "deep"}}}}
        mock_server.send_init([create_config("nested", nested)])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            result = client.configs["nested"]
            assert result["level1"]["level2"]["level3"]["value"] == "deep"

    def test_mixed_array_value(self, mock_server: MockSSEServer):
        """Config with array of mixed types."""
        mixed = [1, "two", True, None, {"key": "value"}, [1, 2, 3]]
        mock_server.send_init([create_config("mixed", mixed)])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            result = client.configs["mixed"]
            assert result == mixed


class TestSyncClientOverrideEdgeCases:
    """Test edge cases for override evaluation."""

    def test_multiple_overrides_first_match_wins(self, mock_server: MockSSEServer):
        """First matching override wins."""
        mock_server.send_init(
            [
                create_config(
                    "value",
                    "default",
                    overrides=[
                        create_override(
                            "first",
                            "first-value",
                            [
                                create_condition("equals", "tier", "premium"),
                            ],
                        ),
                        create_override(
                            "second",
                            "second-value",
                            [
                                create_condition("equals", "tier", "premium"),
                            ],
                        ),
                    ],
                ),
            ]
        )

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            # First override should win
            assert client.with_context({"tier": "premium"}).configs["value"] == "first-value"

    def test_override_with_in_operator(self, mock_server: MockSSEServer):
        """Override using 'in' operator."""
        mock_server.send_init(
            [
                create_config(
                    "feature",
                    False,
                    overrides=[
                        create_override(
                            "vip-users",
                            True,
                            [
                                {
                                    "operator": "in",
                                    "property": "plan",
                                    "value": ["pro", "enterprise"],
                                },
                            ],
                        ),
                    ],
                ),
            ]
        )

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            assert client.with_context({"plan": "free"}).configs["feature"] is False
            assert client.with_context({"plan": "pro"}).configs["feature"] is True
            assert client.with_context({"plan": "enterprise"}).configs["feature"] is True

    def test_override_with_not_in_operator(self, mock_server: MockSSEServer):
        """Override using 'not_in' operator."""
        mock_server.send_init(
            [
                create_config(
                    "restricted",
                    False,
                    overrides=[
                        create_override(
                            "non-blocked",
                            True,
                            [
                                {
                                    "operator": "not_in",
                                    "property": "country",
                                    "value": ["XX", "YY"],
                                },
                            ],
                        ),
                    ],
                ),
            ]
        )

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            assert client.with_context({"country": "XX"}).configs["restricted"] is False
            assert client.with_context({"country": "US"}).configs["restricted"] is True

    def test_override_with_numeric_comparison(self, mock_server: MockSSEServer):
        """Override using numeric comparison operators."""
        mock_server.send_init(
            [
                create_config(
                    "discount",
                    0,
                    overrides=[
                        create_override(
                            "high-spenders",
                            20,
                            [
                                {
                                    "operator": "greater_than",
                                    "property": "total_spent",
                                    "value": 1000,
                                },
                            ],
                        ),
                        create_override(
                            "medium-spenders",
                            10,
                            [
                                {
                                    "operator": "greater_than_or_equal",
                                    "property": "total_spent",
                                    "value": 500,
                                },
                            ],
                        ),
                    ],
                ),
            ]
        )

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            assert client.with_context({"total_spent": 100}).configs["discount"] == 0
            assert client.with_context({"total_spent": 500}).configs["discount"] == 10
            assert client.with_context({"total_spent": 1001}).configs["discount"] == 20

    def test_override_with_multiple_conditions_and(self, mock_server: MockSSEServer):
        """Override with multiple conditions (AND logic)."""
        mock_server.send_init(
            [
                create_config(
                    "special-feature",
                    False,
                    overrides=[
                        create_override(
                            "premium-beta",
                            True,
                            [
                                create_condition("equals", "plan", "premium"),
                                create_condition("equals", "beta", True),
                            ],
                        ),
                    ],
                ),
            ]
        )

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            # Both conditions must match
            assert client.with_context({"plan": "premium"}).configs["special-feature"] is False
            assert client.with_context({"beta": True}).configs["special-feature"] is False
            assert (
                client.with_context({"plan": "premium", "beta": True}).configs["special-feature"]
                is True
            )

    def test_override_missing_context_property(self, mock_server: MockSSEServer):
        """Override doesn't match when context property is missing."""
        mock_server.send_init(
            [
                create_config(
                    "feature",
                    "default",
                    overrides=[
                        create_override(
                            "has-user",
                            "user-value",
                            [
                                create_condition("equals", "user_id", "123"),
                            ],
                        ),
                    ],
                ),
            ]
        )

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            # No user_id in context - should get default
            assert client.configs["feature"] == "default"
            assert client.with_context({}).configs["feature"] == "default"
            assert client.with_context({"user_id": "123"}).configs["feature"] == "user-value"


class TestSyncClientSubscriptionEdgeCases:
    """Test edge cases for subscriptions."""

    def test_subscriber_exception_doesnt_break_other_subscribers(self, mock_server: MockSSEServer):
        """Exception in one subscriber doesn't prevent others from being called."""
        mock_server.send_init([create_config("feature", False)])

        successful_changes: list[bool] = []

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:

            def bad_subscriber(name, config):
                raise ValueError("Intentional error")

            def good_subscriber(name, config):
                successful_changes.append(config.value)

            client.subscribe(bad_subscriber)
            client.subscribe(good_subscriber)

            mock_server.send_config_change(create_config("feature", True))
            time.sleep(0.3)

            # Good subscriber should still be called
            assert len(successful_changes) == 1
            assert successful_changes[0] is True

    def test_multiple_subscribers_same_config(self, mock_server: MockSSEServer):
        """Multiple subscribers for the same config all receive updates."""
        mock_server.send_init([create_config("feature", False)])

        changes1: list[bool] = []
        changes2: list[bool] = []

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            client.subscribe_config("feature", lambda c: changes1.append(c.value))
            client.subscribe_config("feature", lambda c: changes2.append(c.value))

            mock_server.send_config_change(create_config("feature", True))
            time.sleep(0.3)

            assert changes1 == [True]
            assert changes2 == [True]

    def test_unsubscribe_same_callback_twice(self, mock_server: MockSSEServer):
        """Unsubscribing same callback twice doesn't raise."""
        mock_server.send_init([create_config("feature", True)])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:

            def callback(name, config):
                pass

            unsubscribe = client.subscribe(callback)
            unsubscribe()
            unsubscribe()  # Should not raise

    def test_subscribe_before_and_after_init(self, mock_server: MockSSEServer):
        """Subscriptions work regardless of when they're added."""
        mock_server.send_init([create_config("feature", False)])

        changes: list[bool] = []

        client = Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        )

        # Subscribe before connect
        client.subscribe(lambda name, config: changes.append(config.value))

        try:
            client.connect()

            mock_server.send_config_change(create_config("feature", True))
            time.sleep(0.3)

            assert changes == [True]
        finally:
            client.close()

    def test_config_change_updates_local_cache(self, mock_server: MockSSEServer):
        """Config changes update the local cache immediately."""
        mock_server.send_init([create_config("counter", 0)])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            assert client.configs["counter"] == 0

            mock_server.send_config_change(create_config("counter", 1))
            time.sleep(0.3)
            assert client.configs["counter"] == 1

            mock_server.send_config_change(create_config("counter", 2))
            time.sleep(0.3)
            assert client.configs["counter"] == 2


class TestSyncClientErrorHandling:
    """Test error handling scenarios."""

    def test_server_returns_400(self, mock_server: MockSSEServer):
        """Client handles 400 Bad Request."""
        mock_server.set_status_code(400)

        client = Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            initialization_timeout_ms=1000,
            retry_delay_ms=100,
        )

        # Should timeout because 400 errors are retried
        with pytest.raises(TimeoutError):
            client.connect()

        client.close()

    def test_server_returns_403(self, mock_server: MockSSEServer):
        """Client handles 403 Forbidden."""
        mock_server.set_status_code(403)

        client = Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            initialization_timeout_ms=1000,
            retry_delay_ms=100,
        )

        # Should timeout because 403 errors are retried
        with pytest.raises(TimeoutError):
            client.connect()

        client.close()

    def test_server_returns_503(self, mock_server: MockSSEServer):
        """Client handles 503 Service Unavailable and retries."""
        mock_server.set_status_code(503)

        # Queue init for after retry
        def send_init_later():
            time.sleep(0.3)
            mock_server.send_init([create_config("feature", True)])

        threading.Thread(target=send_init_later, daemon=True).start()

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            initialization_timeout_ms=3000,
            retry_delay_ms=100,
        ) as client:
            assert client.configs["feature"] is True

    def test_new_config_added_via_change_event(self, mock_server: MockSSEServer):
        """New configs can be added via config_change events."""
        mock_server.send_init([create_config("existing", True)])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            assert client.configs["existing"] is True

            with pytest.raises(KeyError):
                client.configs["new-config"]

            # Add new config via change event
            mock_server.send_config_change(create_config("new-config", "new-value"))
            time.sleep(0.3)

            assert client.configs["new-config"] == "new-value"


class TestSyncClientDebugMode:
    """Test debug mode functionality."""

    def test_debug_mode_enabled(self, mock_server: MockSSEServer):
        """Debug mode can be enabled without errors."""
        mock_server.send_init([create_config("feature", True)])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            debug=True,
        ) as client:
            assert client.configs["feature"] is True


class TestSyncClientInactivityTimeout:
    """Test inactivity timeout handling."""

    def test_inactivity_timeout_triggers_reconnect(self, mock_server: MockSSEServer):
        """Client reconnects when server stops sending events."""
        mock_server.send_init([create_config("feature", "initial")])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            inactivity_timeout_ms=2000,  # 2 second timeout
            retry_delay_ms=100,
        ) as client:
            assert client.configs["feature"] == "initial"

            # Queue a new init for when the client reconnects after inactivity
            mock_server.send_init([create_config("feature", "after-reconnect")])

            # Wait for inactivity timeout + reconnection
            time.sleep(2.5)

            # Should have the new value after reconnect
            assert client.configs["feature"] == "after-reconnect"


class TestSyncClientWithContext:
    """Test the with_context method for scoped context."""

    def test_with_context_merges_context(self, mock_server: MockSSEServer):
        """with_context merges context with client's default context."""
        mock_server.send_init(
            [
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
            ]
        )

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            context={"environment": "production"},
        ) as client:
            # Original client doesn't match override
            assert client.configs["rate-limit"] == 100

            # Create scoped client with additional context
            user_client = client.with_context({"plan": "premium"})

            # Scoped client should use merged context
            assert user_client.configs["rate-limit"] == 1000

    def test_with_context_get_with_additional_context(self, mock_server: MockSSEServer):
        """Scoped client's get() can accept additional context."""
        mock_server.send_init(
            [
                create_config(
                    "feature",
                    "default",
                    overrides=[
                        create_override(
                            "region-override",
                            "eu-value",
                            [
                                create_condition("equals", "plan", "premium"),
                                create_condition("equals", "region", "eu"),
                            ],
                        ),
                    ],
                ),
            ]
        )

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            user_client = client.with_context({"plan": "premium"})

            # Without region, override doesn't match
            assert user_client.configs["feature"] == "default"

            # With region in per-call context, override matches
            assert user_client.with_context({"region": "eu"}).configs["feature"] == "eu-value"

    def test_with_context_configs_accessor(self, mock_server: MockSSEServer):
        """Scoped client's .configs uses merged context."""
        mock_server.send_init(
            [
                create_config(
                    "settings",
                    {"tier": "free"},
                    overrides=[
                        create_override(
                            "premium-settings",
                            {"tier": "premium"},
                            [create_condition("equals", "plan", "premium")],
                        ),
                    ],
                ),
            ]
        )

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            user_client = client.with_context({"plan": "premium"})

            # configs accessor uses merged context
            settings = user_client.configs["settings"]
            assert settings["tier"] == "premium"

    def test_with_context_chaining(self, mock_server: MockSSEServer):
        """with_context can be chained to add more context."""
        mock_server.send_init(
            [
                create_config(
                    "feature",
                    "default",
                    overrides=[
                        create_override(
                            "full-match",
                            "matched",
                            [
                                create_condition("equals", "a", 1),
                                create_condition("equals", "b", 2),
                                create_condition("equals", "c", 3),
                            ],
                        ),
                    ],
                ),
            ]
        )

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            context={"a": 1},
        ) as client:
            client_b = client.with_context({"b": 2})
            client_c = client_b.with_context({"c": 3})

            # Only fully chained client matches
            assert client.configs["feature"] == "default"
            assert client_b.configs["feature"] == "default"
            assert client_c.configs["feature"] == "matched"

    def test_with_context_does_not_affect_original(self, mock_server: MockSSEServer):
        """Creating scoped client doesn't affect original client."""
        mock_server.send_init(
            [
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
            ]
        )

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            # Create scoped client
            _ = client.with_context({"plan": "premium"})

            # Original client is unaffected
            assert client.configs["rate-limit"] == 100

    def test_with_context_is_initialized(self, mock_server: MockSSEServer):
        """Scoped client's is_initialized() delegates to original."""
        mock_server.send_init([create_config("feature", True)])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            user_client = client.with_context({"user_id": "123"})
            assert user_client.is_initialized() is True

    def test_with_context_subscribe(self, mock_server: MockSSEServer):
        """Scoped client's subscribe delegates to original."""
        mock_server.send_init([create_config("feature", False)])

        changes: list[tuple[str, bool]] = []

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            user_client = client.with_context({"user_id": "123"})

            def on_change(name, config):
                changes.append((name, config.value))

            unsubscribe = user_client.subscribe(on_change)

            mock_server.send_config_change(create_config("feature", True))
            time.sleep(0.3)

            assert len(changes) == 1
            assert changes[0] == ("feature", True)

            unsubscribe()


class TestSyncClientWithDefaults:
    """Test the with_defaults method for scoped defaults."""

    def test_with_defaults_returns_default_for_missing(self, mock_server: MockSSEServer):
        """with_defaults provides defaults for missing configs."""
        mock_server.send_init([create_config("existing", "value")])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            safe_client = client.with_defaults({"missing-config": "fallback"})

            # Existing config works normally
            assert safe_client.configs["existing"] == "value"

            # Missing config returns the scoped default
            assert safe_client.configs["missing-config"] == "fallback"

    def test_with_defaults_chaining(self, mock_server: MockSSEServer):
        """with_defaults can be chained to add more defaults."""
        mock_server.send_init([create_config("existing", "value")])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            client_a = client.with_defaults({"a": 1})
            client_b = client_a.with_defaults({"b": 2})

            assert client_b.configs["a"] == 1
            assert client_b.configs["b"] == 2

    def test_with_defaults_merged_with_context(self, mock_server: MockSSEServer):
        """with_defaults and with_context can be combined."""
        mock_server.send_init(
            [
                create_config(
                    "rate-limit",
                    100,
                    overrides=[
                        create_override(
                            "premium",
                            1000,
                            [create_condition("equals", "plan", "premium")],
                        ),
                    ],
                ),
            ]
        )

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            # Chain with_context and with_defaults
            scoped = client.with_context({"plan": "premium"}).with_defaults({"timeout": 30})

            # Context affects override evaluation
            assert scoped.configs["rate-limit"] == 1000
            # Defaults apply for missing configs
            assert scoped.configs["timeout"] == 30

    def test_with_defaults_overridden_by_explicit_default(self, mock_server: MockSSEServer):
        """Explicit default in get() overrides scoped default."""
        mock_server.send_init([create_config("existing", "value")])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            safe_client = client.with_defaults({"missing": "scoped-default"})

            # Explicit default takes precedence
            assert safe_client.configs.get("missing", "explicit") == "explicit"

    def test_with_defaults_does_not_affect_original(self, mock_server: MockSSEServer):
        """Creating scoped client doesn't affect original client."""
        mock_server.send_init([create_config("existing", "value")])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            _ = client.with_defaults({"missing": "default"})

            # Original client still raises KeyError
            with pytest.raises(KeyError):
                client.configs["missing"]


class TestSyncClientConfigsAccessor:
    """Test the configs property for dictionary-style access."""

    def test_configs_bracket_access(self, mock_server: MockSSEServer):
        """Access configs using bracket notation."""
        mock_server.send_init(
            [
                create_config("feature-flag", True),
                create_config("settings", {"theme": "dark", "fontSize": 14}),
            ]
        )

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            assert client.configs["feature-flag"] is True
            assert client.configs["settings"] == {"theme": "dark", "fontSize": 14}
            assert client.configs["settings"]["theme"] == "dark"

    def test_configs_missing_key_raises_keyerror(self, mock_server: MockSSEServer):
        """Accessing missing config via configs raises KeyError."""
        mock_server.send_init([create_config("existing", True)])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            with pytest.raises(KeyError):
                _ = client.configs["nonexistent"]

    def test_configs_get_method(self, mock_server: MockSSEServer):
        """configs.get() returns default for missing keys."""
        mock_server.send_init([create_config("existing", True)])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            assert client.configs.get("existing") is True
            assert client.configs.get("missing") is None
            assert client.configs.get("missing", "default") == "default"

    def test_configs_contains(self, mock_server: MockSSEServer):
        """Check if config exists using 'in' operator."""
        mock_server.send_init([create_config("existing", True)])

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            assert "existing" in client.configs
            assert "missing" not in client.configs

    def test_configs_keys(self, mock_server: MockSSEServer):
        """Get all config names."""
        mock_server.send_init(
            [
                create_config("config-a", 1),
                create_config("config-b", 2),
                create_config("config-c", 3),
            ]
        )

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            keys = client.configs.keys()
            assert "config-a" in keys
            assert "config-b" in keys
            assert "config-c" in keys

    def test_configs_evaluates_overrides(self, mock_server: MockSSEServer):
        """configs accessor evaluates overrides with default context."""
        mock_server.send_init(
            [
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
            ]
        )

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            context={"plan": "premium"},
        ) as client:
            # Should apply override based on default context
            assert client.configs["rate-limit"] == 1000

    def test_configs_closed_client_raises(self, mock_server: MockSSEServer):
        """Accessing configs on closed client raises ClientClosedError."""
        mock_server.send_init([create_config("feature", True)])

        client = Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        )
        client.connect()
        client.close()

        with pytest.raises(ClientClosedError):
            _ = client.configs["feature"]


class TestReplaneClientId:
    """Test auto-generated replaneClientId context field."""

    def test_auto_generates_replane_client_id(self, mock_server: MockSSEServer):
        """Client auto-generates replaneClientId and uses it for segmentation."""
        mock_server.send_init(
            [
                create_config(
                    "feature",
                    "default",
                    overrides=[
                        create_override(
                            "segmented-override",
                            "segmented-value",
                            [
                                {
                                    "operator": "segmentation",
                                    "property": "replaneClientId",
                                    "fromPercentage": 0,
                                    "toPercentage": 100,
                                    "seed": "test-seed",
                                }
                            ],
                        ),
                    ],
                ),
            ]
        )

        # Create client without providing replaneClientId
        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            # Should match segmentation because replaneClientId is auto-generated
            assert client.configs["feature"] == "segmented-value"

    def test_user_provided_replane_client_id_takes_precedence(self, mock_server: MockSSEServer):
        """User-provided replaneClientId takes precedence over auto-generated one."""
        user_provided_id = "user-provided-client-id"
        mock_server.send_init(
            [
                create_config(
                    "feature",
                    "default",
                    overrides=[
                        create_override(
                            "user-override",
                            "user-override-value",
                            [create_condition("equals", "replaneClientId", user_provided_id)],
                        ),
                    ],
                ),
            ]
        )

        # Provide replaneClientId in context - should take precedence
        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
            context={"replaneClientId": user_provided_id},
        ) as client:
            assert client.configs["feature"] == "user-override-value"

    def test_per_request_context_overrides_replane_client_id(self, mock_server: MockSSEServer):
        """Per-request context can override replaneClientId."""
        per_request_id = "per-request-client-id"
        mock_server.send_init(
            [
                create_config(
                    "feature",
                    "default",
                    overrides=[
                        create_override(
                            "per-request-override",
                            "per-request-value",
                            [create_condition("equals", "replaneClientId", per_request_id)],
                        ),
                    ],
                ),
            ]
        )

        with Replane(
            base_url=mock_server.url,
            sdk_key="rp_test_key",
        ) as client:
            # Default should be based on auto-generated ID (won't match)
            assert client.configs["feature"] == "default"

            # Per-request context should override the auto-generated ID
            assert (
                client.with_context({"replaneClientId": per_request_id}).configs["feature"]
                == "per-request-value"
            )

    def test_unique_replane_client_id_per_client_instance(self):
        """Each client instance gets a unique replaneClientId."""
        # Create multiple client instances and collect their auto-generated IDs
        # We don't need to connect - the ID is generated at construction time
        client_ids = set()
        for _ in range(10):
            client = Replane(
                base_url="http://localhost:9999",  # Won't connect
                sdk_key="rp_test_key",
            )
            client_id = client._context.get("replaneClientId")
            assert client_id is not None, "replaneClientId should be auto-generated"
            client_ids.add(client_id)

        # All 10 clients should have unique IDs
        assert len(client_ids) == 10, "Each client should get a unique replaneClientId"
