# Error Handling

The Replane SDK uses a hierarchy of exceptions to help you handle errors appropriately.

## Exception Hierarchy

```
ReplaneError (base class)
├── ConfigNotFoundError (used for required configs at init time)
├── TimeoutError
├── AuthenticationError
├── NetworkError
├── ClientClosedError
├── NotInitializedError
└── MissingDependencyError
```

Note: Accessing a missing config via `replane.configs["name"]` raises a standard `KeyError`, not `ConfigNotFoundError`. Use `replane.configs.get("name", default)` to avoid exceptions.

## Error Codes

Each `ReplaneError` has a `code` attribute from the `ErrorCode` enum:

| Code                 | Description                             |
| -------------------- | --------------------------------------- |
| `not_found`          | Config doesn't exist (required configs) |
| `timeout`            | Operation timed out                     |
| `network_error`      | Network request failed                  |
| `auth_error`         | Authentication failed (invalid SDK key) |
| `forbidden`          | Access denied                           |
| `server_error`       | Server returned 5xx error               |
| `client_error`       | Client error (4xx)                      |
| `closed`             | Client has been closed                  |
| `not_initialized`    | Client not yet initialized              |
| `missing_dependency` | Required dependency not installed       |
| `unknown`            | Unknown error                           |

## Handling Errors

### Basic Error Handling

```python
from replane import (
    Replane,
    ReplaneError,
    TimeoutError,
    AuthenticationError,
)

try:
    with Replane(
        base_url="https://replane.example.com",
        sdk_key="rp_...",
    ) as replane:
        value = replane.configs["my-config"]
except KeyError as e:
    print(f"Config not found: {e}")
except TimeoutError as e:
    print(f"Timed out after {e.timeout_ms}ms")
except AuthenticationError:
    print("Invalid SDK key - check your configuration")
except ReplaneError as e:
    print(f"Replane error [{e.code}]: {e.message}")
```

### Using Error Codes

```python
from replane import ReplaneError, ErrorCode

try:
    replane.connect()
except ReplaneError as e:
    match e.code:
        case ErrorCode.TIMEOUT:
            # Maybe retry
            pass
        case ErrorCode.AUTH_ERROR:
            # Log and alert
            logger.critical("Replane authentication failed!")
        case _:
            # Generic handling
            logger.error(f"Replane error: {e}")
```

## Specific Exceptions

### KeyError (Missing Config)

Accessing a missing config via bracket notation raises a standard `KeyError`:

```python
try:
    value = replane.configs["nonexistent-config"]
except KeyError as e:
    print(f"Config not found: {e}")
    value = "default"
```

**Prevention:** Use `.get()` method or `defaults` option:

```python
# With get() method
value = replane.configs.get("config", "fallback")

# With defaults during init
replane = Replane(
    ...,
    defaults={"config": "fallback"},
)

# With with_defaults()
safe_client = replane.with_defaults({"config": "fallback"})
value = safe_client.configs["config"]  # Returns "fallback" if not configured
```

### ConfigNotFoundError

Raised when required configs are missing during initialization.

```python
from replane import Replane, ConfigNotFoundError

try:
    with Replane(
        ...,
        required=["critical-config-1", "critical-config-2"],
    ) as replane:
        pass
except ConfigNotFoundError as e:
    print(f"Missing required configs: {e}")
```

**Attributes:**

- `config_name: str` - Name or description of missing config(s)

### TimeoutError

Raised when an operation exceeds its timeout.

```python
from replane import TimeoutError

try:
    replane.connect()
except TimeoutError as e:
    print(f"Connection timed out after {e.timeout_ms}ms")
```

**Attributes:**

- `timeout_ms: int | None` - Timeout value in milliseconds

**Prevention:** Increase timeout values:

```python
replane = Replane(
    ...,
    initialization_timeout_ms=10000,  # 10 seconds
    request_timeout_ms=5000,  # 5 seconds
)
```

### AuthenticationError

Raised when the SDK key is invalid or missing.

```python
from replane import AuthenticationError

try:
    replane.connect()
except AuthenticationError:
    print("Check your SDK key!")
```

**Common causes:**

- Invalid SDK key
- SDK key for wrong environment
- Revoked SDK key

### NetworkError

Raised when a network request fails.

```python
from replane import NetworkError

try:
    replane.connect()
except NetworkError as e:
    print(f"Network error: {e.message}")
    if e.__cause__:
        print(f"Caused by: {e.__cause__}")
```

**Common causes:**

- Server unreachable
- DNS resolution failed
- Connection refused
- SSL/TLS errors

### ClientClosedError

Raised when attempting operations on a closed client.

```python
from replane import ClientClosedError

replane = Replane(...)
replane.connect()
replane.close()

try:
    _ = replane.configs["config"]  # Raises ClientClosedError
except ClientClosedError:
    print("Client was already closed")
```

### NotInitializedError

Raised when the client hasn't finished initializing.

```python
from replane import NotInitializedError

replane = Replane(...)
replane.connect(wait=False)  # Don't wait

try:
    _ = replane.configs["config"]  # May raise if not ready
except NotInitializedError:
    replane.wait_for_init()  # Wait then retry
    value = replane.configs["config"]
```

### MissingDependencyError

Raised when using features that require optional dependencies.

```python
from replane import AsyncReplane, MissingDependencyError

try:
    replane = AsyncReplane(...)
except MissingDependencyError as e:
    print(f"Missing: {e.dependency}")
    print(f"Install with: pip install replane[async]")
```

**Attributes:**

- `dependency: str` - Name of the missing package
- `feature: str` - Feature that requires the dependency

## Error Cause Chain

Errors preserve the original cause for debugging:

```python
try:
    replane.connect()
except ReplaneError as e:
    print(f"Error: {e.message}")
    if e.__cause__:
        print(f"Original error: {e.__cause__}")
```

## Best Practices

1. **Catch specific exceptions first**, then fall back to `ReplaneError`
2. **Use defaults** for resilience against missing configs
3. **Log errors** with their codes for debugging
4. **Don't catch and ignore** - at minimum, log the error
5. **Use `.get()` method** instead of catching `KeyError` when appropriate

```python
# Good: specific handling
try:
    value = replane.configs["critical-config"]
except KeyError:
    logger.error("Critical config missing!")
    raise  # Re-raise for critical configs

# Good: graceful fallback
value = replane.configs.get("optional-config", "safe-default")

# Bad: silently ignoring
try:
    value = replane.configs["config"]
except KeyError:
    pass  # Don't do this!
```
