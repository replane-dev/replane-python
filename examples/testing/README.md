# Testing Example

This example demonstrates how to test applications that use the Replane SDK using the built-in `InMemoryReplaneClient` and `create_test_client` utilities.

## Prerequisites

- Python 3.10 or higher
- pytest

## Setup

1. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Run Tests

```bash
pytest -v
```

Or with coverage:

```bash
pytest -v --cov=app
```

## Files

- `app.py` - Sample application code that uses Replane
- `test_app.py` - Tests demonstrating various testing patterns

## Testing Patterns Demonstrated

### Basic Usage

```python
from replane.testing import create_test_client

def test_simple():
    client = create_test_client({
        "feature-enabled": True,
        "rate-limit": 100,
    })
    assert client.get("feature-enabled") is True
```

### Testing with Overrides

```python
from replane.testing import InMemoryReplaneClient

def test_with_overrides():
    client = InMemoryReplaneClient()
    client.set_config(
        "rate-limit",
        value=100,  # Default
        overrides=[{
            "name": "premium",
            "conditions": [
                {"operator": "equals", "property": "plan", "expected": "premium"}
            ],
            "value": 1000,
        }],
    )

    assert client.get("rate-limit", context={"plan": "free"}) == 100
    assert client.get("rate-limit", context={"plan": "premium"}) == 1000
```

### Testing Services with Dependency Injection

```python
import pytest
from replane.testing import create_test_client
from myapp import MyService

@pytest.fixture
def replane_client():
    return create_test_client({"config": "value"})

def test_service(replane_client):
    service = MyService(replane_client)
    result = service.do_something()
    assert result == expected
```

### Testing Config Change Subscriptions

```python
def test_subscriptions():
    client = create_test_client()
    changes = []

    client.subscribe(lambda name, config: changes.append(name))
    client.set("feature", True)

    assert "feature" in changes
```

## Key Testing Utilities

### `create_test_client(configs, context=None)`

Quick way to create a test client with initial values:

```python
replane = create_test_client({
    "feature": True,
    "limit": 100,
})
```

### `InMemoryReplaneClient`

Full-featured test client with support for:

- Setting simple values: `replane.set("key", value)`
- Setting configs with overrides: `replane.set_config("key", value, overrides=[...])`
- Default context: `InMemoryReplaneClient(context={"env": "test"})`
- Subscriptions: `client.subscribe(callback)`
- Context manager: `with client: ...`

## What This Example Shows

- Using `create_test_client` for simple test cases
- Using `InMemoryReplaneClient` for complex scenarios
- Testing plan-based overrides
- Testing user targeting
- Testing multiple conditions (AND logic)
- Using pytest fixtures for shared test setup
- Testing subscription callbacks
- Testing default values
