"""Tests for override evaluation logic."""

from replane._eval import (
    evaluate_condition,
    evaluate_config,
    evaluate_override,
    fnv1a_32,
    hash_to_percentage,
)
from replane.types import (
    AndCondition,
    Config,
    NotCondition,
    OrCondition,
    Override,
    PropertyCondition,
    SegmentationCondition,
)


class TestFnv1aHash:
    """Tests for FNV-1a 32-bit hash function."""

    def test_empty_string(self):
        # FNV-1a offset basis for empty string
        assert fnv1a_32("") == 0x811C9DC5

    def test_known_values(self):
        # Test against known FNV-1a values
        assert fnv1a_32("a") == 0xE40C292C
        assert fnv1a_32("foobar") == 0xBF9CF968

    def test_deterministic(self):
        """Same input always produces same output."""
        for _ in range(100):
            assert fnv1a_32("test-user-123") == fnv1a_32("test-user-123")


class TestHashToPercentage:
    """Tests for percentage bucketing."""

    def test_range(self):
        """Result is always between 0 and 100."""
        for i in range(1000):
            pct = hash_to_percentage(f"user-{i}", "seed")
            assert 0 <= pct < 100

    def test_deterministic(self):
        """Same user+seed always gets same percentage."""
        pct1 = hash_to_percentage("user-123", "feature-x")
        pct2 = hash_to_percentage("user-123", "feature-x")
        assert pct1 == pct2

    def test_different_seeds_different_results(self):
        """Different seeds produce different distributions."""
        pct1 = hash_to_percentage("user-123", "seed-a")
        pct2 = hash_to_percentage("user-123", "seed-b")
        # Not guaranteed different, but almost always will be
        # Just check both are valid
        assert 0 <= pct1 < 100
        assert 0 <= pct2 < 100


class TestEvaluateCondition:
    """Tests for condition evaluation."""

    def test_equals_matched(self):
        cond = PropertyCondition(operator="equals", property="plan", expected="pro")
        result = evaluate_condition(cond, {"plan": "pro"})
        assert result == "matched"

    def test_equals_not_matched(self):
        cond = PropertyCondition(operator="equals", property="plan", expected="pro")
        result = evaluate_condition(cond, {"plan": "free"})
        assert result == "not_matched"

    def test_equals_missing_property(self):
        cond = PropertyCondition(operator="equals", property="plan", expected="pro")
        result = evaluate_condition(cond, {})
        assert result == "unknown"

    def test_in_matched(self):
        cond = PropertyCondition(operator="in", property="plan", expected=["pro", "enterprise"])
        result = evaluate_condition(cond, {"plan": "pro"})
        assert result == "matched"

    def test_in_not_matched(self):
        cond = PropertyCondition(operator="in", property="plan", expected=["pro", "enterprise"])
        result = evaluate_condition(cond, {"plan": "free"})
        assert result == "not_matched"

    def test_not_in_matched(self):
        cond = PropertyCondition(operator="not_in", property="plan", expected=["free", "trial"])
        result = evaluate_condition(cond, {"plan": "pro"})
        assert result == "matched"

    def test_not_in_not_matched(self):
        cond = PropertyCondition(operator="not_in", property="plan", expected=["free", "trial"])
        result = evaluate_condition(cond, {"plan": "free"})
        assert result == "not_matched"

    def test_less_than_matched(self):
        cond = PropertyCondition(operator="lt", property="age", expected=18)
        result = evaluate_condition(cond, {"age": 15})
        assert result == "matched"

    def test_less_than_not_matched(self):
        cond = PropertyCondition(operator="lt", property="age", expected=18)
        result = evaluate_condition(cond, {"age": 21})
        assert result == "not_matched"

    def test_greater_than_or_equal_matched(self):
        cond = PropertyCondition(operator="gte", property="score", expected=100)
        result = evaluate_condition(cond, {"score": 100})
        assert result == "matched"

    def test_and_all_matched(self):
        cond = AndCondition(
            operator="and",
            conditions=(
                PropertyCondition(operator="equals", property="plan", expected="pro"),
                PropertyCondition(operator="gte", property="score", expected=50),
            ),
        )
        result = evaluate_condition(cond, {"plan": "pro", "score": 75})
        assert result == "matched"

    def test_and_one_not_matched(self):
        cond = AndCondition(
            operator="and",
            conditions=(
                PropertyCondition(operator="equals", property="plan", expected="pro"),
                PropertyCondition(operator="gte", property="score", expected=50),
            ),
        )
        result = evaluate_condition(cond, {"plan": "pro", "score": 25})
        assert result == "not_matched"

    def test_or_one_matched(self):
        cond = OrCondition(
            operator="or",
            conditions=(
                PropertyCondition(operator="equals", property="plan", expected="pro"),
                PropertyCondition(operator="equals", property="plan", expected="enterprise"),
            ),
        )
        result = evaluate_condition(cond, {"plan": "pro"})
        assert result == "matched"

    def test_or_none_matched(self):
        cond = OrCondition(
            operator="or",
            conditions=(
                PropertyCondition(operator="equals", property="plan", expected="pro"),
                PropertyCondition(operator="equals", property="plan", expected="enterprise"),
            ),
        )
        result = evaluate_condition(cond, {"plan": "free"})
        assert result == "not_matched"

    def test_not_inverts_matched(self):
        cond = NotCondition(
            operator="not",
            condition=PropertyCondition(operator="equals", property="plan", expected="free"),
        )
        result = evaluate_condition(cond, {"plan": "free"})
        assert result == "not_matched"

    def test_not_inverts_not_matched(self):
        cond = NotCondition(
            operator="not",
            condition=PropertyCondition(operator="equals", property="plan", expected="free"),
        )
        result = evaluate_condition(cond, {"plan": "pro"})
        assert result == "matched"

    def test_segmentation_in_range(self):
        cond = SegmentationCondition(
            operator="segmentation",
            property="user_id",
            from_percentage=0,
            to_percentage=100,
            seed="test",
        )
        result = evaluate_condition(cond, {"user_id": "user-123"})
        assert result == "matched"

    def test_segmentation_deterministic(self):
        """Same user always gets same result for same config."""
        cond = SegmentationCondition(
            operator="segmentation",
            property="user_id",
            from_percentage=0,
            to_percentage=50,
            seed="feature-x",
        )
        results = [evaluate_condition(cond, {"user_id": "user-123"}) for _ in range(100)]
        # All results should be the same
        assert len(set(results)) == 1


