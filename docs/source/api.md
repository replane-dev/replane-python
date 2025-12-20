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
   :members:
   :undoc-members:
```

### Override

```{eval-rst}
.. autoclass:: replane.Override
   :members:
   :undoc-members:
```

### Conditions

```{eval-rst}
.. autoclass:: replane.PropertyCondition
   :members:
   :undoc-members:

.. autoclass:: replane.SegmentationCondition
   :members:
   :undoc-members:

.. autoclass:: replane.AndCondition
   :members:
   :undoc-members:

.. autoclass:: replane.OrCondition
   :members:
   :undoc-members:

.. autoclass:: replane.NotCondition
   :members:
   :undoc-members:
```

### Context

```{eval-rst}
.. autoclass:: replane.Context
   :members:
   :undoc-members:
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
