# API Reference

This page provides detailed API documentation for the Replane Python SDK.

## Clients

### SyncReplaneClient

```{eval-rst}
.. autoclass:: replane.SyncReplaneClient
   :members:
   :undoc-members:
   :show-inheritance:
```

### AsyncReplaneClient

```{eval-rst}
.. autoclass:: replane.AsyncReplaneClient
   :members:
   :undoc-members:
   :show-inheritance:
```

## Testing

### InMemoryReplaneClient

```{eval-rst}
.. autoclass:: replane.testing.InMemoryReplaneClient
   :members:
   :undoc-members:
   :show-inheritance:
```

### create_test_client

```{eval-rst}
.. autofunction:: replane.testing.create_test_client
```

## Types

### Config

```{eval-rst}
.. autoclass:: replane.Config
   :no-index:
```

**Attributes:**

- `name` (str): Unique identifier for this config.
- `value` (Any): The base/default value returned when no overrides match.
- `overrides` (tuple[Override, ...]): List of override rules evaluated in order.

### Override

```{eval-rst}
.. autoclass:: replane.Override
   :no-index:
```

**Attributes:**

- `name` (str): Name/description of this override rule.
- `conditions` (tuple[Condition, ...]): Conditions that must all match.
- `value` (Any): Value to return when conditions match.

### Conditions

```{eval-rst}
.. autoclass:: replane.PropertyCondition
   :no-index:

.. autoclass:: replane.SegmentationCondition
   :no-index:

.. autoclass:: replane.AndCondition
   :no-index:

.. autoclass:: replane.OrCondition
   :no-index:

.. autoclass:: replane.NotCondition
   :no-index:
```

### Context

Context is a `TypedDict` representing runtime context for override evaluation.
It's a dictionary with string keys and primitive values (`str`, `int`, `float`, `bool`, or `None`).

```python
from replane import Context

context: Context = {
    "user_id": "user-123",
    "plan": "premium",
    "region": "us-east",
    "is_beta": True,
}
```

## Errors

### ReplaneError

```{eval-rst}
.. autoclass:: replane.ReplaneError
   :members:
   :undoc-members:
   :show-inheritance:
```

### ErrorCode

```{eval-rst}
.. autoclass:: replane.ErrorCode
   :members:
   :undoc-members:
```

### Specific Errors

```{eval-rst}
.. autoclass:: replane.ConfigNotFoundError
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: replane.TimeoutError
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: replane.AuthenticationError
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: replane.NetworkError
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: replane.ClientClosedError
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: replane.NotInitializedError
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: replane.MissingDependencyError
   :members:
   :undoc-members:
   :show-inheritance:
```

## Version

```{eval-rst}
.. autodata:: replane.VERSION
.. autodata:: replane.VERSION_SHORT
```
