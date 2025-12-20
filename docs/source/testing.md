# Testing

The Replane SDK provides an in-memory client specifically designed for testing. This allows you to test your application without connecting to a real Replane server.

## In-Memory Client

The `InMemoryReplaneClient` provides the same interface as the real clients but stores all configs in memory:

```python
from replane.testing import InMemoryReplaneClient

# Create with initial configs
replane = InMemoryReplaneClient({
    "feature-enabled": True,
    "rate-limit": 100,
    "api-version": "v2",
})

# Use like the real client
assert replane.get("feature-enabled") is True
assert replane.get("rate-limit") == 100
```

## Using create_test_client

For convenience, use the `create_test_client` helper:

```python
from replane.testing import create_test_client

replane = create_test_client({
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
def replane():
    return create_test_client({
        "feature-enabled": True,
        "rate-limit": 100,
    })

def test_feature_flag(replane):
    assert replane.get("feature-enabled") is True

def test_rate_limit(replane):
    assert replane.get("rate-limit") == 100
```

## Testing with Overrides

Test override behavior by setting up configs with override rules:

```python
from replane.testing import InMemoryReplaneClient

def test_plan_based_rate_limits():
    replane = InMemoryReplaneClient()
    replane.set_config(
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
    assert replane.get("rate-limit", context={"plan": "free"}) == 100

    # Premium users get override value
    assert replane.get("rate-limit", context={"plan": "pro"}) == 1000
    assert replane.get("rate-limit", context={"plan": "enterprise"}) == 1000
```

## Testing Multiple Conditions

```python
def test_multiple_conditions():
    replane = InMemoryReplaneClient()
    replane.set_config(
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
    assert replane.get("feature", context={"plan": "premium", "region": "us"}) is True
    assert replane.get("feature", context={"plan": "premium", "region": "eu"}) is False
    assert replane.get("feature", context={"plan": "free", "region": "us"}) is False
```

## Dynamic Config Updates

The in-memory client supports updating configs during tests:

```python
def test_config_updates():
    replane = InMemoryReplaneClient({"feature": False})

    # Initially disabled
    assert replane.get("feature") is False

    # Update the config
    replane.set("feature", True)

    # Now enabled
    assert replane.get("feature") is True
```

## Testing Subscriptions

Test that your code reacts to config changes:

```python
def test_subscription():
    replane = InMemoryReplaneClient({"value": 1})
    changes = []

    def on_change(name, config):
        changes.append((name, config.value))

    replane.subscribe(on_change)

    replane.set("value", 2)
    replane.set("value", 3)

    assert changes == [("value", 2), ("value", 3)]
```

## Testing Error Handling

Test how your code handles missing configs:

```python
import pytest
from replane.errors import ConfigNotFoundError
from replane.testing import InMemoryReplaneClient

def test_missing_config():
    replane = InMemoryReplaneClient()

    with pytest.raises(ConfigNotFoundError) as exc_info:
        replane.get("nonexistent")

    assert exc_info.value.config_name == "nonexistent"

def test_missing_with_default():
    replane = InMemoryReplaneClient()

    # Should return default, not raise
    value = replane.get("nonexistent", default="fallback")
    assert value == "fallback"
```

## Default Context in Tests

Set a default context for all test operations:

```python
def test_with_default_context():
    replane = InMemoryReplaneClient(
        {"feature": False},
        context={"environment": "test"},
    )

    replane.set_config(
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
    assert replane.get("feature") is True
```

## Dependency Injection Pattern

For better testability, inject the Replane client into your code:

```python
# your_module.py
class FeatureService:
    def __init__(self, replane):
        self.replane = replane

    def is_feature_enabled(self, user_id: str) -> bool:
        return self.replane.get(
            "new-feature",
            context={"user_id": user_id}
        )

# test_your_module.py
from replane.testing import create_test_client
from your_module import FeatureService

def test_feature_service():
    replane = create_test_client({"new-feature": True})
    service = FeatureService(replane)

    assert service.is_feature_enabled("user-123") is True
```

## Context Manager Support

The in-memory client supports context managers for cleanup:

```python
def test_with_context_manager():
    with InMemoryReplaneClient({"key": "value"}) as replane:
        assert replane.get("key") == "value"
    # Client is closed after the block
```
