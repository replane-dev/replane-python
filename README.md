# Replane Python SDK

Python SDK for [Replane](https://replane.dev) - a dynamic configuration platform with real-time updates.

[![PyPI](https://img.shields.io/pypi/v/replane)](https://pypi.org/project/replane/)
[![CI](https://github.com/replane-dev/replane-python/actions/workflows/ci.yml/badge.svg)](https://github.com/replane-dev/replane-python/actions)
[![License](https://img.shields.io/github/license/replane-dev/replane-python)](https://github.com/replane-dev/replane-python/blob/main/LICENSE)
[![Community](https://img.shields.io/badge/discussions-join-blue?logo=github)](https://github.com/orgs/replane-dev/discussions)

## Features

- **Real-time updates** via Server-Sent Events (SSE)
- **Context-based overrides** for feature flags, A/B testing, and gradual rollouts
- **Zero dependencies** for sync client (stdlib only)
- **Both sync and async** clients available
- **Type-safe** with full type hints
- **Testing utilities** with in-memory client

## Installation

```bash
# Basic installation (sync client only, zero dependencies)
pip install replane

# With async support (adds httpx dependency)
pip install replane[async]
```

## Quick Start

### Synchronous Client

```python
from replane import Replane

# Using context manager (recommended)
with Replane(
    base_url="https://replane.example.com",
    sdk_key="sk_live_...",
) as client:
    # Get a simple config value
    rate_limit = client.get("rate-limit")

    # Get with context for override evaluation
    feature_enabled = client.get(
        "new-feature",
        context={"user_id": user.id, "plan": user.plan},
    )

    # Get with fallback default
    timeout = client.get("request-timeout", default=30)
```

### Asynchronous Client

Requires `pip install replane[async]`:

```python
from replane import AsyncReplane

async with AsyncReplane(
    base_url="https://replane.example.com",
    sdk_key="sk_live_...",
) as client:
    # get() is sync since it reads from local cache
    rate_limit = client.get("rate-limit")

    # With context
    enabled = client.get("feature", context={"plan": "premium"})
```

## Configuration Options

Both clients accept the same configuration:

```python
client = Replane(
    base_url="https://replane.example.com",
    sdk_key="sk_live_...",

    # Default context applied to all get() calls
    context={"environment": "production"},

    # Fallback values used if server is unavailable during init
    fallbacks={
        "rate-limit": 100,
        "feature-enabled": False,
    },

    # Configs that must exist (raises error if missing)
    required=["rate-limit", "feature-enabled"],

    # Timeouts in milliseconds
    request_timeout_ms=2000,
    initialization_timeout_ms=5000,
    retry_delay_ms=200,
    inactivity_timeout_ms=30000,
)
```

## Context-Based Overrides

Replane evaluates override rules client-side using the context you provide. Your context data never leaves your application.

```python
# Define context based on current user/request
context = {
    "user_id": "user-123",
    "plan": "premium",
    "region": "us-east",
    "is_beta_tester": True,
}

# Overrides are evaluated locally
value = client.get("feature-flag", context=context)
```

### Override Examples

**Percentage rollout** (gradual feature release):
```python
# Server config has 10% rollout based on user_id
# Same user always gets same result (deterministic hashing)
enabled = client.get("new-checkout", context={"user_id": user.id})
```

**Plan-based features**:
```python
max_items = client.get("max-items", context={"plan": user.plan})
# Returns different values for free/pro/enterprise plans
```

**Geographic targeting**:
```python
content = client.get("homepage-banner", context={"country": request.country})
```

## Subscribing to Changes

React to config changes in real-time:

```python
# Subscribe to all config changes
def on_any_change(name: str, config):
    print(f"Config {name} changed to {config.value}")

unsubscribe = client.subscribe(on_any_change)

# Subscribe to specific config
def on_feature_change(config):
    update_feature_state(config.value)

unsubscribe_feature = client.subscribe_config("my-feature", on_feature_change)

# Later: stop receiving updates
unsubscribe()
unsubscribe_feature()
```

For async clients, callbacks can be async:

```python
async def on_change(name: str, config):
    await notify_services(name, config.value)

client.subscribe(on_change)
```

## Error Handling

```python
from replane import (
    ReplaneError,
    ConfigNotFoundError,
    TimeoutError,
    AuthenticationError,
    NetworkError,
    ErrorCode,
)

try:
    value = client.get("my-config")
except ConfigNotFoundError as e:
    print(f"Config not found: {e.config_name}")
except TimeoutError as e:
    print(f"Timed out after {e.timeout_ms}ms")
except AuthenticationError:
    print("Invalid SDK key")
except ReplaneError as e:
    print(f"Error [{e.code}]: {e.message}")
```

## Testing

Use the in-memory client for unit tests:

```python
from replane.testing import create_test_client, InMemoryReplaneClient

# Simple usage
client = create_test_client({
    "feature-enabled": True,
    "rate-limit": 100,
})

assert client.get("feature-enabled") is True

# With overrides
client = InMemoryReplaneClient()
client.set_config(
    "feature",
    value=False,
    overrides=[{
        "name": "premium-users",
        "conditions": [
            {"operator": "in", "property": "plan", "expected": ["pro", "enterprise"]}
        ],
        "value": True,
    }],
)

assert client.get("feature", context={"plan": "free"}) is False
assert client.get("feature", context={"plan": "pro"}) is True
```

### Pytest Fixture Example

```python
import pytest
from replane.testing import create_test_client

@pytest.fixture
def replane_client():
    return create_test_client({
        "feature-flags": {"dark-mode": True, "new-ui": False},
        "rate-limits": {"default": 100, "premium": 1000},
    })

def test_feature_flag(replane_client):
    flags = replane_client.get("feature-flags")
    assert flags["dark-mode"] is True
```

## Manual Lifecycle Management

If you prefer not to use context managers:

```python
# Sync
client = Replane(base_url="...", sdk_key="...")
client.connect()  # Blocks until initialized
try:
    value = client.get("config")
finally:
    client.close()

# Async
client = AsyncReplane(base_url="...", sdk_key="...")
await client.connect()
try:
    value = client.get("config")
finally:
    await client.close()
```

## Framework Integration

### FastAPI

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from replane import AsyncReplane

client: AsyncReplane | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global client
    client = AsyncReplane(
        base_url="https://replane.example.com",
        sdk_key="sk_live_...",
    )
    await client.connect()
    yield
    await client.close()

app = FastAPI(lifespan=lifespan)

def get_replane() -> AsyncReplane:
    assert client is not None
    return client

@app.get("/items")
async def get_items(replane: AsyncReplane = Depends(get_replane)):
    max_items = replane.get("max-items", context={"plan": "free"})
    return {"max_items": max_items}
```

### Flask

```python
from flask import Flask, g
from replane import Replane

app = Flask(__name__)
replane_client: Replane | None = None

@app.before_first_request
def init_replane():
    global replane_client
    replane_client = Replane(
        base_url="https://replane.example.com",
        sdk_key="sk_live_...",
    )
    replane_client.connect()

@app.route("/items")
def get_items():
    max_items = replane_client.get("max-items")
    return {"max_items": max_items}
```

## Requirements

- Python 3.10+
- No dependencies for sync client
- `httpx` for async client (`pip install replane[async]`)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and contribution guidelines.

## Community

Have questions or want to discuss Replane? Join the conversation in [GitHub Discussions](https://github.com/orgs/replane-dev/discussions).

## License

MIT
