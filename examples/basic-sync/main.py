"""Basic synchronous Replane client example.

This example demonstrates how to use the SyncReplaneClient
to read feature flags and configuration values.
"""

from replane import SyncReplaneClient

# Configuration - replace with your actual values
BASE_URL = "https://your-replane-server.com"
SDK_KEY = "sk_your_sdk_key_here"


def main():
    # Using context manager (recommended)
    with SyncReplaneClient(
        base_url=BASE_URL,
        sdk_key=SDK_KEY,
        # Optional: set default context for all evaluations
        context={"environment": "production"},
        # Optional: fallback values if server is unavailable
        fallbacks={
            "feature-enabled": False,
            "max-items": 10,
        },
        # Optional: enable debug logging
        debug=True,
    ) as client:
        # Read a boolean feature flag
        is_feature_enabled = client.get("feature-enabled")
        print(f"Feature enabled: {is_feature_enabled}")

        # Read a numeric config
        max_items = client.get("max-items")
        print(f"Max items: {max_items}")

        # Read with context for override evaluation
        rate_limit = client.get(
            "rate-limit",
            context={"plan": "premium", "user_id": "user-123"},
        )
        print(f"Rate limit: {rate_limit}")

        # Read with default value if config doesn't exist
        timeout = client.get("request-timeout", default=30)
        print(f"Timeout: {timeout}")


def example_manual_lifecycle():
    """Example showing manual connect/close lifecycle."""
    client = SyncReplaneClient(
        base_url=BASE_URL,
        sdk_key=SDK_KEY,
    )

    try:
        # Connect and wait for initial configs
        client.connect(wait=True)

        # Now you can read configs
        value = client.get("my-config")
        print(f"Config value: {value}")

    finally:
        # Always close the client when done
        client.close()


def example_non_blocking_connect():
    """Example showing non-blocking connection."""
    client = SyncReplaneClient(
        base_url=BASE_URL,
        sdk_key=SDK_KEY,
        fallbacks={"my-config": "default-value"},
    )

    # Start connection without waiting
    client.connect(wait=False)

    # Can use fallback values immediately
    value = client.get("my-config")
    print(f"Initial value (may be fallback): {value}")

    # Later, wait for initialization if needed
    client.wait_for_init()

    # Now we have fresh values from server
    value = client.get("my-config")
    print(f"Server value: {value}")

    client.close()


if __name__ == "__main__":
    main()
