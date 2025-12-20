"""Override evaluation logic for the Replane Python SDK.

This module handles client-side evaluation of config overrides based on context.
The context never leaves the application - all evaluation happens locally.
"""

from __future__ import annotations

from typing import Any, Literal

from .types import (
    AndCondition,
    Condition,
    Config,
    ContextValue,
    NotCondition,
    OrCondition,
    Override,
    PropertyCondition,
    SegmentationCondition,
)

# FNV-1a 32-bit constants
FNV_PRIME = 0x01000193
FNV_OFFSET_BASIS = 0x811C9DC5
FNV_MASK = 0xFFFFFFFF


def fnv1a_32(data: str) -> int:
    """Compute FNV-1a 32-bit hash of a string.

    This hash function is used for deterministic percentage-based bucketing
    in segmentation conditions. The same input always produces the same hash,
    ensuring users consistently see the same variant.

    Args:
        data: String to hash.

    Returns:
        32-bit unsigned integer hash value.
    """
    h = FNV_OFFSET_BASIS
    for byte in data.encode("utf-8"):
        h ^= byte
        h = (h * FNV_PRIME) & FNV_MASK
    return h


def hash_to_percentage(value: str, seed: str) -> float:
    """Convert a value to a percentage (0-100) using FNV-1a hash.

    Args:
        value: The value to hash (e.g., user ID).
        seed: Salt to ensure different configs get different distributions.

    Returns:
        A percentage between 0 and 100.
    """
    combined = f"{seed}:{value}"
    h = fnv1a_32(combined)
    return (h % 10000) / 100.0


ConditionResult = Literal["matched", "not_matched", "unknown"]


def _cast_to_type(value: Any, target_type: type) -> Any:
    """Attempt to cast a value to match a target type.

    This handles type coercion between context values and expected values
    in conditions, similar to how JS handles type comparisons.

    Args:
        value: Value to cast.
        target_type: Type to cast to.

    Returns:
        The cast value, or the original if casting fails.
    """
    if isinstance(value, target_type):
        return value

    try:
        if target_type is bool:
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes")
            return bool(value)
        elif target_type in (int, float):
            return target_type(value)
        elif target_type is str:
            return str(value)
    except (ValueError, TypeError):
        pass

    return value


def _compare_values(
    ctx_value: ContextValue,
    expected: Any,
    operator: str,
) -> ConditionResult:
    """Compare a context value against an expected value.

    Args:
        ctx_value: Value from the context.
        expected: Expected value from the condition.
        operator: Comparison operator.

    Returns:
        "matched", "not_matched", or "unknown" if comparison can't be made.
    """
    if ctx_value is None:
        return "unknown"

    # Try to cast expected to match context value's type
    target_type = type(ctx_value)
    casted = _cast_to_type(expected, target_type)

    if operator == "equals":
        return "matched" if ctx_value == casted else "not_matched"
    elif operator == "lt":
        try:
            return "matched" if ctx_value < casted else "not_matched"
        except TypeError:
            return "unknown"
    elif operator == "lte":
        try:
            return "matched" if ctx_value <= casted else "not_matched"
        except TypeError:
            return "unknown"
    elif operator == "gt":
        try:
            return "matched" if ctx_value > casted else "not_matched"
        except TypeError:
            return "unknown"
    elif operator == "gte":
        try:
            return "matched" if ctx_value >= casted else "not_matched"
        except TypeError:
            return "unknown"
    else:
        return "unknown"


def evaluate_condition(
    condition: Condition,
    context: dict[str, ContextValue],
) -> ConditionResult:
    """Evaluate a single condition against a context.

    Args:
        condition: The condition to evaluate.
        context: Runtime context with property values.

    Returns:
        "matched" if condition is satisfied,
        "not_matched" if condition is not satisfied,
        "unknown" if evaluation is indeterminate (missing property).
    """
    match condition:
        case AndCondition(conditions=conditions):
            # All conditions must match
            has_unknown = False
            for c in conditions:
                result = evaluate_condition(c, context)
                if result == "not_matched":
                    return "not_matched"
                if result == "unknown":
                    has_unknown = True
            return "unknown" if has_unknown else "matched"

        case OrCondition(conditions=conditions):
            # At least one condition must match
            has_unknown = False
            for c in conditions:
                result = evaluate_condition(c, context)
                if result == "matched":
                    return "matched"
                if result == "unknown":
                    has_unknown = True
            return "unknown" if has_unknown else "not_matched"

        case NotCondition(condition=inner):
            result = evaluate_condition(inner, context)
            if result == "matched":
                return "not_matched"
            elif result == "not_matched":
                return "matched"
            return "unknown"

        case SegmentationCondition(
            property=prop,
            from_percentage=from_pct,
            to_percentage=to_pct,
            seed=seed,
        ):
            ctx_value = context.get(prop)
            if ctx_value is None:
                return "unknown"

            # Convert to string for hashing
            str_value = str(ctx_value)
            percentage = hash_to_percentage(str_value, seed)

            if from_pct <= percentage < to_pct:
                return "matched"
            return "not_matched"

        case PropertyCondition(operator=op, property=prop, expected=expected):
            ctx_value = context.get(prop)

            if op == "in":
                if ctx_value is None:
                    return "unknown"
                if not isinstance(expected, (list, tuple)):
                    return "unknown"
                # Check if context value is in the expected list
                for item in expected:
                    casted = _cast_to_type(item, type(ctx_value))
                    if ctx_value == casted:
                        return "matched"
                return "not_matched"

            elif op == "not_in":
                if ctx_value is None:
                    return "unknown"
                if not isinstance(expected, (list, tuple)):
                    return "unknown"
                # Check if context value is NOT in the expected list
                for item in expected:
                    casted = _cast_to_type(item, type(ctx_value))
                    if ctx_value == casted:
                        return "not_matched"
                return "matched"

            else:
                return _compare_values(ctx_value, expected, op)

        case _:
            return "unknown"


def evaluate_override(
    override: Override,
    context: dict[str, ContextValue],
) -> bool:
    """Check if an override matches the given context.

    All conditions in the override must match for it to apply.

    Args:
        override: Override rule to evaluate.
        context: Runtime context with property values.

    Returns:
        True if all conditions match, False otherwise.
    """
    for condition in override.conditions:
        result = evaluate_condition(condition, context)
        if result != "matched":
            return False
    return True


def evaluate_config(
    config: Config,
    context: dict[str, ContextValue] | None = None,
) -> Any:
    """Evaluate a config and return the appropriate value.

    Overrides are evaluated in order. The first matching override's value
    is returned. If no overrides match, the base value is returned.

    Args:
        config: The config to evaluate.
        context: Optional runtime context for override evaluation.

    Returns:
        The config value (either from a matching override or the base value).

    Example:
        >>> config = Config(
        ...     name="feature-enabled",
        ...     value=False,
        ...     overrides=[
        ...         Override(
        ...             name="beta-users",
        ...             conditions=[PropertyCondition("equals", "plan", "beta")],
        ...             value=True,
        ...         )
        ...     ],
        ... )
        >>> evaluate_config(config, {"plan": "beta"})
        True
        >>> evaluate_config(config, {"plan": "free"})
        False
    """
    if context is None:
        context = {}

    for override in config.overrides:
        if evaluate_override(override, context):
            return override.value

    return config.value
