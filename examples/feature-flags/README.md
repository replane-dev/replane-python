# Feature Flags Example

This example demonstrates various feature flag and remote configuration patterns with the Replane SDK.

## Prerequisites

- Python 3.10 or higher
- A running Replane server
- An SDK key from your Replane dashboard

## Setup

1. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Update configuration in `main.py`:

```python
BASE_URL = "https://your-replane-server.com"
SDK_KEY = "your_sdk_key_here"
```

## Run

```bash
python main.py
```

## Use Cases Demonstrated

### 1. Basic Feature Flags

Simple on/off toggles for features:

```python
dark_mode = client.get("dark-mode-enabled", default=False)
if dark_mode:
    enable_dark_theme()
```

### 2. User Targeting

Enable features for specific users (beta testers, VIPs):

```python
beta_enabled = client.get(
    "beta-feature",
    context={"user_id": current_user.id},
    default=False,
)
```

### 3. Plan-Based Limits

Different limits based on subscription plan:

```python
rate_limit = client.get(
    "api-rate-limit",
    context={"plan": user.plan},
    default=100,
)
```

### 4. Regional Features

Enable/disable features by geographic region:

```python
apple_pay = client.get(
    "apple-pay-enabled",
    context={"region": user.region},
    default=False,
)
```

### 5. Gradual Rollout

Roll out features to a percentage of users:

```python
# Percentage configured server-side using segmentation
new_feature = client.get(
    "experimental-feature",
    context={"user_id": user.id},
    default=False,
)
```

### 6. Environment-Specific Configs

Different settings for dev/staging/production:

```python
log_level = client.get(
    "log-level",
    context={"environment": os.environ.get("ENV", "development")},
    default="INFO",
)
```

### 7. Complex Conditions

Multiple conditions combined (AND/OR logic):

```python
# VIP discount requires premium plan AND high LTV
discount = client.get(
    "vip-discount-percent",
    context={
        "plan": user.plan,
        "ltv": user.lifetime_value,
        "region": user.region,
    },
    default=0,
)
```

### 8. Real-Time Updates

Subscribe to config changes:

```python
def on_change(name, config):
    print(f"Config '{name}' changed to: {config.value}")

unsubscribe = client.subscribe(on_change)
```

## Server-Side Configuration

For these examples to work fully, configure the following in your Replane dashboard:

### Example: `api-rate-limit` with plan-based overrides

```json
{
  "name": "api-rate-limit",
  "value": 100,
  "overrides": [
    {
      "name": "starter-plan",
      "conditions": [
        { "operator": "equals", "property": "plan", "expected": "starter" }
      ],
      "value": 500
    },
    {
      "name": "pro-plan",
      "conditions": [
        { "operator": "equals", "property": "plan", "expected": "pro" }
      ],
      "value": 2000
    },
    {
      "name": "enterprise-plan",
      "conditions": [
        { "operator": "equals", "property": "plan", "expected": "enterprise" }
      ],
      "value": 10000
    }
  ]
}
```

### Example: `beta-feature` with user targeting

```json
{
  "name": "beta-feature",
  "value": false,
  "overrides": [
    {
      "name": "beta-users",
      "conditions": [
        {
          "operator": "in",
          "property": "user_id",
          "expected": ["user-1", "user-2", "user-3"]
        }
      ],
      "value": true
    }
  ]
}
```

### Example: Gradual rollout with segmentation

```json
{
  "name": "experimental-feature",
  "value": false,
  "overrides": [
    {
      "name": "10-percent-rollout",
      "conditions": [
        {
          "operator": "segmentation",
          "property": "user_id",
          "fromPercentage": 0,
          "toPercentage": 10,
          "seed": "experimental-feature-rollout"
        }
      ],
      "value": true
    }
  ]
}
```

## Best Practices

1. **Always provide fallbacks**: Use the `fallbacks` parameter or `default` in `get()` calls
2. **Use meaningful config names**: `api-rate-limit` not `limit1`
3. **Document your context properties**: Keep a list of what context values your app uses
4. **Test with InMemoryReplaneClient**: See the `testing` example for how to test
5. **Monitor config changes**: Use subscriptions for logging or analytics
