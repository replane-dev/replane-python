"""Type definitions for the Replane Python SDK.

This module contains all the data models used by the SDK, implemented using
dataclasses and TypedDict for zero external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict


# Context type - what users pass to evaluate overrides
class Context(TypedDict, total=False):
    """Runtime context for override evaluation.

    Context is a dictionary of string keys to primitive values.
    Common properties include user IDs, subscription plans, regions, etc.

    Example::

        context: Context = {
            "user_id": "user-123",
            "plan": "premium",
            "region": "us-east",
            "is_beta": True,
        }
    """

    pass  # All keys are optional, any str key maps to ContextValue


# Type alias for context values
ContextValue = str | int | float | bool | None


# Condition types for override evaluation
@dataclass(frozen=True, slots=True)
class PropertyCondition:
    """A condition that compares a context property against expected values."""

    operator: Literal["equals", "in", "not_in", "lt", "lte", "gt", "gte"]
    property: str
    expected: Any


@dataclass(frozen=True, slots=True)
class SegmentationCondition:
    """A condition for percentage-based bucketing (gradual rollouts)."""

    operator: Literal["segmentation"]
    property: str
    from_percentage: float
    to_percentage: float
    seed: str


@dataclass(frozen=True, slots=True)
class AndCondition:
    """Logical AND of multiple conditions."""

    operator: Literal["and"]
    conditions: tuple[Condition, ...]


@dataclass(frozen=True, slots=True)
class OrCondition:
    """Logical OR of multiple conditions."""

    operator: Literal["or"]
    conditions: tuple[Condition, ...]


@dataclass(frozen=True, slots=True)
class NotCondition:
    """Logical NOT of a condition."""

    operator: Literal["not"]
    condition: Condition


# Union type for all conditions
Condition = PropertyCondition | SegmentationCondition | AndCondition | OrCondition | NotCondition


@dataclass(frozen=True, slots=True)
class Override:
    """An override rule that returns a specific value when conditions match."""

    name: str
    conditions: tuple[Condition, ...]
    value: Any


@dataclass(slots=True)
class Config:
    """A configuration with its base value and override rules.

    Attributes:
        name: Unique identifier for this config.
        value: The base/default value returned when no overrides match.
        overrides: List of override rules evaluated in order.
    """

    name: str
    value: Any
    overrides: tuple[Override, ...] = field(default_factory=tuple)


# Type for config change callbacks
ConfigChangeCallback = Any  # Will be properly typed in client module


def parse_condition(data: dict[str, Any]) -> Condition:
    """Parse a condition from API response data.

    Args:
        data: Raw condition data from the API.

    Returns:
        A typed Condition object.

    Raises:
        ValueError: If the condition operator is unknown.
    """
    operator = data.get("operator")

    if operator == "and":
        return AndCondition(
            operator="and",
            conditions=tuple(parse_condition(c) for c in data["conditions"]),
        )
    elif operator == "or":
        return OrCondition(
            operator="or",
            conditions=tuple(parse_condition(c) for c in data["conditions"]),
        )
    elif operator == "not":
        return NotCondition(
            operator="not",
            condition=parse_condition(data["condition"]),
        )
    elif operator == "segmentation":
        return SegmentationCondition(
            operator="segmentation",
            property=data["property"],
            from_percentage=data["fromPercentage"],
            to_percentage=data["toPercentage"],
            seed=data["seed"],
        )
    elif operator in ("equals", "in", "not_in"):
        return PropertyCondition(
            operator=operator,
            property=data["property"],
            expected=data.get("expected", data.get("value")),
        )
    elif operator == "less_than":
        return PropertyCondition(
            operator="lt",
            property=data["property"],
            expected=data.get("expected", data.get("value")),
        )
    elif operator == "less_than_or_equal":
        return PropertyCondition(
            operator="lte",
            property=data["property"],
            expected=data.get("expected", data.get("value")),
        )
    elif operator == "greater_than":
        return PropertyCondition(
            operator="gt",
            property=data["property"],
            expected=data.get("expected", data.get("value")),
        )
    elif operator == "greater_than_or_equal":
        return PropertyCondition(
            operator="gte",
            property=data["property"],
            expected=data.get("expected", data.get("value")),
        )
    else:
        raise ValueError(f"Unknown condition operator: {operator}")


def parse_override(data: dict[str, Any]) -> Override:
    """Parse an override from API response data."""
    return Override(
        name=data["name"],
        conditions=tuple(parse_condition(c) for c in data["conditions"]),
        value=data["value"],
    )


def parse_config(data: dict[str, Any]) -> Config:
    """Parse a config from API response data."""
    return Config(
        name=data["name"],
        value=data["value"],
        overrides=tuple(parse_override(o) for o in data.get("overrides", [])),
    )
