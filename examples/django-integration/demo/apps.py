"""Django app configuration with Replane initialization."""

import atexit

from django.apps import AppConfig
from django.conf import settings


class DemoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "demo"

    def ready(self):
        """Initialize Replane client when Django starts."""
        # Avoid double initialization in development with auto-reload
        import sys

        if "runserver" in sys.argv and "--noreload" not in sys.argv:
            # Only initialize in the reloader process, not the main process
            import os

            if os.environ.get("RUN_MAIN") != "true":
                return

        from demo.replane_client import init_replane, shutdown_replane

        # Initialize the Replane client
        init_replane(
            base_url=settings.REPLANE_BASE_URL,
            sdk_key=settings.REPLANE_SDK_KEY,
            defaults=getattr(settings, "REPLANE_DEFAULTS", {}),
        )

        # Register cleanup on shutdown
        atexit.register(shutdown_replane)
