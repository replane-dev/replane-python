"""Django middleware for Replane integration."""

from demo.replane_client import get_replane
from django.http import JsonResponse


class ReplaneMiddleware:
    """Middleware that checks maintenance mode and adds Replane context to requests."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip maintenance check for health endpoint
        if request.path == "/health/":
            return self.get_response(request)

        # Check maintenance mode
        try:
            client = get_replane()
            if client.get("maintenance-mode", default=False):
                return JsonResponse(
                    {
                        "error": "Service is under maintenance",
                        "message": "Please try again later.",
                    },
                    status=503,
                )
        except RuntimeError:
            # Client not initialized, continue without check
            pass

        # Add user context to request for use in views
        request.replane_context = self._build_context(request)

        return self.get_response(request)

    def _build_context(self, request) -> dict:
        """Build Replane context from the request."""
        return {
            "user_id": request.headers.get("X-User-ID", "anonymous"),
            "plan": request.headers.get("X-User-Plan", "free"),
            "ip_address": self._get_client_ip(request),
        }

    def _get_client_ip(self, request) -> str:
        """Get client IP address from request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")
