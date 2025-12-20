"""Tests demonstrating how to use the Replane testing utilities.

This module shows various patterns for testing code that uses Replane.
"""

import pytest
from app import OrderService, calculate_discount, get_rate_limit, is_feature_enabled

from replane.testing import InMemoryReplaneClient, create_test_client


class TestBasicUsage:
    """Basic testing patterns with InMemoryReplaneClient."""

    def test_simple_config_values(self):
        """Test reading simple config values."""
        client = create_test_client(
            {
                "rate-limit": 100,
                "feature-enabled": True,
                "api-version": "v2",
            }
        )

        assert client.get("rate-limit") == 100
        assert client.get("feature-enabled") is True
        assert client.get("api-version") == "v2"

    def test_default_values(self):
        """Test that default values work correctly."""
        client = create_test_client({})

        # Should return default when config doesn't exist
        assert client.get("missing-config", default=42) == 42
        assert client.get("missing-flag", default=False) is False

    def test_context_manager(self):
        """Test using the client as a context manager."""
        with create_test_client({"key": "value"}) as client:
            assert client.get("key") == "value"

    def test_set_config_dynamically(self):
        """Test setting configs after creation."""
        client = create_test_client()

        client.set("feature-enabled", True)
        assert client.get("feature-enabled") is True

        client.set("feature-enabled", False)
        assert client.get("feature-enabled") is False


class TestWithOverrides:
    """Testing patterns with override rules."""

    def test_plan_based_overrides(self):
        """Test overrides based on user plan."""
        client = InMemoryReplaneClient()

        # Set up config with overrides
        client.set_config(
            "rate-limit",
            value=100,  # Default for free users
            overrides=[
                {
                    "name": "premium-users",
                    "conditions": [
                        {"operator": "equals", "property": "plan", "expected": "premium"}
                    ],
                    "value": 1000,
                },
                {
                    "name": "enterprise-users",
                    "conditions": [
                        {"operator": "equals", "property": "plan", "expected": "enterprise"}
                    ],
                    "value": 10000,
                },
            ],
        )

        # Test different plans
        assert client.get("rate-limit", context={"plan": "free"}) == 100
        assert client.get("rate-limit", context={"plan": "premium"}) == 1000
        assert client.get("rate-limit", context={"plan": "enterprise"}) == 10000

    def test_user_targeting(self):
        """Test overrides targeting specific users."""
        client = InMemoryReplaneClient()

        client.set_config(
            "new-feature",
            value=False,
            overrides=[
                {
                    "name": "beta-users",
                    "conditions": [
                        {
                            "operator": "in",
                            "property": "user_id",
                            "expected": ["user-1", "user-2", "user-3"],
                        }
                    ],
                    "value": True,
                },
            ],
        )

        # Beta users get the feature
        assert client.get("new-feature", context={"user_id": "user-1"}) is True
        assert client.get("new-feature", context={"user_id": "user-2"}) is True

        # Regular users don't
        assert client.get("new-feature", context={"user_id": "user-999"}) is False

    def test_multiple_conditions(self):
        """Test overrides with multiple conditions (AND logic)."""
        client = InMemoryReplaneClient()

        client.set_config(
            "special-offer",
            value=False,
            overrides=[
                {
                    "name": "premium-us-users",
                    "conditions": [
                        {"operator": "equals", "property": "plan", "expected": "premium"},
                        {"operator": "equals", "property": "region", "expected": "US"},
                    ],
                    "value": True,
                },
            ],
        )

        # Both conditions must match
        assert client.get("special-offer", context={"plan": "premium", "region": "US"}) is True
        assert client.get("special-offer", context={"plan": "premium", "region": "EU"}) is False
        assert client.get("special-offer", context={"plan": "free", "region": "US"}) is False


class TestApplicationCode:
    """Testing actual application code with mocked Replane."""

    def test_get_rate_limit(self):
        """Test the get_rate_limit function."""
        client = InMemoryReplaneClient()
        client.set_config(
            "rate-limit",
            value=100,
            overrides=[
                {
                    "name": "premium",
                    "conditions": [
                        {"operator": "equals", "property": "plan", "expected": "premium"}
                    ],
                    "value": 500,
                },
            ],
        )

        assert get_rate_limit(client, "free") == 100
        assert get_rate_limit(client, "premium") == 500

    def test_is_feature_enabled(self):
        """Test the is_feature_enabled function."""
        client = create_test_client({"dark-mode": True, "beta-feature": False})

        assert is_feature_enabled(client, "dark-mode") is True
        assert is_feature_enabled(client, "beta-feature") is False
        assert is_feature_enabled(client, "unknown-feature") is False  # Uses default

    def test_calculate_discount(self):
        """Test the calculate_discount function."""
        client = create_test_client(
            {
                "base-discount": 10,
                "premium-bonus": 15,
            }
        )

        # Regular user gets base discount
        assert calculate_discount(client, "user-1", is_premium=False) == 10

        # Premium user gets base + bonus
        assert calculate_discount(client, "user-1", is_premium=True) == 25


class TestOrderService:
    """Testing a service class with Replane."""

    @pytest.fixture
    def replane_client(self):
        """Create a test client for the OrderService."""
        client = InMemoryReplaneClient()

        client.set_config(
            "max-items-per-order",
            value=10,
            overrides=[
                {
                    "name": "premium",
                    "conditions": [
                        {"operator": "equals", "property": "plan", "expected": "premium"}
                    ],
                    "value": 50,
                },
            ],
        )

        client.set_config(
            "express-shipping-enabled",
            value=False,
            overrides=[
                {
                    "name": "us-region",
                    "conditions": [
                        {"operator": "in", "property": "region", "expected": ["US", "CA"]}
                    ],
                    "value": True,
                },
            ],
        )

        return client

    def test_max_items_free_plan(self, replane_client):
        """Test max items for free plan."""
        service = OrderService(replane_client)
        assert service.get_max_items_per_order("free") == 10

    def test_max_items_premium_plan(self, replane_client):
        """Test max items for premium plan."""
        service = OrderService(replane_client)
        assert service.get_max_items_per_order("premium") == 50

    def test_express_shipping_available_regions(self, replane_client):
        """Test express shipping in available regions."""
        service = OrderService(replane_client)
        assert service.is_express_shipping_available("US") is True
        assert service.is_express_shipping_available("CA") is True

    def test_express_shipping_unavailable_regions(self, replane_client):
        """Test express shipping in unavailable regions."""
        service = OrderService(replane_client)
        assert service.is_express_shipping_available("EU") is False
        assert service.is_express_shipping_available("APAC") is False


class TestSubscriptions:
    """Testing config change subscriptions."""

    def test_subscribe_to_changes(self):
        """Test subscribing to config changes."""
        client = create_test_client({"value": 1})
        changes = []

        # Subscribe to all changes
        unsubscribe = client.subscribe(lambda name, config: changes.append((name, config.value)))

        # Make some changes
        client.set("value", 2)
        client.set("value", 3)
        client.set("other", "x")

        assert len(changes) == 3
        assert changes[0] == ("value", 2)
        assert changes[1] == ("value", 3)
        assert changes[2] == ("other", "x")

        # Unsubscribe and verify no more notifications
        unsubscribe()
        client.set("value", 4)
        assert len(changes) == 3  # No new changes recorded

    def test_subscribe_to_specific_config(self):
        """Test subscribing to a specific config."""
        client = create_test_client()
        changes = []

        # Subscribe to only "feature" config
        client.subscribe_config("feature", lambda config: changes.append(config.value))

        client.set("feature", True)
        client.set("other", "ignored")
        client.set("feature", False)

        assert changes == [True, False]
