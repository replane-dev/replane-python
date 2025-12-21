# Error Handling

The Replane SDK uses a hierarchy of exceptions to help you handle errors appropriately.

## Exception Hierarchy

```
ReplaneError (base class)
├── ConfigNotFoundError
├── TimeoutError
├── AuthenticationError
├── NetworkError
├── ClientClosedError
├── NotInitializedError
└── MissingDependencyError
```

## Error Codes

Each `ReplaneError` has a `code` attribute from the `ErrorCode` enum:

| Code | Description |
|------|-------------|
| `not_found` | Config doesn't exist |
| `timeout` | Operation timed out |
| `network_error` | Network request failed |
| `auth_error` | Authentication failed (invalid SDK key) |
| `forbidden` | Access denied |
| `server_error` | Server returned 5xx error |
| `client_error` | Client error (4xx) |
| `closed` | Client has been closed |
| `not_initialized` | Client not yet initialized |
| `missing_dependency` | Required dependency not installed |
| `unknown` | Unknown error |

## Handling Errors

### Basic Error Handling

```python
from replane import (
    Replane,
    ReplaneError,
    ConfigNotFoundError,
    TimeoutError,
    AuthenticationError,
)

try:
    with Replane(
        base_url="https://replane.example.com",
        sdk_key="rp_...",
    ) as replane:
        value = replane.get("my-config")
except ConfigNotFoundError as e:
    print(f"Config '{e.config_name}' not found")
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
    value = replane.get("config")
except ReplaneError as e:
    match e.code:
        case ErrorCode.NOT_FOUND:
            # Handle missing config
            value = default_value
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

### ConfigNotFoundError

Raised when requesting a config that doesn't exist.

```python
from replane import ConfigNotFoundError

try:
    value = replane.get("nonexistent-config")
except ConfigNotFoundError as e:
    print(f"Config not found: {e.config_name}")
    # Use a default value instead
    value = "default"
```

**Attributes:**
- `config_name: str` - Name of the missing config

**Prevention:** Use `default` parameter or `fallbacks` option:

```python
# With default
value = replane.get("config", default="fallback")

# With fallbacks during init
replane = Replane(
    ...,
    fallbacks={"config": "fallback"},
)
```

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
    replane.get("config")  # Raises ClientClosedError
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
    replane.get("config")  # May raise if not ready
except NotInitializedError:
    replane.wait_for_init()  # Wait then retry
    value = replane.get("config")
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
2. **Use fallbacks** for resilience against missing configs
3. **Log errors** with their codes for debugging
4. **Don't catch and ignore** - at minimum, log the error
5. **Use `default` parameter** instead of catching `ConfigNotFoundError` when appropriate

```python
# Good: specific handling
try:
    value = replane.get("critical-config")
except ConfigNotFoundError:
    logger.error("Critical config missing!")
    raise  # Re-raise for critical configs

# Good: graceful fallback
value = replane.get("optional-config", default="safe-default")

# Bad: silently ignoring
try:
    value = replane.get("config")
except ReplaneError:
    pass  # Don't do this!
```
