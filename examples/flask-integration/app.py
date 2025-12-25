"""Flask integration example with Replane.

This example shows how to integrate the Replane SDK with a Flask application
for feature flags and dynamic configuration.
"""

import atexit
import os

from flask import Flask, jsonify, request

from replane import Replane

app = Flask(__name__)

# Configuration from environment variables
BASE_URL = os.environ.get("REPLANE_BASE_URL", "https://your-replane-server.com")
SDK_KEY = os.environ.get("REPLANE_SDK_KEY", "your_sdk_key_here")

# Initialize the Replane client at application startup
replane_client = Replane(
    base_url=BASE_URL,
    sdk_key=SDK_KEY,
    defaults={
        "rate-limit": 100,
        "new-dashboard-enabled": False,
        "max-upload-size-mb": 10,
    },
)

# Connect to Replane server
replane_client.connect()


# Ensure client is closed on shutdown
@atexit.register
def cleanup():
    replane_client.close()


def get_user_context():
    """Build context from the current request."""
    # In a real app, you'd get this from authentication
    user_id = request.headers.get("X-User-ID", "anonymous")
    plan = request.headers.get("X-User-Plan", "free")

    return {
        "user_id": user_id,
        "plan": plan,
        "ip_address": request.remote_addr,
    }


@app.route("/")
def index():
    """Homepage with feature flag check."""
    ctx = get_user_context()

    # Check if new dashboard is enabled for this user
    new_dashboard = replane_client.get("new-dashboard-enabled", context=ctx)

    if new_dashboard:
        return jsonify({"message": "Welcome to the new dashboard!", "version": "v2"})
    else:
        return jsonify({"message": "Welcome!", "version": "v1"})


@app.route("/api/upload", methods=["POST"])
def upload():
    """Upload endpoint with configurable size limit."""
    ctx = get_user_context()

    # Get the max upload size based on user's plan
    max_size_mb = replane_client.get("max-upload-size-mb", context=ctx)

    # Check content length
    content_length = request.content_length or 0
    max_bytes = max_size_mb * 1024 * 1024

    if content_length > max_bytes:
        return (
            jsonify(
                {
                    "error": "File too large",
                    "max_size_mb": max_size_mb,
                }
            ),
            413,
        )

    return jsonify(
        {
            "message": "Upload successful",
            "allowed_size_mb": max_size_mb,
        }
    )


@app.route("/api/items")
def get_items():
    """List items with configurable rate limiting."""
    ctx = get_user_context()

    # Get rate limit for this user
    rate_limit = replane_client.get("rate-limit", context=ctx)

    # In a real app, you'd implement actual rate limiting here
    # This just shows the configured limit

    items = [
        {"id": 1, "name": "Item 1"},
        {"id": 2, "name": "Item 2"},
        {"id": 3, "name": "Item 3"},
    ]

    return jsonify(
        {
            "items": items,
            "rate_limit": rate_limit,
            "user_plan": ctx["plan"],
        }
    )


@app.route("/api/config")
def get_config():
    """Debug endpoint to view current config values."""
    ctx = get_user_context()

    return jsonify(
        {
            "context": ctx,
            "configs": {
                "new-dashboard-enabled": replane_client.get("new-dashboard-enabled", context=ctx),
                "rate-limit": replane_client.get("rate-limit", context=ctx),
                "max-upload-size-mb": replane_client.get("max-upload-size-mb", context=ctx),
            },
        }
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
