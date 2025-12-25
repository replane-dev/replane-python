"""Feature flags and remote configuration examples.

This example demonstrates various use cases for feature flags and
dynamic configuration with the Replane SDK.
"""

from replane import Replane

# Configuration - replace with your actual values
BASE_URL = "https://your-replane-server.com"
SDK_KEY = "your_sdk_key_here"


def demo_basic_feature_flags(client: Replane):
    """Basic boolean feature flags."""
    print("\n=== Basic Feature Flags ===")

    # Simple boolean flag
    dark_mode = client.get("dark-mode-enabled", default=False)
    print(f"Dark mode: {dark_mode}")

    # Feature flag for new UI
    new_checkout = client.get("new-checkout-flow", default=False)
    if new_checkout:
        print("Using new checkout flow")
    else:
        print("Using legacy checkout flow")


def demo_user_targeting(client: Replane):
    """Feature flags with user targeting."""
    print("\n=== User Targeting ===")

    # Different users get different experiences
    users = [
        {"user_id": "user-1", "name": "Alice"},
        {"user_id": "user-2", "name": "Bob"},
        {"user_id": "user-100", "name": "Charlie"},
    ]

    for user in users:
        # Beta feature for specific users
        beta_enabled = client.get(
            "beta-feature",
            context={"user_id": user["user_id"]},
            default=False,
        )
        print(f"{user['name']}: beta feature = {beta_enabled}")


def demo_plan_based_limits(client: Replane):
    """Dynamic limits based on subscription plan."""
    print("\n=== Plan-Based Limits ===")

    plans = ["free", "starter", "pro", "enterprise"]

    for plan in plans:
        # Rate limits vary by plan
        rate_limit = client.get(
            "api-rate-limit",
            context={"plan": plan},
            default=100,
        )

        # Storage limits vary by plan
        storage_gb = client.get(
            "storage-limit-gb",
            context={"plan": plan},
            default=5,
        )

        # Max team members vary by plan
        max_members = client.get(
            "max-team-members",
            context={"plan": plan},
            default=1,
        )

        print(
            f"{plan:12} | Rate: {rate_limit:5}/hr | Storage: {storage_gb:4}GB | Members: {max_members}"
        )


def demo_regional_features(client: Replane):
    """Features enabled for specific regions."""
    print("\n=== Regional Features ===")

    regions = ["US", "EU", "APAC", "LATAM"]

    for region in regions:
        # Payment methods available in region
        apple_pay = client.get(
            "apple-pay-enabled",
            context={"region": region},
            default=False,
        )

        crypto = client.get(
            "crypto-payments-enabled",
            context={"region": region},
            default=False,
        )

        print(f"{region}: Apple Pay = {apple_pay}, Crypto = {crypto}")


def demo_gradual_rollout(client: Replane):
    """Gradual feature rollout (percentage-based)."""
    print("\n=== Gradual Rollout ===")

    # Simulate checking feature for multiple users
    # The actual percentage rollout is configured server-side
    # using segmentation conditions

    users = [f"user-{i}" for i in range(1, 11)]

    enabled_count = 0
    for user_id in users:
        enabled = client.get(
            "experimental-feature",
            context={"user_id": user_id},
            default=False,
        )
        if enabled:
            enabled_count += 1
        print(f"{user_id}: {enabled}")

    print(f"\nEnabled for {enabled_count}/{len(users)} users ({enabled_count * 10}%)")


def demo_environment_configs(client: Replane):
    """Environment-specific configuration."""
    print("\n=== Environment Configs ===")

    environments = ["development", "staging", "production"]

    for env in environments:
        # Log level varies by environment
        log_level = client.get(
            "log-level",
            context={"environment": env},
            default="INFO",
        )

        # Debug mode
        debug = client.get(
            "debug-mode",
            context={"environment": env},
            default=False,
        )

        # Cache TTL
        cache_ttl = client.get(
            "cache-ttl-seconds",
            context={"environment": env},
            default=300,
        )

        print(f"{env:12} | Log: {log_level:5} | Debug: {debug} | Cache TTL: {cache_ttl}s")


def demo_complex_conditions(client: Replane):
    """Features with multiple conditions."""
    print("\n=== Complex Conditions ===")

    # VIP discount requires both premium plan AND high lifetime value
    test_cases = [
        {"plan": "free", "ltv": 0, "region": "US"},
        {"plan": "premium", "ltv": 500, "region": "US"},
        {"plan": "premium", "ltv": 5000, "region": "US"},
        {"plan": "enterprise", "ltv": 10000, "region": "EU"},
    ]

    for ctx in test_cases:
        discount = client.get(
            "vip-discount-percent",
            context=ctx,
            default=0,
        )
        print(
            f"Plan: {ctx['plan']:10} LTV: ${ctx['ltv']:5} Region: {ctx['region']} -> {discount}% discount"
        )


def demo_real_time_updates(client: Replane):
    """Subscribe to real-time config changes."""
    print("\n=== Real-Time Updates ===")

    def on_config_change(name, config):
        print(f"Config '{name}' changed to: {config.value}")

    # Subscribe to all changes
    unsubscribe = client.subscribe(on_config_change)

    print("Subscribed to config changes.")
    print("Change configs in Replane dashboard to see updates.")
    print("Press Ctrl+C to stop.\n")

    import time

    try:
        while True:
            # Periodically show current values
            time.sleep(10)
            print(f"Current 'feature-flag' value: {client.get('feature-flag', default='N/A')}")
    except KeyboardInterrupt:
        print("\nUnsubscribing...")
        unsubscribe()


def main():
    with Replane(
        base_url=BASE_URL,
        sdk_key=SDK_KEY,
        # Default values ensure the app works even if server is unreachable
        defaults={
            "dark-mode-enabled": False,
            "new-checkout-flow": False,
            "beta-feature": False,
            "api-rate-limit": 100,
            "storage-limit-gb": 5,
            "max-team-members": 1,
            "apple-pay-enabled": False,
            "crypto-payments-enabled": False,
            "experimental-feature": False,
            "log-level": "INFO",
            "debug-mode": False,
            "cache-ttl-seconds": 300,
            "vip-discount-percent": 0,
        },
        debug=False,
    ) as client:
        demo_basic_feature_flags(client)
        demo_user_targeting(client)
        demo_plan_based_limits(client)
        demo_regional_features(client)
        demo_gradual_rollout(client)
        demo_environment_configs(client)
        demo_complex_conditions(client)

        # Uncomment to test real-time updates:
        # demo_real_time_updates(client)


if __name__ == "__main__":
    main()
