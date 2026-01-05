# Replane Python SDK

Python SDK for [Replane](https://replane.dev) - a dynamic configuration platform with real-time updates.

## Features

- **Real-time updates** via Server-Sent Events (SSE)
- **Context-based overrides** for feature flags, A/B testing, and gradual rollouts
- **Zero dependencies** for sync client (stdlib only)
- **Both sync and async** clients available
- **Type-safe** with full type hints
- **Testing utilities** with in-memory client

## Quick Example

```python
from replane import Replane

# Using context manager (recommended)
with Replane(
    base_url="https://replane.example.com",
    sdk_key="rp_...",
) as replane:
    # Get a config value
    rate_limit = replane.configs["rate-limit"]

    # Get with context for override evaluation
    user_client = replane.with_context({"user_id": user.id, "plan": user.plan})
    feature_enabled = user_client.configs["new-feature"]
```

Or without context manager:

```python
replane = Replane(base_url="...", sdk_key="...")
replane.connect()

rate_limit = replane.configs["rate-limit"]

replane.close()
```

```{toctree}
:maxdepth: 2
:hidden:
:caption: Getting Started

installation
quickstart
```

```{toctree}
:maxdepth: 2
:hidden:
:caption: User Guide

configuration
overrides
testing
frameworks
```

```{toctree}
:maxdepth: 2
:hidden:
:caption: Reference

api
errors
```

```{toctree}
:hidden:
:caption: Development

CHANGELOG
CONTRIBUTING
GitHub Repository <https://github.com/replane-dev/replane-python>
```

## Indices and tables

```{eval-rst}
* :ref:`genindex`
* :ref:`modindex`
```
