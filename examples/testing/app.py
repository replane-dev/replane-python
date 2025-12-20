"""Sample application code to be tested.

This module contains example functions that use Replane for configuration.
"""


def get_rate_limit(client, user_plan: str) -> int:
    """Get rate limit based on user's plan."""
    return client.get("rate-limit", context={"plan": user_plan})


def is_feature_enabled(client, feature_name: str, user_id: str | None = None) -> bool:
    """Check if a feature is enabled for a user."""
    context = {"user_id": user_id} if user_id else {}
    return client.get(feature_name, context=context, default=False)


def calculate_discount(client, user_id: str, is_premium: bool) -> float:
    """Calculate discount percentage for a user."""
    base_discount = client.get("base-discount", default=0)
    premium_bonus = client.get("premium-bonus", default=0) if is_premium else 0
    return base_discount + premium_bonus


class OrderService:
    """Example service class that uses Replane."""

    def __init__(self, replane_client):
        self.client = replane_client

    def get_max_items_per_order(self, user_plan: str) -> int:
        """Get maximum items allowed per order."""
        return self.client.get(
            "max-items-per-order",
            context={"plan": user_plan},
            default=10,
        )

    def is_express_shipping_available(self, region: str) -> bool:
        """Check if express shipping is available in a region."""
        return self.client.get(
            "express-shipping-enabled",
            context={"region": region},
            default=False,
        )
