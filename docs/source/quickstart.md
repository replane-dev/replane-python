# Quickstart

This guide will help you get started with the Replane Python SDK in minutes.

## Prerequisites

1. A Replane server running (self-hosted or cloud)
2. An SDK key from your Replane dashboard
3. Python 3.10+

## Basic Usage

### Synchronous Client

The sync client is the simplest way to get started:

```python
from replane import SyncReplaneClient

# Using context manager (recommended)
with SyncReplaneClient(
    base_url="https://replane.example.com",
    sdk_key="sk_live_...",
) as replane:
    # Get a simple config value
    rate_limit = replane.get("rate-limit")
    print(f"Rate limit: {rate_limit}")

    # Get with context for override evaluation
    feature_enabled = replane.get(
        "new-feature",
        context={"user_id": "user-123", "plan": "premium"},
    )
    print(f"Feature enabled: {feature_enabled}")

    # Get with fallback default
    timeout = replane.get("request-timeout", default=30)
    print(f"Timeout: {timeout}")
```

### Asynchronous Client

For async applications (FastAPI, aiohttp, etc.), use the async client:

```python
from replane import AsyncReplaneClient

async def main():
    async with AsyncReplaneClient(
        base_url="https://replane.example.com",
        sdk_key="sk_live_...",
    ) as client:
        # get() is sync - it reads from local cache
        rate_limit = client.get("rate-limit")

        # With context
        enabled = client.get("feature", context={"plan": "premium"})

# Run with asyncio
import asyncio
asyncio.run(main())
```

```{note}
The async client requires the `async` extra: `pip install replane[async]`
```

## Understanding Config Values

Configs in Replane can be any JSON-serializable value:

```python
# Boolean (feature flags)
dark_mode = client.get("dark-mode-enabled")  # True/False

# Number (limits, thresholds)
max_items = client.get("max-items-per-page")  # 50

# String
api_version = client.get("api-version")  # "v2"

# Object
settings = client.get("app-settings")  # {"theme": "dark", "lang": "en"}

# Array
allowed_origins = client.get("cors-origins")  # ["localhost", "example.com"]
```

## Using Context for Overrides

Context allows you to get different values based on runtime conditions:

```python
# Different rate limits per plan
rate_limit = client.get(
    "rate-limit",
    context={"plan": user.subscription_plan}
)
# Returns 100 for "free", 1000 for "pro", 10000 for "enterprise"

# Feature flags per user
show_beta = client.get(
    "show-beta-features",
    context={
        "user_id": user.id,
        "is_beta_tester": user.is_beta,
    }
)
```

Context is evaluated locally - your data never leaves your application.

## Subscribing to Changes

React to config changes in real-time:

```python
def on_config_change(name: str, config):
    print(f"Config '{name}' changed to: {config.value}")
    # Invalidate caches, update UI, etc.

# Subscribe to all changes
unsubscribe = client.subscribe(on_config_change)

# Or subscribe to specific config
def on_rate_limit_change(config):
    update_rate_limiter(config.value)

unsubscribe_rate = client.subscribe_config("rate-limit", on_rate_limit_change)

# Later, stop receiving updates
unsubscribe()
unsubscribe_rate()
```

## Error Handling

Handle errors gracefully:

```python
from replane import (
    SyncReplaneClient,
    ConfigNotFoundError,
    TimeoutError,
    AuthenticationError,
    ReplaneError,
)

try:
    with SyncReplaneClient(
        base_url="https://replane.example.com",
        sdk_key="sk_live_...",
    ) as client:
        value = client.get("my-config")
except ConfigNotFoundError as e:
    print(f"Config not found: {e.config_name}")
except TimeoutError as e:
    print(f"Connection timed out: {e.timeout_ms}ms")
except AuthenticationError:
    print("Invalid SDK key")
except ReplaneError as e:
    print(f"Error [{e.code}]: {e.message}")
```

## Next Steps

- {doc}`configuration` - Learn about all client options
- {doc}`overrides` - Deep dive into context-based overrides
- {doc}`testing` - How to test your application
- {doc}`frameworks` - Integration with popular frameworks
