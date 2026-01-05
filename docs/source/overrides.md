# Context and Overrides

Replane's override system allows you to return different config values based on runtime context. This enables powerful use cases like feature flags, A/B testing, and gradual rollouts.

## How Overrides Work

Each config in Replane has:
- A **base value** - the default returned when no overrides match
- **Override rules** - conditions that, when matched, return a different value

Override rules are evaluated in order. The first matching rule wins.

```
Config: "rate-limit"
├── Base value: 100
└── Overrides:
    ├── 1. If plan == "enterprise" → 10000
    ├── 2. If plan == "pro" → 1000
    └── 3. If region in ["us", "eu"] → 500
```

## Using Context

Use `with_context()` to evaluate overrides:

```python
# Without context - returns base value
rate_limit = replane.configs["rate-limit"]  # 100

# With context - evaluates overrides
pro_client = replane.with_context({"plan": "pro"})
rate_limit = pro_client.configs["rate-limit"]  # 1000

enterprise_client = replane.with_context({"plan": "enterprise"})
rate_limit = enterprise_client.configs["rate-limit"]  # 10000
```

## Context Properties

Context is a dictionary with string keys and primitive values:

```python
context = {
    # String values
    "user_id": "user-123",
    "plan": "premium",
    "region": "us-east",
    "country": "US",

    # Numeric values
    "age": 25,
    "purchase_count": 10,
    "account_age_days": 365,

    # Boolean values
    "is_admin": True,
    "is_beta_tester": False,
    "email_verified": True,

    # None is also valid (treated as "unknown")
    "referral_code": None,
}
```

## Default Context

Set a default context that applies to all config accesses:

```python
replane = Replane(
    ...,
    context={
        "environment": "production",
        "app_version": "2.1.0",
    },
)

# These accesses include the default context
replane.configs["feature"]  # context: {"environment": "production", "app_version": "2.1.0"}

# Additional context is merged with defaults using with_context()
user_client = replane.with_context({"user_id": "123"})
user_client.configs["feature"]
# Effective context: {"environment": "production", "app_version": "2.1.0", "user_id": "123"}
```

## Condition Types

Replane supports several condition types for overrides:

### Equals

Match when a property equals a specific value:

```python
# Override: plan equals "premium"
replane.with_context({"plan": "premium"}).configs["feature"]  # Matches
replane.with_context({"plan": "free"}).configs["feature"]     # Doesn't match
```

### In / Not In

Match when a property is (or isn't) in a list of values:

```python
# Override: plan in ["pro", "enterprise"]
replane.with_context({"plan": "pro"}).configs["feature"]        # Matches
replane.with_context({"plan": "enterprise"}).configs["feature"] # Matches
replane.with_context({"plan": "free"}).configs["feature"]       # Doesn't match
```

### Comparison (lt, lte, gt, gte)

Numeric comparisons:

```python
# Override: age >= 18
replane.with_context({"age": 21}).configs["adult-content"]  # Matches
replane.with_context({"age": 15}).configs["adult-content"]  # Doesn't match
```

### Segmentation (Percentage Rollout)

Roll out features to a percentage of users:

```python
# Override: 10% of users (based on user_id)
user_client = replane.with_context({"user_id": "user-123"})
user_client.configs["new-checkout"]
# Deterministic: same user always gets same result
```

Segmentation uses a hash function to deterministically bucket users. This ensures:
- The same user always sees the same variant
- Distribution is statistically uniform
- No server-side state is needed

### Logical Operators (AND, OR, NOT)

Combine conditions with logical operators:

```python
# Override: (plan == "pro" OR plan == "enterprise") AND region == "us"
replane.with_context({"plan": "pro", "region": "us"}).configs["feature"]      # Matches
replane.with_context({"plan": "pro", "region": "eu"}).configs["feature"]      # Doesn't match
replane.with_context({"plan": "free", "region": "us"}).configs["feature"]     # Doesn't match
```

## Client-Side Evaluation

All override evaluation happens locally in your application. The context you provide never leaves your servers.

This design provides:
- **Privacy** - User data stays in your application
- **Speed** - No network round-trip for config reads
- **Reliability** - Works even if connection is temporarily lost

## Common Patterns

### Feature Flags

```python
user_client = replane.with_context({"user_id": user.id})
if user_client.configs["new-dashboard-enabled"]:
    return render_new_dashboard()
else:
    return render_old_dashboard()
```

### Plan-Based Features

```python
plan_client = replane.with_context({"plan": user.plan})
max_projects = plan_client.configs["max-projects"]
# free: 3, pro: 10, enterprise: unlimited (-1)
```

### Gradual Rollout

Configure a 10% rollout in Replane dashboard, then:

```python
user_client = replane.with_context({"user_id": user.id})
use_new_algorithm = user_client.configs["new-recommendation-algorithm"]
```

### Geographic Targeting

```python
geo_client = replane.with_context({"country": request.geo.country})
banner_content = geo_client.configs["homepage-banner"]
```

### A/B Testing

```python
user_client = replane.with_context({"user_id": user.id})
button_color = user_client.configs["checkout-button-color"]
# Returns "blue", "green", or "red" based on user's bucket
```

## Missing Context Properties

When a condition references a property not in the context:

- The condition result is "unknown"
- For AND conditions: if any condition is unknown and none fail, the result is unknown
- For OR conditions: if any condition matches, it matches; otherwise unknown
- Unknown results typically mean the override doesn't match

```python
# Override requires "plan" property
replane.configs["feature"]  # Override won't match (no plan in default context)
replane.with_context({"plan": "pro"}).configs["feature"]  # Override can match
```

Best practice: ensure your context includes all properties that overrides might reference.
