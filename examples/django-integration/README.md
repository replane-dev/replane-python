# Django Integration Example

This example demonstrates how to integrate the Replane SDK with a Django application for feature flags and dynamic configuration.

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
export REPLANE_SDK_KEY="your_sdk_key_here"
```

Or update the defaults in `config/settings.py`.

## Run

```bash
python manage.py runserver
```

The server will start on `http://localhost:8000`.

## Project Structure

```
django-integration/
├── manage.py
├── config/
│   ├── __init__.py
│   ├── settings.py      # Django settings with Replane config
│   ├── urls.py
│   └── wsgi.py
└── demo/
    ├── __init__.py
    ├── apps.py           # App config with Replane initialization
    ├── replane_client.py # Singleton client management
    ├── middleware.py     # Maintenance mode & context middleware
    ├── views.py          # Example views using Replane
    └── urls.py
```

## API Endpoints

### `GET /`

Homepage that shows different content based on the `new-dashboard-enabled` feature flag.

```bash
curl http://localhost:8000/
```

### `GET /api/items/`

List items with rate limiting info based on user's plan.

```bash
# As a free user
curl http://localhost:8000/api/items/

# As a premium user
curl -H "X-User-Plan: premium" http://localhost:8000/api/items/
```

### `POST /api/upload/`

Upload endpoint with configurable max file size based on user's plan.

```bash
curl -X POST http://localhost:8000/api/upload/
```

### `GET /api/config/`

Debug endpoint showing current configuration values.

```bash
curl -H "X-User-ID: user-123" -H "X-User-Plan: premium" \
     http://localhost:8000/api/config/
```

### `GET /health/`

Health check endpoint showing Replane connection status.

```bash
curl http://localhost:8000/health/
```

## Key Integration Points

### 1. Settings Configuration (`config/settings.py`)

```python
# Replane Configuration
REPLANE_BASE_URL = os.environ.get("REPLANE_BASE_URL", "...")
REPLANE_SDK_KEY = os.environ.get("REPLANE_SDK_KEY", "...")
REPLANE_DEFAULTS = {
    "rate_limit": 100,
    "new-dashboard-enabled": False,
}
```

### 2. App Initialization (`demo/apps.py`)

The Replane client is initialized when Django starts:

```python
class DemoConfig(AppConfig):
    def ready(self):
        from demo.replane_client import init_replane
        init_replane(
            base_url=settings.REPLANE_BASE_URL,
            sdk_key=settings.REPLANE_SDK_KEY,
            defaults=settings.REPLANE_DEFAULTS,
        )
```

### 3. Singleton Client (`demo/replane_client.py`)

```python
from demo.replane_client import get_replane

replane = get_replane()
user_client = replane.with_context({"user_id": "123"})
value = user_client.configs["feature_flag"]
```

### 4. Middleware (`demo/middleware.py`)

- Checks maintenance mode globally
- Builds user context from request headers
- Attaches context to `request.replane_context`

### 5. Using in Views (`demo/views.py`)

```python
from demo.replane_client import get_replane

class MyView(View):
    def get(self, request):
        client = get_replane()
        ctx = request.replane_context

        if client.get("new_feature", context=ctx):
            return JsonResponse({"feature": "enabled"})
        return JsonResponse({"feature": "disabled"})
```

## What This Example Shows

- Initializing `Replane` at Django startup
- Singleton pattern for sharing client across requests
- Custom middleware for maintenance mode
- Building evaluation context from request headers
- Using feature flags in class-based views
- Health check endpoint with Replane status
- Proper cleanup on application shutdown

## Production Considerations

1. **Use environment variables** for `REPLANE_BASE_URL` and `REPLANE_SDK_KEY`
2. **Set appropriate defaults** for all configs your app depends on
3. **Monitor the health endpoint** to ensure Replane connectivity
4. **Handle `RuntimeError`** if client initialization fails
5. **Consider using Django signals** for more complex initialization scenarios
