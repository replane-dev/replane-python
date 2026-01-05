# Replane Python SDK

Python SDK for [Replane](https://replane.dev) - a dynamic configuration platform with real-time updates.

[![PyPI](https://img.shields.io/pypi/v/replane)](https://pypi.org/project/replane/)
[![CI](https://github.com/replane-dev/replane-python/actions/workflows/main.yml/badge.svg)](https://github.com/replane-dev/replane-python/actions)
[![License](https://img.shields.io/github/license/replane-dev/replane-python)](https://github.com/replane-dev/replane-python/blob/main/LICENSE)
[![Community](https://img.shields.io/badge/discussions-join-blue?logo=github)](https://github.com/orgs/replane-dev/discussions)

> **Tip:** Get started instantly with [Replane Cloud](https://cloud.replane.dev) — no infrastructure required.

## Features

- **Real-time updates** via Server-Sent Events (SSE)
- **Context-based overrides** for feature flags, A/B testing, and gradual rollouts
- **Zero dependencies** for sync client (stdlib only)
- **Both sync and async** clients available
- **Type-safe** with TypedDict support and full type hints
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
    base_url="https://cloud.replane.dev",  # or your self-hosted URL
    sdk_key="rp_...",
) as replane:
    # Get a simple config value
    rate_limit = replane.configs["rate-limit"]

    # Get with context for override evaluation
    user_client = replane.with_context({"user_id": user.id, "plan": user.plan})
    feature_enabled = user_client.configs["new-feature"]

    # Get with fallback default
    timeout = replane.configs.get("request-timeout", 30)
```

### Asynchronous Client

Requires `pip install replane[async]`:

```python
from replane import AsyncReplane

async with AsyncReplane(
    base_url="https://replane.example.com",
    sdk_key="rp_...",
) as replane:
    # Access configs from local cache
    rate_limit = replane.configs["rate-limit"]

    # With context
    enabled = replane.with_context({"plan": "premium"}).configs["feature"]
```

### Type-Safe with Generated Types (Recommended)

Generate TypedDict types from your Replane dashboard for full type safety:

```python
from replane import Replane
from replane_types import Configs  # Generated from Replane dashboard

# Use the Configs TypedDict as a type parameter
with Replane[Configs](
    base_url="https://cloud.replane.dev",
    sdk_key="rp_...",
) as replane:
    # Access configs with dictionary-style notation
    settings = replane.configs["app-settings"]

    # Full type safety - IDE knows the structure of settings
    print(settings["maxUploadSizeMb"])
    print(settings["allowedFileTypes"])

    # Check if config exists
    if "feature-flag" in replane.configs:
        flag = replane.configs["feature-flag"]

    # Safe access with default
    timeout = replane.configs.get("timeout", 30)
```

The `.configs` property provides:

- **Dictionary-style access** with `replane.configs["config-name"]`
- **Type inference** when using generated TypedDict types
- **Override evaluation** using the default context
- **Familiar dict methods**: `.get()`, `.keys()`, `in` operator

## Configuration Options

Both clients accept the same configuration:

```python
replane = Replane(
    base_url="https://replane.example.com",
    sdk_key="rp_...",

    # Default context applied to all config evaluations
    context={"environment": "production"},

    # Default values used if server is unavailable during init
    defaults={
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

    # Custom agent identifier for User-Agent header
    agent="my-app/1.0.0",

    # Enable debug logging
    debug=True,
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

# Overrides are evaluated locally using with_context()
value = replane.with_context(context).configs["feature-flag"]
```

### Scoped Clients with `with_context()`

Create scoped clients for specific users or requests using `with_context()`:

```python
with Replane(
    base_url="https://cloud.replane.dev",
    sdk_key="rp_...",
) as replane:
    # Create a scoped client for a specific user
    user_client = replane.with_context({
        "user_id": user.id,
        "plan": user.plan,
    })

    # All operations use the merged context
    rate_limit = user_client.configs["rate-limit"]
    settings = user_client.configs["app-settings"]

    # Can be chained for additional context
    request_client = user_client.with_context({"region": request.region})
```

The original client is unaffected - scoped clients are lightweight wrappers.

### Scoped Defaults with `with_defaults()`

Create scoped clients with fallback values using `with_defaults()`:

```python
with Replane(
    base_url="https://cloud.replane.dev",
    sdk_key="rp_...",
) as replane:
    # Create a client with fallback defaults
    safe_client = replane.with_defaults({
        "timeout": 30,
        "max-retries": 3,
    })

    # Returns the default if config doesn't exist
    timeout = safe_client.configs["timeout"]  # 30 if not configured

    # Chain with with_context() for both features
    user_client = replane.with_context({"plan": "premium"}).with_defaults({
        "rate-limit": 1000,
    })
```

Explicit defaults in `.configs.get()` take precedence over scoped defaults.

### Override Examples

**Percentage rollout** (gradual feature release):

```python
# Server config has 10% rollout based on user_id
# Same user always gets same result (deterministic hashing)
enabled = replane.with_context({"user_id": user.id}).configs["new-checkout"]
```

**Plan-based features**:

```python
max_items = replane.with_context({"plan": user.plan}).configs["max-items"]
# Returns different values for free/pro/enterprise plans
```

**Geographic targeting**:

```python
content = replane.with_context({"country": request.country}).configs["homepage-banner"]
```

## Subscribing to Changes

React to config changes in real-time:

```python
# Subscribe to all config changes
def on_any_change(name: str, config):
    print(f"Config {name} changed to {config.value}")

unsubscribe = replane.subscribe(on_any_change)

# Subscribe to specific config
def on_feature_change(config):
    update_feature_state(config.value)

unsubscribe_feature = replane.subscribe_config("my-feature", on_feature_change)

# Later: stop receiving updates
unsubscribe()
unsubscribe_feature()
```

For async clients, callbacks can be async:

```python
async def on_change(name: str, config):
    await notify_services(name, config.value)

replane.subscribe(on_change)
```

## Error Handling

```python
from replane import (
    ReplaneError,
    TimeoutError,
    AuthenticationError,
    NetworkError,
    ErrorCode,
)

try:
    value = replane.configs["my-config"]
except KeyError as e:
    print(f"Config not found: {e}")
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
replane = create_test_client({
    "feature-enabled": True,
    "rate-limit": 100,
})

assert replane.configs["feature-enabled"] is True

# With overrides
replane = InMemoryReplaneClient()
replane.set_config(
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

assert replane.with_context({"plan": "free"}).configs["feature"] is False
assert replane.with_context({"plan": "pro"}).configs["feature"] is True
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
    flags = replane_client.configs["feature-flags"]
    assert flags["dark-mode"] is True
```

## Manual Lifecycle Management

If you prefer not to use context managers:

```python
# Sync
replane = Replane(base_url="...", sdk_key="...")
replane.connect()  # Blocks until initialized
try:
    value = replane.configs["config"]
finally:
    replane.close()

# Async
replane = AsyncReplane(base_url="...", sdk_key="...")
await replane.connect()
try:
    value = replane.configs["config"]
finally:
    await replane.close()
```

## Framework Integration

### FastAPI

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from replane import AsyncReplane

_replane: AsyncReplane | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _replane
    _replane = AsyncReplane(
        base_url="https://replane.example.com",
        sdk_key="rp_...",
    )
    await _replane.connect()
    yield
    await _replane.close()

app = FastAPI(lifespan=lifespan)

def get_replane() -> AsyncReplane:
    assert _replane is not None
    return _replane

@app.get("/items")
async def get_items(replane: AsyncReplane = Depends(get_replane)):
    max_items = replane.with_context({"plan": "free"}).configs["max-items"]
    return {"max_items": max_items}
```

### Flask

```python
from flask import Flask, g
from replane import Replane

app = Flask(__name__)
_replane: Replane | None = None

@app.before_first_request
def init_replane():
    global _replane
    _replane = Replane(
        base_url="https://replane.example.com",
        sdk_key="rp_...",
    )
    _replane.connect()

@app.route("/items")
def get_items():
    max_items = _replane.configs["max-items"]
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
