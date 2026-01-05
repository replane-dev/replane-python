# Framework Integration

This guide shows how to integrate Replane with popular Python web frameworks.

## FastAPI

FastAPI's async nature makes it a perfect fit for the async Replane client.

### Basic Setup

```python
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Depends
from replane import AsyncReplane

# Global client instance
_replane: AsyncReplane | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage Replane client lifecycle."""
    global _replane
    _replane = AsyncReplane(
        base_url="https://replane.example.com",
        sdk_key="rp_...",
    )
    await _replane.connect()
    yield
    await _replane.close()

app = FastAPI(lifespan=lifespan)

def get_replane() -> AsyncReplane:
    """Dependency to get Replane client."""
    assert _replane is not None
    return _replane

# Define reusable dependency type
Replane = Annotated[AsyncReplane, Depends(get_replane)]

@app.get("/items")
async def get_items(replane: Replane):
    max_items = replane.configs["max-items-per-page"]
    return {"max_items": max_items}
```

### With User Context

```python
from fastapi import Request

@app.get("/features")
async def get_features(request: Request, replane: Replane):
    # Build context from request/user
    user_client = replane.with_context({
        "user_id": request.state.user.id,
        "plan": request.state.user.plan,
    })

    return {
        "dark_mode": user_client.configs["dark-mode-enabled"],
        "beta_features": user_client.configs["beta-features"],
    }
```

### Dependency with Context

Create a dependency that automatically includes user context:

```python
from fastapi import Request, Depends
from replane._async import ContextualAsyncReplane

def get_replane_with_context(
    request: Request,
    replane: Replane,
) -> ContextualAsyncReplane:
    context = {}
    if hasattr(request.state, "user"):
        context["user_id"] = request.state.user.id
        context["plan"] = request.state.user.plan
    return replane.with_context(context)

ReplaneWithContext = Annotated[ContextualAsyncReplane, Depends(get_replane_with_context)]

@app.get("/dashboard")
async def dashboard(replane: ReplaneWithContext):
    # Context is automatically included
    show_analytics = replane.configs["show-analytics"]
    return {"show_analytics": show_analytics}
```

## Flask

Flask works well with the synchronous Replane client.

### Basic Setup

```python
from flask import Flask, g
from replane import Replane

app = Flask(__name__)

# Store client at module level
_replane: Replane | None = None

def get_replane() -> Replane:
    global _replane
    if _replane is None:
        _replane = Replane(
            base_url="https://replane.example.com",
            sdk_key="rp_...",
        )
        _replane.connect()
    return _replane

@app.route("/items")
def get_items():
    replane = get_replane()
    max_items = replane.configs["max-items-per-page"]
    return {"max_items": max_items}
```

### With Application Factory

```python
from flask import Flask, current_app
from replane import Replane

def create_app():
    app = Flask(__name__)

    # Store in app config
    app.replane = None

    @app.before_request
    def init_replane():
        if app.replane is None:
            app.replane = Replane(
                base_url=app.config["REPLANE_URL"],
                sdk_key=app.config["REPLANE_SDK_KEY"],
            )
            app.replane.connect()

    return app

# In routes
@app.route("/features")
def features():
    replane = current_app.replane
    return {"enabled": replane.configs["feature-enabled"]}
```

### Flask Extension Pattern

```python
from flask import Flask, _app_ctx_stack
from replane import Replane

class FlaskReplane:
    def __init__(self, app: Flask | None = None):
        self._replane: Replane | None = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask):
        app.extensions["replane"] = self

        @app.teardown_appcontext
        def teardown(exception):
            if self._replane is not None:
                self._replane.close()

    @property
    def client(self) -> Replane:
        if self._replane is None:
            from flask import current_app
            self._replane = Replane(
                base_url=current_app.config["REPLANE_URL"],
                sdk_key=current_app.config["REPLANE_SDK_KEY"],
            )
            self._replane.connect()
        return self._replane

# Usage
replane = FlaskReplane()

def create_app():
    app = Flask(__name__)
    app.config["REPLANE_URL"] = "https://replane.example.com"
    app.config["REPLANE_SDK_KEY"] = "rp_..."
    replane.init_app(app)
    return app

@app.route("/")
def index():
    return {"feature": replane.client.configs["feature"]}
```

## Django

Django can use either the sync or async client depending on your setup.

### Sync Setup (Traditional Django)

```python
# settings.py
REPLANE_URL = "https://replane.example.com"
REPLANE_SDK_KEY = "rp_..."

# replane_client.py
from django.conf import settings
from replane import Replane

_replane: Replane | None = None

def get_replane() -> Replane:
    global _replane
    if _replane is None:
        _replane = Replane(
            base_url=settings.REPLANE_URL,
            sdk_key=settings.REPLANE_SDK_KEY,
        )
        _replane.connect()
    return _replane

# views.py
from django.http import JsonResponse
from .replane_client import get_replane

def features_view(request):
    replane = get_replane()
    if request.user.is_authenticated:
        user_client = replane.with_context({"user_id": str(request.user.id)})
        feature_enabled = user_client.configs["feature"]
    else:
        feature_enabled = replane.configs["feature"]
    return JsonResponse({
        "feature_enabled": feature_enabled,
    })
```

### Async Setup (Django 4.1+)

```python
# replane_client.py
from django.conf import settings
from replane import AsyncReplane

_replane: AsyncReplane | None = None

async def get_replane() -> AsyncReplane:
    global _replane
    if _replane is None:
        _replane = AsyncReplane(
            base_url=settings.REPLANE_URL,
            sdk_key=settings.REPLANE_SDK_KEY,
        )
        await _replane.connect()
    return _replane

# views.py
from django.http import JsonResponse
from .replane_client import get_replane

async def features_view(request):
    replane = await get_replane()
    return JsonResponse({
        "feature_enabled": replane.configs["feature"],
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
from replane import AsyncReplane

_replane: AsyncReplane | None = None

async def startup():
    global _replane
    _replane = AsyncReplane(
        base_url="https://replane.example.com",
        sdk_key="rp_...",
    )
    await _replane.connect()

async def shutdown():
    if _replane:
        await _replane.close()

async def homepage(request):
    feature = _replane.configs["feature"]
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
from replane import AsyncReplane

async def create_app():
    app = web.Application()

    async def on_startup(app):
        app["replane"] = AsyncReplane(
            base_url="https://replane.example.com",
            sdk_key="rp_...",
        )
        await app["replane"].connect()

    async def on_cleanup(app):
        await app["replane"].close()

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    app.router.add_get("/", handler)
    return app

async def handler(request):
    replane = request.app["replane"]
    return web.json_response({
        "feature": replane.configs["feature"],
    })

if __name__ == "__main__":
    web.run_app(create_app())
```

## General Best Practices

1. **Initialize once** - Create the client once at startup, not per-request
2. **Close on shutdown** - Always close the client when your application shuts down
3. **Use context managers** - When possible, use `with`/`async with` for automatic cleanup
4. **Handle errors** - Wrap initialization in try/except for graceful degradation
5. **Use defaults** - Configure default values for resilience
