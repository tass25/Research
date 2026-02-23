"""Tests for shared/grammar_validation.py."""

import pytest
from shared.grammar_validation import (
    validate_rule, validate_dnf, is_grammar_valid, is_valid_dnf,
    GrammarCheckResult, _tokenize_rule,
)


ALLOWED_VARS = [
    "initial_distance_to_obstacle", "initial_speed",
    "obstacle_radius", "initial_heading_error",
]


class TestTokenizer:
    def test_simple_tokens(self):
        tokens = _tokenize_rule("x > 5")
        assert tokens == ["x", ">", "5"]

    def test_le_operator(self):
        tokens = _tokenize_rule("x <= 10")
        assert "<=" in tokens

    def test_ge_operator(self):
        tokens = _tokenize_rule("x >= 3")
        assert ">=" in tokens

    def test_ne_operator(self):
        tokens = _tokenize_rule("x != 0")
        assert "!=" in tokens

    def test_parentheses(self):
        tokens = _tokenize_rule("(x > 5) AND (y < 3)")
        assert "(" in tokens
        assert ")" in tokens
        assert "AND" in tokens

    def test_negative_number(self):
        tokens = _tokenize_rule("x > -5")
        # Negative numbers get split; tokenizer handles them as separate tokens
        assert "-5" in tokens or ("-" in tokens and "5" in tokens)


class TestValidateRule:
    def test_simple_valid_rule(self):
        result = validate_rule("initial_speed > 1.5", ALLOWED_VARS)
        assert result.is_valid is True
        assert result.n_predicates == 1
        assert "initial_speed" in result.variables_used

    def test_conjunction(self):
        result = validate_rule(
            "initial_speed > 1 AND obstacle_radius <= 0.5",
            ALLOWED_VARS,
        )
        assert result.is_valid is True
        assert result.n_predicates == 2
        assert result.n_conjunctions >= 1

    def test_disjunction(self):
        result = validate_rule(
            "initial_speed > 2 OR obstacle_radius < 0.3",
            ALLOWED_VARS,
        )
        assert result.is_valid is True
        assert result.n_conjunctions == 2  # 2 disjuncts

    def test_unknown_variable(self):
        result = validate_rule("bogus_var > 5", ALLOWED_VARS)
        assert result.is_valid is False
        assert len(result.errors) >= 1
        assert "bogus_var" in result.errors[0]

    def test_empty_input(self):
        result = validate_rule("", ALLOWED_VARS)
        assert result.is_valid is False
        assert "Empty" in result.errors[0]

    def test_whitespace_only(self):
        result = validate_rule("   ", ALLOWED_VARS)
        assert result.is_valid is False

    def test_unmatched_parens(self):
        result = validate_rule("(initial_speed > 5", ALLOWED_VARS)
        assert result.is_valid is False
        assert any("parenthes" in e.lower() for e in result.errors)

    def test_invalid_token(self):
        result = validate_rule("initial_speed > @#$", ALLOWED_VARS)
        assert result.is_valid is False

    def test_complexity_warning(self):
        # 11 predicates should trigger warning
        preds = " AND ".join(
            f"initial_speed > {i}" for i in range(11)
        )
        result = validate_rule(preds, ALLOWED_VARS)
        assert result.is_valid is True
        assert any("complexity" in w.lower() for w in result.warnings)


class TestValidateDNF:
    def test_simple_predicate(self):
        ok, msg = validate_dnf("initial_speed > 1.5")
        assert ok is True

    def test_conjunction(self):
        ok, msg = validate_dnf(
            "initial_speed > 1 AND obstacle_radius <= 0.5"
        )
        assert ok is True

    def test_disjunction_of_conjunctions(self):
        ok, msg = validate_dnf(
            "(initial_speed > 1 AND obstacle_radius <= 0.5) OR "
            "(initial_distance_to_obstacle < 2)"
        )
        assert ok is True
        assert "2 clause" in msg

    def test_invalid_predicate(self):
        ok, msg = validate_dnf("hello world")
        assert ok is False
        assert "not a simple comparison" in msg

    def test_empty(self):
        ok, msg = validate_dnf("")
        assert ok is False


class TestConvenienceHelpers:
    def test_is_grammar_valid(self):
        assert is_grammar_valid("initial_speed > 5", ALLOWED_VARS) is True
        assert is_grammar_valid("bogus > 5", ALLOWED_VARS) is False

    def test_is_valid_dnf(self):
        assert is_valid_dnf("initial_speed > 5") is True
        assert is_valid_dnf("not_a_rule") is False
