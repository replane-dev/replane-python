# Flask Integration Example

This example demonstrates how to integrate the Replane SDK with a Flask web application for feature flags and dynamic configuration.

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

3. Set environment variables:

```bash
export REPLANE_BASE_URL="https://your-replane-server.com"
export REPLANE_SDK_KEY="sk_your_sdk_key_here"
```

Or update the defaults in `app.py`.

## Run

```bash
python app.py
```

The server will start on `http://localhost:5000`.

## API Endpoints

### `GET /`
Homepage that shows different content based on the `new-dashboard-enabled` feature flag.

```bash
curl http://localhost:5000/
```

### `GET /api/items`
List items with rate limiting info based on user's plan.

```bash
# As a free user
curl http://localhost:5000/api/items

# As a premium user
curl -H "X-User-Plan: premium" http://localhost:5000/api/items
```

### `POST /api/upload`
Upload endpoint with configurable max file size based on user's plan.

```bash
curl -X POST http://localhost:5000/api/upload
```

### `GET /api/config`
Debug endpoint showing current configuration values.

```bash
curl -H "X-User-ID: user-123" -H "X-User-Plan: premium" \
     http://localhost:5000/api/config
```

## What This Example Shows

- Initializing `SyncReplaneClient` at application startup
- Building evaluation context from request headers
- Using feature flags to control UI features
- Dynamic configuration for rate limits and upload sizes
- Proper cleanup on application shutdown
- Context-based override evaluation
