"""Django views demonstrating Replane integration."""

from demo.replane_client import get_replane
from django.http import JsonResponse
from django.views import View


class IndexView(View):
    """Homepage with feature flag check."""

    def get(self, request):
        replane = get_replane()
        ctx = getattr(request, "replane_context", {})

        # Check if new dashboard is enabled for this user
        user_client = replane.with_context(ctx)
        new_dashboard = user_client.configs["new-dashboard-enabled"]

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
        replane = get_replane()
        ctx = getattr(request, "replane_context", {})

        # Get rate limit for this user
        user_client = replane.with_context(ctx)
        rate_limit = user_client.configs["rate-limit"]

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
        replane = get_replane()
        ctx = getattr(request, "replane_context", {})

        # Get the max upload size based on user's plan
        user_client = replane.with_context(ctx)
        max_size_mb = user_client.configs["max-upload-size-mb"]

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
        replane = get_replane()
        ctx = getattr(request, "replane_context", {})

        user_client = replane.with_context(ctx)
        return JsonResponse(
            {
                "context": ctx,
                "configs": {
                    "new-dashboard-enabled": user_client.configs["new-dashboard-enabled"],
                    "rate-limit": user_client.configs["rate-limit"],
                    "max-upload-size-mb": user_client.configs["max-upload-size-mb"],
                    "maintenance-mode": user_client.configs["maintenance-mode"],
                },
            }
        )


class HealthView(View):
    """Health check endpoint."""

    def get(self, request):
        try:
            replane = get_replane()
            replane_connected = replane.is_initialized()
        except RuntimeError:
            replane_connected = False

        return JsonResponse(
            {
                "status": "healthy",
                "replane_connected": replane_connected,
            }
        )
