"""Tests for type definitions and parsing."""

import pytest

from replane.types import (
    AndCondition,
    Config,
    NotCondition,
    OrCondition,
    Override,
    PropertyCondition,
    SegmentationCondition,
    parse_condition,
    parse_config,
    parse_override,
)


class TestParseCondition:
    """Tests for condition parsing from API data."""

    def test_parse_equals(self):
        data = {"operator": "equals", "property": "plan", "expected": "pro"}
        cond = parse_condition(data)
        assert isinstance(cond, PropertyCondition)
        assert cond.operator == "equals"
        assert cond.property == "plan"
        assert cond.expected == "pro"

    def test_parse_in(self):
        data = {"operator": "in", "property": "region", "expected": ["us", "eu"]}
        cond = parse_condition(data)
        assert isinstance(cond, PropertyCondition)
        assert cond.operator == "in"
        assert cond.expected == ["us", "eu"]

    def test_parse_not_in(self):
        data = {"operator": "not_in", "property": "plan", "expected": ["trial"]}
        cond = parse_condition(data)
        assert isinstance(cond, PropertyCondition)
        assert cond.operator == "not_in"

    def test_parse_less_than(self):
        data = {"operator": "less_than", "property": "age", "expected": 18}
        cond = parse_condition(data)
        assert isinstance(cond, PropertyCondition)
        assert cond.operator == "lt"
        assert cond.expected == 18

    def test_parse_less_than_or_equal(self):
        data = {"operator": "less_than_or_equal", "property": "count", "expected": 5}
        cond = parse_condition(data)
        assert cond.operator == "lte"

    def test_parse_greater_than(self):
        data = {"operator": "greater_than", "property": "score", "expected": 100}
        cond = parse_condition(data)
        assert cond.operator == "gt"

    def test_parse_greater_than_or_equal(self):
        data = {"operator": "greater_than_or_equal", "property": "level", "expected": 5}
        cond = parse_condition(data)
        assert cond.operator == "gte"

    def test_parse_segmentation(self):
        data = {
            "operator": "segmentation",
            "property": "user_id",
            "fromPercentage": 0,
            "toPercentage": 50,
            "seed": "feature-x",
        }
        cond = parse_condition(data)
        assert isinstance(cond, SegmentationCondition)
        assert cond.operator == "segmentation"
        assert cond.property == "user_id"
        assert cond.from_percentage == 0
        assert cond.to_percentage == 50
        assert cond.seed == "feature-x"

    def test_parse_and(self):
        data = {
            "operator": "and",
            "conditions": [
                {"operator": "equals", "property": "a", "expected": 1},
                {"operator": "equals", "property": "b", "expected": 2},
            ],
        }
        cond = parse_condition(data)
        assert isinstance(cond, AndCondition)
        assert len(cond.conditions) == 2
        assert all(isinstance(c, PropertyCondition) for c in cond.conditions)

    def test_parse_or(self):
        data = {
            "operator": "or",
            "conditions": [
                {"operator": "equals", "property": "x", "expected": 1},
                {"operator": "equals", "property": "x", "expected": 2},
            ],
        }
        cond = parse_condition(data)
        assert isinstance(cond, OrCondition)
        assert len(cond.conditions) == 2

    def test_parse_not(self):
        data = {
            "operator": "not",
            "condition": {"operator": "equals", "property": "blocked", "expected": True},
        }
        cond = parse_condition(data)
        assert isinstance(cond, NotCondition)
        assert isinstance(cond.condition, PropertyCondition)

    def test_parse_nested_conditions(self):
        data = {
            "operator": "and",
            "conditions": [
                {
                    "operator": "or",
                    "conditions": [
                        {"operator": "equals", "property": "plan", "expected": "pro"},
                        {"operator": "equals", "property": "plan", "expected": "enterprise"},
                    ],
                },
                {"operator": "equals", "property": "region", "expected": "us"},
            ],
        }
        cond = parse_condition(data)
        assert isinstance(cond, AndCondition)
        assert isinstance(cond.conditions[0], OrCondition)

    def test_parse_unknown_operator_raises(self):
        data = {"operator": "unknown", "property": "x", "expected": 1}
        with pytest.raises(ValueError, match="Unknown condition operator"):
            parse_condition(data)


class TestParseOverride:
    """Tests for override parsing."""

    def test_parse_override(self):
        data = {
            "name": "premium-users",
            "conditions": [{"operator": "equals", "property": "plan", "expected": "premium"}],
            "value": True,
        }
        override = parse_override(data)
        assert isinstance(override, Override)
        assert override.name == "premium-users"
        assert len(override.conditions) == 1
        assert override.value is True

    def test_parse_override_empty_conditions(self):
        data = {"name": "default", "conditions": [], "value": "always"}
        override = parse_override(data)
        assert len(override.conditions) == 0


class TestParseConfig:
    """Tests for config parsing."""

    def test_parse_config_simple(self):
        data = {"name": "feature-flag", "value": True}
        config = parse_config(data)
        assert isinstance(config, Config)
        assert config.name == "feature-flag"
        assert config.value is True
        assert len(config.overrides) == 0

    def test_parse_config_with_overrides(self):
        data = {
            "name": "rate-limit",
            "value": 100,
            "overrides": [
                {
                    "name": "premium",
                    "conditions": [
                        {"operator": "equals", "property": "plan", "expected": "premium"}
                    ],
                    "value": 1000,
                }
            ],
        }
        config = parse_config(data)
        assert config.name == "rate-limit"
        assert config.value == 100
        assert len(config.overrides) == 1
        assert config.overrides[0].value == 1000

    def test_parse_config_json_value(self):
        data = {
            "name": "settings",
            "value": {"theme": "dark", "notifications": True},
        }
        config = parse_config(data)
        assert config.value == {"theme": "dark", "notifications": True}

    def test_parse_config_array_value(self):
        data = {"name": "allowed-origins", "value": ["localhost", "example.com"]}
        config = parse_config(data)
        assert config.value == ["localhost", "example.com"]


class TestDataclassImmutability:
    """Tests for dataclass frozen behavior."""

    def test_property_condition_immutable(self):
        cond = PropertyCondition(operator="equals", property="x", expected=1)
        with pytest.raises(AttributeError):
            cond.expected = 2  # type: ignore

    def test_override_immutable(self):
        override = Override(name="test", conditions=(), value=1)
        with pytest.raises(AttributeError):
            override.value = 2  # type: ignore

    def test_config_mutable(self):
        # Config is intentionally mutable for updates
        config = Config(name="test", value=1)
        config.value = 2
        assert config.value == 2
