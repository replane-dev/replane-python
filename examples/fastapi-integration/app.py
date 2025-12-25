"""FastAPI integration example with Replane.

This example shows how to integrate the Replane SDK with a FastAPI application
for feature flags and dynamic configuration using the async client.
"""

import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

from replane import AsyncReplane

# Configuration from environment variables
BASE_URL = os.environ.get("REPLANE_BASE_URL", "https://your-replane-server.com")
SDK_KEY = os.environ.get("REPLANE_SDK_KEY", "your_sdk_key_here")

# Global client instance
replane_client: AsyncReplane | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    global replane_client

    # Initialize and connect the Replane client
    replane_client = AsyncReplane(
        base_url=BASE_URL,
        sdk_key=SDK_KEY,
        defaults={
            "rate-limit": 100,
            "new-dashboard-enabled": False,
            "max-upload-size-mb": 10,
            "maintenance-mode": False,
        },
    )
    await replane_client.connect()

    yield

    # Cleanup on shutdown
    if replane_client:
        await replane_client.close()


app = FastAPI(
    title="Replane FastAPI Example",
    lifespan=lifespan,
)


# Dependency to get the Replane client
def get_replane() -> AsyncReplane:
    if replane_client is None:
        raise HTTPException(status_code=503, detail="Configuration service unavailable")
    return replane_client


# Dependency to build user context from request
def get_user_context(
    request: Request,
    x_user_id: Annotated[str | None, Header()] = None,
    x_user_plan: Annotated[str | None, Header()] = None,
) -> dict:
    return {
        "user_id": x_user_id or "anonymous",
        "plan": x_user_plan or "free",
        "ip_address": request.client.host if request.client else "unknown",
    }


# Response models
class WelcomeResponse(BaseModel):
    message: str
    version: str


class ItemsResponse(BaseModel):
    items: list[dict]
    rate_limit: int
    user_plan: str


class ConfigResponse(BaseModel):
    context: dict
    configs: dict


class UploadResponse(BaseModel):
    message: str
    allowed_size_mb: int


# Middleware to check maintenance mode
@app.middleware("http")
async def check_maintenance_mode(request: Request, call_next):
    if replane_client and request.url.path != "/health":
        maintenance = replane_client.get("maintenance-mode", default=False)
        if maintenance:
            return HTTPException(
                status_code=503,
                detail="Service is under maintenance. Please try again later.",
            )
    return await call_next(request)


@app.get("/", response_model=WelcomeResponse)
async def index(
    replane: Annotated[AsyncReplane, Depends(get_replane)],
    ctx: Annotated[dict, Depends(get_user_context)],
):
    """Homepage with feature flag check."""
    new_dashboard = replane.get("new-dashboard-enabled", context=ctx)

    if new_dashboard:
        return WelcomeResponse(message="Welcome to the new dashboard!", version="v2")
    else:
        return WelcomeResponse(message="Welcome!", version="v1")


@app.get("/api/items", response_model=ItemsResponse)
async def get_items(
    replane: Annotated[AsyncReplane, Depends(get_replane)],
    ctx: Annotated[dict, Depends(get_user_context)],
):
    """List items with configurable rate limiting."""
    rate_limit = replane.get("rate-limit", context=ctx)

    items = [
        {"id": 1, "name": "Item 1"},
        {"id": 2, "name": "Item 2"},
        {"id": 3, "name": "Item 3"},
    ]

    return ItemsResponse(
        items=items,
        rate_limit=rate_limit,
        user_plan=ctx["plan"],
    )


@app.post("/api/upload", response_model=UploadResponse)
async def upload(
    request: Request,
    replane: Annotated[AsyncReplane, Depends(get_replane)],
    ctx: Annotated[dict, Depends(get_user_context)],
):
    """Upload endpoint with configurable size limit."""
    max_size_mb = replane.get("max-upload-size-mb", context=ctx)

    content_length = request.headers.get("content-length", 0)
    max_bytes = max_size_mb * 1024 * 1024

    if int(content_length) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {max_size_mb}MB",
        )

    return UploadResponse(
        message="Upload successful",
        allowed_size_mb=max_size_mb,
    )


@app.get("/api/config", response_model=ConfigResponse)
async def get_config(
    replane: Annotated[AsyncReplane, Depends(get_replane)],
    ctx: Annotated[dict, Depends(get_user_context)],
):
    """Debug endpoint to view current config values."""
    return ConfigResponse(
        context=ctx,
        configs={
            "new-dashboard-enabled": replane.get("new-dashboard-enabled", context=ctx),
            "rate-limit": replane.get("rate-limit", context=ctx),
            "max-upload-size-mb": replane.get("max-upload-size-mb", context=ctx),
            "maintenance-mode": replane.get("maintenance-mode", context=ctx),
        },
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "replane_connected": replane_client is not None and replane_client.is_initialized(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
