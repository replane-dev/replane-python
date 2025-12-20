# Basic Asynchronous Example

This example demonstrates the basic usage of the Replane Python SDK with the asynchronous client.

## Prerequisites

- Python 3.10 or higher
- A running Replane server
- An SDK key from your Replane dashboard

## Setup

1. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Update configuration in `main.py`:

```python
BASE_URL = "https://your-replane-server.com"
SDK_KEY = "sk_your_sdk_key_here"
```

## Run

```bash
python main.py
```

## What This Example Shows

- Using the `AsyncReplaneClient` with async context manager
- Reading feature flags and configs (sync read from local cache)
- Passing context for override evaluation
- Using default values for missing configs
- Manual async client lifecycle
- Subscribing to config changes (sync and async callbacks)
- Real-time config updates

## Note on `client.get()`

The `get()` method is intentionally synchronous even in the async client because it only reads from the local in-memory cache. There's no I/O involved, so there's no benefit to making it async. The SSE connection that keeps the cache updated runs in a background task.
