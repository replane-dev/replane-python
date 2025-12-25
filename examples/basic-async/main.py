"""Basic asynchronous Replane client example.

This example demonstrates how to use the AsyncReplane
for async/await applications.
"""

import asyncio

from replane import AsyncReplane

# Configuration - replace with your actual values
BASE_URL = "https://your-replane-server.com"
SDK_KEY = "your_sdk_key_here"


async def main():
    # Using async context manager (recommended)
    async with AsyncReplane(
        base_url=BASE_URL,
        sdk_key=SDK_KEY,
        # Optional: set default context for all evaluations
        context={"environment": "production"},
        # Optional: default values if server is unavailable
        defaults={
            "feature-enabled": False,
            "max-items": 10,
        },
        # Optional: enable debug logging
        debug=True,
    ) as client:
        # Read a boolean feature flag (sync - reads from local cache)
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

        # Keep running to receive real-time updates
        print("\nListening for config updates (Ctrl+C to stop)...")
        try:
            while True:
                await asyncio.sleep(5)
                # Re-read to see any updates
                current_value = client.get("feature-enabled")
                print(f"Current feature-enabled value: {current_value}")
        except KeyboardInterrupt:
            print("\nStopping...")


async def example_manual_lifecycle():
    """Example showing manual connect/close lifecycle."""
    client = AsyncReplane(
        base_url=BASE_URL,
        sdk_key=SDK_KEY,
    )

    try:
        # Connect and wait for initial configs
        await client.connect(wait=True)

        # Now you can read configs
        value = client.get("my-config")
        print(f"Config value: {value}")

    finally:
        # Always close the client when done
        await client.close()


async def example_with_subscriptions():
    """Example showing how to subscribe to config changes."""
    async with AsyncReplane(
        base_url=BASE_URL,
        sdk_key=SDK_KEY,
    ) as client:
        # Subscribe to all config changes
        def on_any_change(name, config):
            print(f"Config '{name}' changed to: {config.value}")

        unsubscribe_all = client.subscribe(on_any_change)

        # Subscribe to a specific config
        def on_feature_change(config):
            print(f"Feature flag updated: {config.value}")

        unsubscribe_feature = client.subscribe_config("feature-enabled", on_feature_change)

        # Keep running to receive updates
        print("Listening for changes...")
        await asyncio.sleep(60)

        # Unsubscribe when done
        unsubscribe_all()
        unsubscribe_feature()


async def example_async_callback():
    """Example showing async callbacks for config changes."""
    async with AsyncReplane(
        base_url=BASE_URL,
        sdk_key=SDK_KEY,
    ) as client:
        # Async callbacks are supported
        async def on_change(name, config):
            print(f"Config '{name}' changed")
            # Can do async operations here
            await asyncio.sleep(0.1)
            print(f"Processed change for '{name}'")

        client.subscribe(on_change)

        await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