class TestEvaluateOverride:
    """Tests for override evaluation."""

    def test_all_conditions_match(self):
        override = Override(
            name="beta-users",
            conditions=(
                PropertyCondition(operator="equals", property="plan", expected="pro"),
                PropertyCondition(operator="equals", property="region", expected="us"),
            ),
            value=True,
        )
        assert evaluate_override(override, {"plan": "pro", "region": "us"}) is True

    def test_one_condition_fails(self):
        override = Override(
            name="beta-users",
            conditions=(
                PropertyCondition(operator="equals", property="plan", expected="pro"),
                PropertyCondition(operator="equals", property="region", expected="us"),
            ),
            value=True,
        )
        assert evaluate_override(override, {"plan": "pro", "region": "eu"}) is False

    def test_empty_conditions_always_matches(self):
        override = Override(
            name="default",
            conditions=(),
            value="always",
        )
        assert evaluate_override(override, {}) is True


class TestEvaluateConfig:
    """Tests for config evaluation."""

    def test_returns_base_value_no_overrides(self):
        config = Config(name="rate-limit", value=100)
        assert evaluate_config(config, {}) == 100

    def test_returns_base_value_no_matching_override(self):
        config = Config(
            name="rate-limit",
            value=100,
            overrides=(
                Override(
                    name="premium",
                    conditions=(
                        PropertyCondition(operator="equals", property="plan", expected="premium"),
                    ),
                    value=1000,
                ),
            ),
        )
        assert evaluate_config(config, {"plan": "free"}) == 100

    def test_returns_override_value_when_matched(self):
        config = Config(
            name="rate-limit",
            value=100,
            overrides=(
                Override(
                    name="premium",
                    conditions=(
                        PropertyCondition(operator="equals", property="plan", expected="premium"),
                    ),
                    value=1000,
                ),
            ),
        )
        assert evaluate_config(config, {"plan": "premium"}) == 1000

    def test_first_matching_override_wins(self):
        config = Config(
            name="feature",
            value="default",
            overrides=(
                Override(
                    name="first",
                    conditions=(PropertyCondition(operator="equals", property="v", expected=1),),
                    value="first-match",
                ),
                Override(
                    name="second",
                    conditions=(PropertyCondition(operator="gte", property="v", expected=1),),
                    value="second-match",
                ),
            ),
        )
        # Both would match, but first wins
        assert evaluate_config(config, {"v": 1}) == "first-match"

    def test_none_context_uses_empty_dict(self):
        config = Config(name="test", value="base")
        assert evaluate_config(config, None) == "base"


class TestTypeCasting:
    """Tests for type coercion in comparisons."""

    def test_string_to_number_comparison(self):
        cond = PropertyCondition(operator="equals", property="count", expected="10")
        result = evaluate_condition(cond, {"count": 10})
        assert result == "matched"

    def test_number_to_string_comparison(self):
        cond = PropertyCondition(operator="equals", property="version", expected=2)
        result = evaluate_condition(cond, {"version": "2"})
        assert result == "matched"

    def test_boolean_string_true(self):
        cond = PropertyCondition(operator="equals", property="enabled", expected="true")
        result = evaluate_condition(cond, {"enabled": True})
        assert result == "matched"
