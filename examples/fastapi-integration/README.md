# FastAPI Integration Example

This example demonstrates how to integrate the Replane SDK with a FastAPI application using the async client for feature flags and dynamic configuration.

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

Or with uvicorn directly:

```bash
uvicorn app:app --reload --port 8000
```

The server will start on `http://localhost:8000`.

## API Endpoints

### `GET /`
Homepage that shows different content based on the `new-dashboard-enabled` feature flag.

```bash
curl http://localhost:8000/
```

### `GET /api/items`
List items with rate limiting info based on user's plan.

```bash
# As a free user
curl http://localhost:8000/api/items

# As a premium user
curl -H "X-User-Plan: premium" http://localhost:8000/api/items
```

### `POST /api/upload`
Upload endpoint with configurable max file size based on user's plan.

```bash
curl -X POST http://localhost:8000/api/upload
```

### `GET /api/config`
Debug endpoint showing current configuration values.

```bash
curl -H "X-User-ID: user-123" -H "X-User-Plan: premium" \
     http://localhost:8000/api/config
```

### `GET /health`
Health check endpoint showing Replane connection status.

```bash
curl http://localhost:8000/health
```

## API Documentation

FastAPI automatically generates OpenAPI documentation:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## What This Example Shows

- Using `AsyncReplane` with FastAPI's lifespan handler
- FastAPI dependency injection for Replane client
- Building evaluation context from request headers
- Using feature flags to control UI features
- Dynamic configuration for rate limits and upload sizes
- Middleware for maintenance mode
- Health check endpoint with Replane status
- Pydantic response models
