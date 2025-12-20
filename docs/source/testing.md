# Testing

The Replane SDK provides an in-memory client specifically designed for testing. This allows you to test your application without connecting to a real Replane server.

## In-Memory Client

The `InMemoryReplaneClient` provides the same interface as the real clients but stores all configs in memory:

```python
from replane.testing import InMemoryReplaneClient

# Create with initial configs
client = InMemoryReplaneClient({
    "feature-enabled": True,
    "rate-limit": 100,
    "api-version": "v2",
})

# Use like the real client
assert client.get("feature-enabled") is True
assert client.get("rate-limit") == 100
```

## Using create_test_client

For convenience, use the `create_test_client` helper:

```python
from replane.testing import create_test_client

client = create_test_client({
    "feature-flags": {"dark-mode": True, "new-ui": False},
    "limits": {"max-items": 50, "max-users": 10},
})
```

## Pytest Fixtures

Create a fixture to share test configs across tests:

```python
import pytest
from replane.testing import create_test_client

@pytest.fixture
def replane_client():
    return create_test_client({
        "feature-enabled": True,
        "rate-limit": 100,
    })

def test_feature_flag(replane_client):
    assert replane_client.get("feature-enabled") is True

def test_rate_limit(replane_client):
    assert replane_client.get("rate-limit") == 100
```

## Testing with Overrides

Test override behavior by setting up configs with override rules:

```python
from replane.testing import InMemoryReplaneClient

def test_plan_based_rate_limits():
    client = InMemoryReplaneClient()
    client.set_config(
        "rate-limit",
        value=100,  # Base value for free users
        overrides=[
            {
                "name": "premium-users",
                "conditions": [
                    {"operator": "in", "property": "plan", "expected": ["pro", "enterprise"]}
                ],
                "value": 1000,
            }
        ],
    )

    # Free user gets base value
    assert client.get("rate-limit", context={"plan": "free"}) == 100

    # Premium users get override value
    assert client.get("rate-limit", context={"plan": "pro"}) == 1000
    assert client.get("rate-limit", context={"plan": "enterprise"}) == 1000
```

## Testing Multiple Conditions

```python
def test_multiple_conditions():
    client = InMemoryReplaneClient()
    client.set_config(
        "feature",
        value=False,
        overrides=[
            {
                "name": "premium-us-users",
                "conditions": [
                    {"operator": "equals", "property": "plan", "expected": "premium"},
                    {"operator": "equals", "property": "region", "expected": "us"},
                ],
                "value": True,
            }
        ],
    )

    # Both conditions must match
    assert client.get("feature", context={"plan": "premium", "region": "us"}) is True
    assert client.get("feature", context={"plan": "premium", "region": "eu"}) is False
    assert client.get("feature", context={"plan": "free", "region": "us"}) is False
```

## Dynamic Config Updates

The in-memory client supports updating configs during tests:

```python
def test_config_updates():
    client = InMemoryReplaneClient({"feature": False})

    # Initially disabled
    assert client.get("feature") is False

    # Update the config
    client.set("feature", True)

    # Now enabled
    assert client.get("feature") is True
```

## Testing Subscriptions

Test that your code reacts to config changes:

```python
def test_subscription():
    client = InMemoryReplaneClient({"value": 1})
    changes = []

    def on_change(name, config):
        changes.append((name, config.value))

    client.subscribe(on_change)

    client.set("value", 2)
    client.set("value", 3)

    assert changes == [("value", 2), ("value", 3)]
```

## Testing Error Handling

Test how your code handles missing configs:

```python
import pytest
from replane.errors import ConfigNotFoundError
from replane.testing import InMemoryReplaneClient

def test_missing_config():
    client = InMemoryReplaneClient()

    with pytest.raises(ConfigNotFoundError) as exc_info:
        client.get("nonexistent")

    assert exc_info.value.config_name == "nonexistent"

def test_missing_with_default():
    client = InMemoryReplaneClient()

    # Should return default, not raise
    value = client.get("nonexistent", default="fallback")
    assert value == "fallback"
```

## Default Context in Tests

Set a default context for all test operations:

```python
def test_with_default_context():
    client = InMemoryReplaneClient(
        {"feature": False},
        context={"environment": "test"},
    )

    client.set_config(
        "feature",
        value=False,
        overrides=[
            {
                "name": "test-env",
                "conditions": [
                    {"operator": "equals", "property": "environment", "expected": "test"}
                ],
                "value": True,
            }
        ],
    )

    # Default context is used
    assert client.get("feature") is True
```

## Dependency Injection Pattern

For better testability, inject the Replane client into your code:

```python
# your_module.py
class FeatureService:
    def __init__(self, replane_client):
        self.config = replane_client

    def is_feature_enabled(self, user_id: str) -> bool:
        return self.config.get(
            "new-feature",
            context={"user_id": user_id}
        )

# test_your_module.py
from replane.testing import create_test_client
from your_module import FeatureService

def test_feature_service():
    client = create_test_client({"new-feature": True})
    service = FeatureService(client)

    assert service.is_feature_enabled("user-123") is True
```

## Context Manager Support

The in-memory client supports context managers for cleanup:

```python
def test_with_context_manager():
    with InMemoryReplaneClient({"key": "value"}) as client:
        assert client.get("key") == "value"
    # Client is closed after the block
```
