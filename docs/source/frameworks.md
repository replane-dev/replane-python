# Framework Integration

This guide shows how to integrate Replane with popular Python web frameworks.

## FastAPI

FastAPI's async nature makes it a perfect fit for the async Replane client.

### Basic Setup

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from replane import AsyncReplaneClient

# Global client instance
replane_client: AsyncReplaneClient | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage Replane client lifecycle."""
    global replane_client
    replane_client = AsyncReplaneClient(
        base_url="https://replane.example.com",
        sdk_key="sk_live_...",
    )
    await replane_client.connect()
    yield
    await replane_client.close()

app = FastAPI(lifespan=lifespan)

def get_replane() -> AsyncReplaneClient:
    """Dependency to get Replane client."""
    assert replane_client is not None
    return replane_client

@app.get("/items")
async def get_items(replane: AsyncReplaneClient = Depends(get_replane)):
    max_items = replane.get("max-items-per-page")
    return {"max_items": max_items}
```

### With User Context

```python
from fastapi import Request

@app.get("/features")
async def get_features(
    request: Request,
    replane: AsyncReplaneClient = Depends(get_replane),
):
    # Build context from request/user
    context = {
        "user_id": request.state.user.id,
        "plan": request.state.user.plan,
    }

    return {
        "dark_mode": replane.get("dark-mode-enabled", context=context),
        "beta_features": replane.get("beta-features", context=context),
    }
```

### Dependency with Context

Create a dependency that automatically includes user context:

```python
from fastapi import Request, Depends

class ReplaneWithContext:
    def __init__(self, client: AsyncReplaneClient, context: dict):
        self._client = client
        self._context = context

    def get(self, name: str, **kwargs):
        ctx = {**self._context, **kwargs.get("context", {})}
        return self._client.get(name, context=ctx, **{k: v for k, v in kwargs.items() if k != "context"})

def get_replane_with_context(
    request: Request,
    replane: AsyncReplaneClient = Depends(get_replane),
) -> ReplaneWithContext:
    context = {}
    if hasattr(request.state, "user"):
        context["user_id"] = request.state.user.id
        context["plan"] = request.state.user.plan
    return ReplaneWithContext(replane, context)

@app.get("/dashboard")
async def dashboard(config: ReplaneWithContext = Depends(get_replane_with_context)):
    # Context is automatically included
    show_analytics = config.get("show-analytics")
    return {"show_analytics": show_analytics}
```

## Flask

Flask works well with the synchronous Replane client.

### Basic Setup

```python
from flask import Flask, g
from replane import SyncReplaneClient

app = Flask(__name__)

# Store client at module level
replane_client: SyncReplaneClient | None = None

def get_replane() -> SyncReplaneClient:
    global replane_client
    if replane_client is None:
        replane_client = SyncReplaneClient(
            base_url="https://replane.example.com",
            sdk_key="sk_live_...",
        )
        replane_client.connect()
    return replane_client

@app.route("/items")
def get_items():
    client = get_replane()
    max_items = client.get("max-items-per-page")
    return {"max_items": max_items}
```

### With Application Factory

```python
from flask import Flask, current_app
from replane import SyncReplaneClient

def create_app():
    app = Flask(__name__)

    # Store in app config
    app.replane_client = None

    @app.before_request
    def init_replane():
        if app.replane_client is None:
            app.replane_client = SyncReplaneClient(
                base_url=app.config["REPLANE_URL"],
                sdk_key=app.config["REPLANE_SDK_KEY"],
            )
            app.replane_client.connect()

    return app

# In routes
@app.route("/features")
def features():
    client = current_app.replane_client
    return {"enabled": client.get("feature-enabled")}
```

### Flask Extension Pattern

```python
from flask import Flask, _app_ctx_stack
from replane import SyncReplaneClient

class FlaskReplane:
    def __init__(self, app: Flask | None = None):
        self._client: SyncReplaneClient | None = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask):
        app.extensions["replane"] = self

        @app.teardown_appcontext
        def teardown(exception):
            if self._client is not None:
                self._client.close()

    @property
    def client(self) -> SyncReplaneClient:
        if self._client is None:
            from flask import current_app
            self._client = SyncReplaneClient(
                base_url=current_app.config["REPLANE_URL"],
                sdk_key=current_app.config["REPLANE_SDK_KEY"],
            )
            self._client.connect()
        return self._client

# Usage
replane = FlaskReplane()

def create_app():
    app = Flask(__name__)
    app.config["REPLANE_URL"] = "https://replane.example.com"
    app.config["REPLANE_SDK_KEY"] = "sk_live_..."
    replane.init_app(app)
    return app

@app.route("/")
def index():
    return {"feature": replane.client.get("feature")}
```

## Django

Django can use either the sync or async client depending on your setup.

### Sync Setup (Traditional Django)

```python
# settings.py
REPLANE_URL = "https://replane.example.com"
REPLANE_SDK_KEY = "sk_live_..."

# replane_client.py
from django.conf import settings
from replane import SyncReplaneClient

_client: SyncReplaneClient | None = None

def get_client() -> SyncReplaneClient:
    global _client
    if _client is None:
        _client = SyncReplaneClient(
            base_url=settings.REPLANE_URL,
            sdk_key=settings.REPLANE_SDK_KEY,
        )
        _client.connect()
    return _client

# views.py
from django.http import JsonResponse
from .replane_client import get_client

def features_view(request):
    client = get_client()
    context = {"user_id": str(request.user.id)} if request.user.is_authenticated else {}
    return JsonResponse({
        "feature_enabled": client.get("feature", context=context),
    })
```

### Async Setup (Django 4.1+)

```python
# replane_client.py
from django.conf import settings
from replane import AsyncReplaneClient

_client: AsyncReplaneClient | None = None

async def get_client() -> AsyncReplaneClient:
    global _client
    if _client is None:
        _client = AsyncReplaneClient(
            base_url=settings.REPLANE_URL,
            sdk_key=settings.REPLANE_SDK_KEY,
        )
        await _client.connect()
    return _client

# views.py
from django.http import JsonResponse
from .replane_client import get_client

async def features_view(request):
    client = await get_client()
    return JsonResponse({
        "feature_enabled": client.get("feature"),
    })
```

### Django AppConfig

Initialize on app ready:

```python
# apps.py
from django.apps import AppConfig

class MyAppConfig(AppConfig):
    name = "myapp"

    def ready(self):
        from . import replane_client
        # Pre-warm the client (optional)
        # Note: This runs in sync context
```

## Starlette

Similar to FastAPI (Starlette is FastAPI's foundation):

```python
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from replane import AsyncReplaneClient

replane_client: AsyncReplaneClient | None = None

async def startup():
    global replane_client
    replane_client = AsyncReplaneClient(
        base_url="https://replane.example.com",
        sdk_key="sk_live_...",
    )
    await replane_client.connect()

async def shutdown():
    if replane_client:
        await replane_client.close()

async def homepage(request):
    feature = replane_client.get("feature")
    return JSONResponse({"feature": feature})

app = Starlette(
    routes=[Route("/", homepage)],
    on_startup=[startup],
    on_shutdown=[shutdown],
)
```

## aiohttp

```python
from aiohttp import web
from replane import AsyncReplaneClient

async def create_app():
    app = web.Application()

    async def on_startup(app):
        app["replane"] = AsyncReplaneClient(
            base_url="https://replane.example.com",
            sdk_key="sk_live_...",
        )
        await app["replane"].connect()

    async def on_cleanup(app):
        await app["replane"].close()

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    app.router.add_get("/", handler)
    return app

async def handler(request):
    client = request.app["replane"]
    return web.json_response({
        "feature": client.get("feature"),
    })

if __name__ == "__main__":
    web.run_app(create_app())
```

## General Best Practices

1. **Initialize once** - Create the client once at startup, not per-request
2. **Close on shutdown** - Always close the client when your application shuts down
3. **Use context managers** - When possible, use `with`/`async with` for automatic cleanup
4. **Handle errors** - Wrap initialization in try/except for graceful degradation
5. **Use fallbacks** - Configure fallback values for resilience
