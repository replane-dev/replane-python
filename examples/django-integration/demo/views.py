"""Django views demonstrating Replane integration."""

from demo.replane_client import get_replane
from django.http import JsonResponse
from django.views import View


class IndexView(View):
    """Homepage with feature flag check."""

    def get(self, request):
        client = get_replane()
        ctx = getattr(request, "replane_context", {})

        # Check if new dashboard is enabled for this user
        new_dashboard = client.get("new-dashboard-enabled", context=ctx)

        if new_dashboard:
            return JsonResponse(
                {
                    "message": "Welcome to the new dashboard!",
                    "version": "v2",
                }
            )
        else:
            return JsonResponse(
                {
                    "message": "Welcome!",
                    "version": "v1",
                }
            )


class ItemsView(View):
    """List items with configurable rate limiting."""

    def get(self, request):
        client = get_replane()
        ctx = getattr(request, "replane_context", {})

        # Get rate limit for this user
        rate_limit = client.get("rate-limit", context=ctx)

        items = [
            {"id": 1, "name": "Item 1"},
            {"id": 2, "name": "Item 2"},
            {"id": 3, "name": "Item 3"},
        ]

        return JsonResponse(
            {
                "items": items,
                "rate_limit": rate_limit,
                "user_plan": ctx.get("plan", "unknown"),
            }
        )


class UploadView(View):
    """Upload endpoint with configurable size limit."""

    def post(self, request):
        client = get_replane()
        ctx = getattr(request, "replane_context", {})

        # Get the max upload size based on user's plan
        max_size_mb = client.get("max-upload-size-mb", context=ctx)

        content_length = int(request.headers.get("Content-Length", 0))
        max_bytes = max_size_mb * 1024 * 1024

        if content_length > max_bytes:
            return JsonResponse(
                {
                    "error": "File too large",
                    "max_size_mb": max_size_mb,
                },
                status=413,
            )

        return JsonResponse(
            {
                "message": "Upload successful",
                "allowed_size_mb": max_size_mb,
            }
        )


class ConfigView(View):
    """Debug endpoint to view current config values."""

    def get(self, request):
        client = get_replane()
        ctx = getattr(request, "replane_context", {})

        return JsonResponse(
            {
                "context": ctx,
                "configs": {
                    "new-dashboard-enabled": client.get("new-dashboard-enabled", context=ctx),
                    "rate-limit": client.get("rate-limit", context=ctx),
                    "max-upload-size-mb": client.get("max-upload-size-mb", context=ctx),
                    "maintenance-mode": client.get("maintenance-mode", context=ctx),
                },
            }
        )


class HealthView(View):
    """Health check endpoint."""

    def get(self, request):
        try:
            client = get_replane()
            replane_connected = client.is_initialized()
        except RuntimeError:
            replane_connected = False

        return JsonResponse(
            {
                "status": "healthy",
                "replane_connected": replane_connected,
            }
        )
