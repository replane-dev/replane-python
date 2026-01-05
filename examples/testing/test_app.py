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
        replane = create_test_client(
            {
                "rate-limit": 100,
                "feature-enabled": True,
                "api-version": "v2",
            }
        )

        assert replane.configs["rate-limit"] == 100
        assert replane.configs["feature-enabled"] is True
        assert replane.configs["api-version"] == "v2"

    def test_default_values(self):
        """Test that default values work correctly."""
        replane = create_test_client({})

        # Should return default when config doesn't exist
        assert replane.configs.get("missing-config", 42) == 42
        assert replane.configs.get("missing-flag", False) is False

    def test_context_manager(self):
        """Test using the client as a context manager."""
        with create_test_client({"key": "value"}) as replane:
            assert replane.configs["key"] == "value"

    def test_set_config_dynamically(self):
        """Test setting configs after creation."""
        replane = create_test_client()

        replane.set("feature-enabled", True)
        assert replane.configs["feature-enabled"] is True

        replane.set("feature-enabled", False)
        assert replane.configs["feature-enabled"] is False


class TestWithOverrides:
    """Testing patterns with override rules."""

    def test_plan_based_overrides(self):
        """Test overrides based on user plan."""
        replane = InMemoryReplaneClient()

        # Set up config with overrides
        replane.set_config(
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
        assert replane.with_context({"plan": "free"}).configs["rate-limit"] == 100
        assert replane.with_context({"plan": "premium"}).configs["rate-limit"] == 1000
        assert replane.with_context({"plan": "enterprise"}).configs["rate-limit"] == 10000

    def test_user_targeting(self):
        """Test overrides targeting specific users."""
        replane = InMemoryReplaneClient()

        replane.set_config(
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
        assert replane.with_context({"user_id": "user-1"}).configs["new-feature"] is True
        assert replane.with_context({"user_id": "user-2"}).configs["new-feature"] is True

        # Regular users don't
        assert replane.with_context({"user_id": "user-999"}).configs["new-feature"] is False

    def test_multiple_conditions(self):
        """Test overrides with multiple conditions (AND logic)."""
        replane = InMemoryReplaneClient()

        replane.set_config(
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
        assert (
            replane.with_context({"plan": "premium", "region": "US"}).configs["special-offer"]
            is True
        )
        assert (
            replane.with_context({"plan": "premium", "region": "EU"}).configs["special-offer"]
            is False
        )
        assert (
            replane.with_context({"plan": "free", "region": "US"}).configs["special-offer"] is False
        )


class TestApplicationCode:
    """Testing actual application code with mocked Replane."""

    def test_get_rate_limit(self):
        """Test the get_rate_limit function."""
        replane = InMemoryReplaneClient()
        replane.set_config(
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

        assert get_rate_limit(replane, "free") == 100
        assert get_rate_limit(replane, "premium") == 500

    def test_is_feature_enabled(self):
        """Test the is_feature_enabled function."""
        replane = create_test_client({"dark-mode": True, "beta-feature": False})

        assert is_feature_enabled(replane, "dark-mode") is True
        assert is_feature_enabled(replane, "beta-feature") is False
        assert is_feature_enabled(replane, "unknown-feature") is False  # Uses default

    def test_calculate_discount(self):
        """Test the calculate_discount function."""
        replane = create_test_client(
            {
                "base-discount": 10,
                "premium-bonus": 15,
            }
        )

        # Regular user gets base discount
        assert calculate_discount(replane, "user-1", is_premium=False) == 10

        # Premium user gets base + bonus
        assert calculate_discount(replane, "user-1", is_premium=True) == 25


class TestOrderService:
    """Testing a service class with Replane."""

    @pytest.fixture
    def replane(self):
        """Create a test client for the OrderService."""
        replane = InMemoryReplaneClient()

        replane.set_config(
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

        replane.set_config(
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

        return replane

    def test_max_items_free_plan(self, replane):
        """Test max items for free plan."""
        service = OrderService(replane)
        assert service.get_max_items_per_order("free") == 10

    def test_max_items_premium_plan(self, replane):
        """Test max items for premium plan."""
        service = OrderService(replane)
        assert service.get_max_items_per_order("premium") == 50

    def test_express_shipping_available_regions(self, replane):
        """Test express shipping in available regions."""
        service = OrderService(replane)
        assert service.is_express_shipping_available("US") is True
        assert service.is_express_shipping_available("CA") is True

    def test_express_shipping_unavailable_regions(self, replane):
        """Test express shipping in unavailable regions."""
        service = OrderService(replane)
        assert service.is_express_shipping_available("EU") is False
        assert service.is_express_shipping_available("APAC") is False


class TestSubscriptions:
    """Testing config change subscriptions."""

    def test_subscribe_to_changes(self):
        """Test subscribing to config changes."""
        replane = create_test_client({"value": 1})
        changes = []

        # Subscribe to all changes
        unsubscribe = replane.subscribe(lambda name, config: changes.append((name, config.value)))

        # Make some changes
        replane.set("value", 2)
        replane.set("value", 3)
        replane.set("other", "x")

        assert len(changes) == 3
        assert changes[0] == ("value", 2)
        assert changes[1] == ("value", 3)
        assert changes[2] == ("other", "x")

        # Unsubscribe and verify no more notifications
        unsubscribe()
        replane.set("value", 4)
        assert len(changes) == 3  # No new changes recorded

    def test_subscribe_to_specific_config(self):
        """Test subscribing to a specific config."""
        replane = create_test_client()
        changes = []

        # Subscribe to only "feature" config
        replane.subscribe_config("feature", lambda config: changes.append(config.value))

        replane.set("feature", True)
        replane.set("other", "ignored")
        replane.set("feature", False)

        assert changes == [True, False]
