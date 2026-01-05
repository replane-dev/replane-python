"""Tests for the in-memory testing client."""

import pytest

from replane.errors import ClientClosedError
from replane.testing import InMemoryReplaneClient, create_test_client


class TestInMemoryReplaneClient:
    """Tests for the in-memory client."""

    def test_get_simple_config(self):
        client = InMemoryReplaneClient({"feature": True})
        assert client.configs["feature"] is True

    def test_get_missing_config_raises(self):
        client = InMemoryReplaneClient()
        with pytest.raises(KeyError):
            client.configs["missing"]

    def test_get_missing_with_default(self):
        client = InMemoryReplaneClient()
        assert client.configs.get("missing", "fallback") == "fallback"

    def test_set_and_get(self):
        client = InMemoryReplaneClient()
        client.set("rate-limit", 100)
        assert client.configs["rate-limit"] == 100

    def test_set_overwrites(self):
        client = InMemoryReplaneClient({"value": 1})
        client.set("value", 2)
        assert client.configs["value"] == 2

    def test_delete_config(self):
        client = InMemoryReplaneClient({"feature": True})
        assert client.delete("feature") is True
        with pytest.raises(KeyError):
            client.configs["feature"]

    def test_delete_nonexistent_returns_false(self):
        client = InMemoryReplaneClient()
        assert client.delete("missing") is False

    def test_default_context(self):
        client = InMemoryReplaneClient(context={"env": "test"})
        client.set_config(
            "feature",
            value=False,
            overrides=[
                {
                    "name": "test-env",
                    "conditions": [{"operator": "equals", "property": "env", "expected": "test"}],
                    "value": True,
                }
            ],
        )
        # Uses default context
        assert client.configs["feature"] is True

    def test_get_context_override(self):
        client = InMemoryReplaneClient(context={"env": "prod"})
        client.set_config(
            "feature",
            value=False,
            overrides=[
                {
                    "name": "test-env",
                    "conditions": [{"operator": "equals", "property": "env", "expected": "test"}],
                    "value": True,
                }
            ],
        )
        # Override default context
        assert client.with_context({"env": "test"}).configs["feature"] is True

    def test_subscribe_all(self):
        client = InMemoryReplaneClient()
        changes = []

        def on_change(name, config):
            changes.append((name, config.value))

        client.subscribe(on_change)
        client.set("a", 1)
        client.set("b", 2)

        assert changes == [("a", 1), ("b", 2)]

    def test_subscribe_specific_config(self):
        client = InMemoryReplaneClient()
        changes = []

        def on_change(config):
            changes.append(config.value)

        client.subscribe_config("target", on_change)
        client.set("other", 1)
        client.set("target", 2)
        client.set("target", 3)

        assert changes == [2, 3]

    def test_unsubscribe(self):
        client = InMemoryReplaneClient()
        changes = []

        def on_change(name, config):
            changes.append(name)

        unsubscribe = client.subscribe(on_change)
        client.set("a", 1)
        unsubscribe()
        client.set("b", 2)

        assert changes == ["a"]

    def test_context_manager(self):
        with InMemoryReplaneClient({"test": "value"}) as client:
            assert client.configs["test"] == "value"
        # Should be closed now
        with pytest.raises(ClientClosedError):
            client.configs["test"]

    def test_close_prevents_operations(self):
        client = InMemoryReplaneClient()
        client.close()
        with pytest.raises(ClientClosedError):
            client.configs["anything"]

    def test_configs_property(self):
        client = InMemoryReplaneClient({"a": 1, "b": 2})
        configs = client.configs
        assert len(configs.keys()) == 2
        assert configs["a"] == 1


class TestSetConfigWithOverrides:
    """Tests for set_config with override rules."""

    def test_simple_override(self):
        client = InMemoryReplaneClient()
        client.set_config(
            "feature",
            value=False,
            overrides=[
                {
                    "name": "premium",
                    "conditions": [
                        {"operator": "equals", "property": "plan", "expected": "premium"}
                    ],
                    "value": True,
                }
            ],
        )

        assert client.with_context({"plan": "free"}).configs["feature"] is False
        assert client.with_context({"plan": "premium"}).configs["feature"] is True

    def test_multiple_conditions(self):
        client = InMemoryReplaneClient()
        client.set_config(
            "rate-limit",
            value=100,
            overrides=[
                {
                    "name": "premium-us",
                    "conditions": [
                        {"operator": "equals", "property": "plan", "expected": "premium"},
                        {"operator": "equals", "property": "region", "expected": "us"},
                    ],
                    "value": 10000,
                }
            ],
        )

        assert client.with_context({"plan": "free", "region": "us"}).configs["rate-limit"] == 100
        assert client.with_context({"plan": "premium", "region": "eu"}).configs["rate-limit"] == 100
        assert (
            client.with_context({"plan": "premium", "region": "us"}).configs["rate-limit"] == 10000
        )

    def test_multiple_overrides_first_wins(self):
        client = InMemoryReplaneClient()
        client.set_config(
            "tier",
            value="free",
            overrides=[
                {
                    "name": "enterprise",
                    "conditions": [
                        {"operator": "equals", "property": "plan", "expected": "enterprise"}
                    ],
                    "value": "enterprise",
                },
                {
                    "name": "premium",
                    "conditions": [
                        {
                            "operator": "in",
                            "property": "plan",
                            "expected": ["premium", "enterprise"],
                        }
                    ],
                    "value": "premium",
                },
            ],
        )

        assert client.with_context({"plan": "free"}).configs["tier"] == "free"
        assert client.with_context({"plan": "premium"}).configs["tier"] == "premium"
        # Enterprise matches first override, so "enterprise" not "premium"
        assert client.with_context({"plan": "enterprise"}).configs["tier"] == "enterprise"

    def test_in_operator(self):
        client = InMemoryReplaneClient()
        client.set_config(
            "feature",
            value=False,
            overrides=[
                {
                    "name": "paid-plans",
                    "conditions": [
                        {"operator": "in", "property": "plan", "expected": ["pro", "enterprise"]}
                    ],
                    "value": True,
                }
            ],
        )

        assert client.with_context({"plan": "free"}).configs["feature"] is False
        assert client.with_context({"plan": "pro"}).configs["feature"] is True
        assert client.with_context({"plan": "enterprise"}).configs["feature"] is True


class TestCreateTestClient:
    """Tests for the create_test_client helper."""

    def test_creates_client_with_configs(self):
        client = create_test_client({"key": "value"})
        assert client.configs["key"] == "value"

    def test_creates_empty_client(self):
        client = create_test_client()
        with pytest.raises(KeyError):
            client.configs["missing"]

    def test_with_default_context(self):
        client = create_test_client({"x": 1}, context={"env": "test"})
        assert client._context == {"env": "test"}
