# Configuration

This page documents all configuration options for the Replane clients.

## Client Options

Both `SyncReplaneClient` and `AsyncReplaneClient` accept the same configuration options:

```python
from replane import SyncReplaneClient

client = SyncReplaneClient(
    # Required
    base_url="https://replane.example.com",
    sdk_key="sk_live_...",

    # Optional
    context={"environment": "production"},
    fallbacks={"rate-limit": 100, "feature-enabled": False},
    required=["rate-limit", "feature-enabled"],
    request_timeout_ms=2000,
    initialization_timeout_ms=5000,
    retry_delay_ms=200,
    inactivity_timeout_ms=30000,
)
```

### Required Options

#### `base_url`
- **Type:** `str`
- **Required:** Yes

The base URL of your Replane server.

```python
base_url="https://replane.example.com"
base_url="http://localhost:3000"  # Local development
```

#### `sdk_key`
- **Type:** `str`
- **Required:** Yes

Your SDK key from the Replane dashboard. SDK keys are scoped to a specific project and environment.

```python
sdk_key="sk_live_abc123..."  # Production
sdk_key="sk_test_xyz789..."  # Testing/staging
```

### Optional Options

#### `context`
- **Type:** `dict[str, str | int | float | bool | None]`
- **Default:** `{}`

Default context applied to all `get()` calls. This is merged with any context passed directly to `get()`.

```python
# Set default context
client = SyncReplaneClient(
    ...,
    context={
        "environment": "production",
        "region": "us-east",
    },
)

# This call uses the default context
value = client.get("config-name")

# This merges with default context
value = client.get("config-name", context={"user_id": "123"})
# Effective context: {"environment": "production", "region": "us-east", "user_id": "123"}
```

#### `fallbacks`
- **Type:** `dict[str, Any]`
- **Default:** `{}`

Fallback values used when configs can't be loaded from the server. This is useful for resilience - your application can still function with sensible defaults if the Replane server is unavailable.

```python
client = SyncReplaneClient(
    ...,
    fallbacks={
        "rate-limit": 100,
        "feature-enabled": False,
        "max-connections": 10,
    },
)
```

Fallbacks are used in two scenarios:
1. During initialization if a config isn't returned by the server
2. If `get()` is called before initialization completes

#### `required`
- **Type:** `list[str]`
- **Default:** `[]`

List of config names that must be present after initialization. If any required config is missing, initialization will fail with a `ConfigNotFoundError`.

```python
client = SyncReplaneClient(
    ...,
    required=["rate-limit", "feature-enabled"],
)
# Raises ConfigNotFoundError if either config is missing
```

This is useful for catching configuration errors early rather than at runtime.

#### `request_timeout_ms`
- **Type:** `int`
- **Default:** `2000` (2 seconds)

Timeout for individual HTTP requests to the Replane server.

```python
client = SyncReplaneClient(
    ...,
    request_timeout_ms=5000,  # 5 seconds
)
```

#### `initialization_timeout_ms`
- **Type:** `int`
- **Default:** `5000` (5 seconds)

Maximum time to wait for the client to initialize and receive configs from the server.

```python
client = SyncReplaneClient(
    ...,
    initialization_timeout_ms=10000,  # 10 seconds
)
```

If initialization times out, a `TimeoutError` is raised.

#### `retry_delay_ms`
- **Type:** `int`
- **Default:** `200` (0.2 seconds)

Initial delay between retry attempts when the connection fails. The delay increases exponentially with each retry (up to 30 seconds max).

```python
client = SyncReplaneClient(
    ...,
    retry_delay_ms=500,  # Start with 0.5 seconds
)
```

#### `inactivity_timeout_ms`
- **Type:** `int`
- **Default:** `30000` (30 seconds)

Maximum time without receiving any SSE events before the connection is considered stale and reconnected. The server sends periodic keepalive pings, so this timeout should be longer than the server's ping interval.

```python
client = SyncReplaneClient(
    ...,
    inactivity_timeout_ms=60000,  # 60 seconds
)
```

## Manual Lifecycle Management

If you prefer not to use context managers, you can manage the client lifecycle manually:

### Sync Client

```python
client = SyncReplaneClient(base_url="...", sdk_key="...")

# Connect and wait for initialization
client.connect()  # Blocks until ready

try:
    value = client.get("config")
finally:
    client.close()
```

You can also connect without waiting:

```python
client.connect(wait=False)  # Returns immediately

# Do other initialization...

# Wait for configs when needed
client.wait_for_init()
```

### Async Client

```python
client = AsyncReplaneClient(base_url="...", sdk_key="...")

await client.connect()

try:
    value = client.get("config")
finally:
    await client.close()
```

## Environment Variables

While the SDK doesn't read environment variables directly, a common pattern is:

```python
import os

client = SyncReplaneClient(
    base_url=os.environ["REPLANE_URL"],
    sdk_key=os.environ["REPLANE_SDK_KEY"],
)
```
