# Configuration

This page documents all configuration options for the Replane clients.

## Client Options

Both `Replane` and `AsyncReplane` accept the same configuration options:

```python
from replane import Replane

replane = Replane(
    # Required
    base_url="https://replane.example.com",
    sdk_key="rp_...",

    # Optional
    context={"environment": "production"},
    fallbacks={"rate-limit": 100, "feature-enabled": False},
    required=["rate-limit", "feature-enabled"],
    request_timeout_ms=2000,
    initialization_timeout_ms=5000,
    retry_delay_ms=200,
    inactivity_timeout_ms=30000,
    debug=False,
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
sdk_key="rp_abc123..."  # Production
sdk_key="rp_test_xyz789..."  # Testing/staging
```

### Optional Options

#### `context`
- **Type:** `dict[str, str | int | float | bool | None]`
- **Default:** `{}`

Default context applied to all `get()` calls. This is merged with any context passed directly to `get()`.

```python
# Set default context
replane = Replane(
    ...,
    context={
        "environment": "production",
        "region": "us-east",
    },
)

# This call uses the default context
value = replane.get("config-name")

# This merges with default context
value = replane.get("config-name", context={"user_id": "123"})
# Effective context: {"environment": "production", "region": "us-east", "user_id": "123"}
```

#### `fallbacks`
- **Type:** `dict[str, Any]`
- **Default:** `{}`

Fallback values used when configs can't be loaded from the server. This is useful for resilience - your application can still function with sensible defaults if the Replane server is unavailable.

```python
replane = Replane(
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
replane = Replane(
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
replane = Replane(
    ...,
    request_timeout_ms=5000,  # 5 seconds
)
```

#### `initialization_timeout_ms`
- **Type:** `int`
- **Default:** `5000` (5 seconds)

Maximum time to wait for the client to initialize and receive configs from the server.

```python
replane = Replane(
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
replane = Replane(
    ...,
    retry_delay_ms=500,  # Start with 0.5 seconds
)
```

#### `inactivity_timeout_ms`
- **Type:** `int`
- **Default:** `30000` (30 seconds)

Maximum time without receiving any SSE events before the connection is considered stale and reconnected. The server sends periodic keepalive pings, so this timeout should be longer than the server's ping interval.

```python
replane = Replane(
    ...,
    inactivity_timeout_ms=60000,  # 60 seconds
)
```

#### `debug`
- **Type:** `bool`
- **Default:** `False`

Enable debug logging to see detailed information about all client activity. This is useful for troubleshooting connection issues, understanding when configs are loaded, and diagnosing override evaluation.

```python
replane = Replane(
    ...,
    debug=True,  # Enable debug logging
)
```

When enabled, you'll see logs for:
- Client initialization parameters
- SSE connection attempts and status
- Each config loaded from the server
- Config retrieval with context and evaluated value
- SSE events received
- Reconnection attempts
- Client close operations

Example output:
```
2024-01-15 10:30:00 [DEBUG] replane: Initializing Replane: base_url=https://replane.example.com, ...
2024-01-15 10:30:00 [DEBUG] replane: connect() called, wait=True
2024-01-15 10:30:00 [DEBUG] replane: Connecting to SSE: host=replane.example.com, port=443, https=True
2024-01-15 10:30:00 [DEBUG] replane: Response status: 200 OK
2024-01-15 10:30:00 [DEBUG] replane: SSE event received: type=init
2024-01-15 10:30:00 [DEBUG] replane: Loaded config: rate-limit (value=100, overrides=2)
2024-01-15 10:30:00 [DEBUG] replane: Initialization complete: 5 configs loaded
```

## Manual Lifecycle Management

If you prefer not to use context managers, you can manage the client lifecycle manually:

### Sync Client

```python
replane = Replane(base_url="...", sdk_key="...")

# Connect and wait for initialization
replane.connect()  # Blocks until ready

try:
    value = replane.get("config")
finally:
    replane.close()
```

You can also connect without waiting:

```python
replane.connect(wait=False)  # Returns immediately

# Do other initialization...

# Wait for configs when needed
replane.wait_for_init()
```

### Async Client

```python
replane = AsyncReplane(base_url="...", sdk_key="...")

await replane.connect()

try:
    value = replane.get("config")
finally:
    await replane.close()
```

## Environment Variables

While the SDK doesn't read environment variables directly, a common pattern is:

```python
import os

replane = Replane(
    base_url=os.environ["REPLANE_URL"],
    sdk_key=os.environ["REPLANE_SDK_KEY"],
)
```
