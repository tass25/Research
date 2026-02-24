"""Tests for parsers/lark_parser.py (Lark grammar-based parser)."""

import pytest
from parsers.lark_parser import OperationalRuleParser
from core.config import DEFAULT_ADS_CONFIG
from core.schema import Relation, Conjunction, Disjunction, Variable, Constant
from core.types import RelOp


@pytest.fixture
def parser():
    return OperationalRuleParser(DEFAULT_ADS_CONFIG)


class TestParserBasic:
    def test_simple_relation(self, parser):
        rule = parser.parse("ego_speed > 10")
        assert isinstance(rule, Disjunction)
        assert len(rule.items) == 1

    def test_simple_relation_evaluates(self, parser):
        rule = parser.parse("ego_speed > 10")
        assert rule.evaluate({"ego_speed": 25.0}) is True
        assert rule.evaluate({"ego_speed": 5.0}) is False

    def test_le_operator(self, parser):
        rule = parser.parse("dist_front <= 5")
        assert rule.evaluate({"dist_front": 5.0}) is True
        assert rule.evaluate({"dist_front": 6.0}) is False

    def test_ge_operator(self, parser):
        rule = parser.parse("ego_speed >= 20")
        assert rule.evaluate({"ego_speed": 20.0}) is True
        assert rule.evaluate({"ego_speed": 19.0}) is False

    def test_eq_operator(self, parser):
        rule = parser.parse("ego_speed = 25")
        assert rule.evaluate({"ego_speed": 25.0}) is True
        assert rule.evaluate({"ego_speed": 24.0}) is False

    def test_ne_operator(self, parser):
        rule = parser.parse("ego_speed != 0")
        assert rule.evaluate({"ego_speed": 10.0}) is True
        assert rule.evaluate({"ego_speed": 0.0}) is False


class TestParserConjunction:
    def test_and_keyword(self, parser):
        rule = parser.parse("(ego_speed > 10) AND (dist_front < 5)")
        assert isinstance(rule, Disjunction)
        env = {"ego_speed": 20.0, "dist_front": 3.0}
        assert rule.evaluate(env) is True

    def test_and_unicode(self, parser):
        rule = parser.parse("(ego_speed > 10) ∧ (dist_front < 5)")
        env = {"ego_speed": 20.0, "dist_front": 3.0}
        assert rule.evaluate(env) is True

    def test_conjunction_false_when_one_fails(self, parser):
        rule = parser.parse("(ego_speed > 10) AND (dist_front < 5)")
        env = {"ego_speed": 20.0, "dist_front": 10.0}
        assert rule.evaluate(env) is False


class TestParserDisjunction:
    def test_or_keyword(self, parser):
        rule = parser.parse("(ego_speed > 30) OR (dist_front < 2)")
        env = {"ego_speed": 5.0, "dist_front": 1.0}
        assert rule.evaluate(env) is True

    def test_or_unicode(self, parser):
        rule = parser.parse("(ego_speed > 30) ∨ (dist_front < 2)")
        env = {"ego_speed": 50.0, "dist_front": 100.0}
        assert rule.evaluate(env) is True


class TestParserComplex:
    def test_nested_conjunction_in_disjunction(self, parser):
        rule = parser.parse(
            "((ego_speed > 10) AND (dist_front < 5)) OR (lane_offset < 1)"
        )
        # First clause satisfied
        assert rule.evaluate({"ego_speed": 20.0, "dist_front": 3.0, "lane_offset": 5.0}) is True
        # Second clause satisfied
        assert rule.evaluate({"ego_speed": 5.0, "dist_front": 50.0, "lane_offset": 0.5}) is True
        # Neither satisfied
        assert rule.evaluate({"ego_speed": 5.0, "dist_front": 50.0, "lane_offset": 5.0}) is False

    def test_negative_constant(self, parser):
        rule = parser.parse("rel_speed > -10")
        assert rule.evaluate({"rel_speed": 0.0}) is True
        assert rule.evaluate({"rel_speed": -20.0}) is False

    def test_decimal_constant(self, parser):
        rule = parser.parse("ego_speed > 10.5")
        assert rule.evaluate({"ego_speed": 11.0}) is True
        assert rule.evaluate({"ego_speed": 10.0}) is False


class TestParserSafe:
    def test_safe_parse_success(self, parser):
        rule, errors = parser.parse_safe("ego_speed > 10")
        assert rule is not None
        assert errors == []

    def test_safe_parse_invalid_variable(self, parser):
        rule, errors = parser.parse_safe("unknown_var > 10")
        assert rule is None
        assert len(errors) > 0

    def test_safe_parse_syntax_error(self, parser):
        rule, errors = parser.parse_safe(">>><<<<")
        assert rule is None
        assert len(errors) > 0


class TestParserEdgeCases:
    def test_all_four_variables(self, parser):
        rule = parser.parse(
            "((ego_speed > 10) AND (dist_front < 50)) OR "
            "((lane_offset > -2) AND (rel_speed < 15))"
        )
        env = {"ego_speed": 20, "dist_front": 30, "lane_offset": 0, "rel_speed": 10}
        assert rule.evaluate(env) is True

    def test_zero_constant(self, parser):
        rule = parser.parse("ego_speed > 0")
        assert rule.evaluate({"ego_speed": 1.0}) is True
        assert rule.evaluate({"ego_speed": 0.0}) is False


class TestParserArithmetic:
    """Test that Lark parser accepts arithmetic expressions.
    
    The Lark grammar allows arithmetic (+, -, *, /) inside comparisons,
    even though grammar_validation.py issues warnings for these. This is
    by design: the parser is permissive to handle real-world LLM outputs.
    """

    def test_addition_in_comparison(self, parser):
        rule = parser.parse("ego_speed + 5 > 20")
        assert rule is not None
        assert isinstance(rule, Disjunction)

    def test_subtraction_in_comparison(self, parser):
        rule = parser.parse("dist_front - 2 > 3")
        assert rule is not None

    def test_multiplication_in_comparison(self, parser):
        rule = parser.parse("ego_speed * 2 > 50")
        assert rule is not None

    def test_division_in_comparison(self, parser):
        rule = parser.parse("dist_front / 10 > 1")
        assert rule is not None

    def test_arithmetic_produces_binary_expr(self, parser):
        from core.schema import BinaryExpr
        rule = parser.parse("ego_speed + 5 > 20")
        # Root is Disjunction → item is Relation → left is BinaryExpr
        rel = rule.items[0]
        assert isinstance(rel, Relation)
        assert isinstance(rel.left, BinaryExpr)

    def test_arithmetic_and_normal_conjunction(self, parser):
        rule = parser.parse("(ego_speed + 5 > 20) AND (dist_front < 10)")
        assert rule is not None
        assert rule.evaluate is not None

