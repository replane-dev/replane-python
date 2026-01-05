"""Sample application code to be tested.

This module contains example functions that use Replane for configuration.
"""


def get_rate_limit(replane, user_plan: str) -> int:
    """Get rate limit based on user's plan."""
    user_client = replane.with_context({"plan": user_plan})
    return user_client.configs["rate-limit"]


def is_feature_enabled(replane, feature_name: str, user_id: str | None = None) -> bool:
    """Check if a feature is enabled for a user."""
    if user_id:
        user_client = replane.with_context({"user_id": user_id})
        return user_client.configs.get(feature_name, False)
    return replane.configs.get(feature_name, False)


def calculate_discount(replane, user_id: str, is_premium: bool) -> float:
    """Calculate discount percentage for a user."""
    base_discount = replane.configs.get("base-discount", 0)
    premium_bonus = replane.configs.get("premium-bonus", 0) if is_premium else 0
    return base_discount + premium_bonus


class OrderService:
    """Example service class that uses Replane."""

    def __init__(self, replane):
        self.replane = replane

    def get_max_items_per_order(self, user_plan: str) -> int:
        """Get maximum items allowed per order."""
        plan_client = self.replane.with_context({"plan": user_plan})
        return plan_client.configs.get("max-items-per-order", 10)

    def is_express_shipping_available(self, region: str) -> bool:
        """Check if express shipping is available in a region."""
        region_client = self.replane.with_context({"region": region})
        return region_client.configs.get("express-shipping-enabled", False)
