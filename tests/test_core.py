"""Tests for core package (config, schema, types)."""

import pytest
from core.types import RelOp, ArithOp
from core.schema import (
    Variable, Constant, BinaryExpr, Relation,
    Conjunction, Disjunction,
)
from core.config import GrammarConfig, DEFAULT_ADS_CONFIG


# ── RelOp ──────────────────────────────────────────────────────────────

class TestRelOp:
    @pytest.mark.parametrize("s,expected", [
        ("<", RelOp.LT), ("<=", RelOp.LE), (">", RelOp.GT),
        (">=", RelOp.GE), ("=", RelOp.EQ), ("!=", RelOp.NE),
    ])
    def test_from_string(self, s, expected):
        assert RelOp.from_string(s) == expected

    def test_invalid_operator(self):
        with pytest.raises(ValueError, match="Invalid relational"):
            RelOp.from_string("<<")


# ── ArithOp ────────────────────────────────────────────────────────────

class TestArithOp:
    @pytest.mark.parametrize("s,expected", [
        ("+", ArithOp.ADD), ("-", ArithOp.SUB),
        ("*", ArithOp.MUL), ("/", ArithOp.DIV),
    ])
    def test_from_string(self, s, expected):
        assert ArithOp.from_string(s) == expected

    def test_invalid_operator(self):
        with pytest.raises(ValueError, match="Invalid arithmetic"):
            ArithOp.from_string("%")


# ── Variable ───────────────────────────────────────────────────────────

class TestVariable:
    def test_evaluate(self):
        v = Variable("ego_speed")
        assert v.evaluate({"ego_speed": 25.0}) == 25.0

    def test_missing_variable(self):
        v = Variable("unknown")
        with pytest.raises(KeyError, match="unknown"):
            v.evaluate({"ego_speed": 10.0})

    def test_frozen(self):
        v = Variable("x")
        with pytest.raises(AttributeError):
            v.name = "y"


# ── Constant ───────────────────────────────────────────────────────────

class TestConstant:
    def test_evaluate(self):
        c = Constant(42.0)
        assert c.evaluate({}) == 42.0
        assert c.evaluate({"ego_speed": 10.0}) == 42.0

    def test_negative(self):
        c = Constant(-3.14)
        assert c.evaluate({}) == -3.14


# ── BinaryExpr ─────────────────────────────────────────────────────────

class TestBinaryExpr:
    def test_add(self):
        expr = BinaryExpr(Variable("x"), ArithOp.ADD, Constant(5.0))
        assert expr.evaluate({"x": 10.0}) == 15.0

    def test_sub(self):
        expr = BinaryExpr(Variable("x"), ArithOp.SUB, Constant(3.0))
        assert expr.evaluate({"x": 10.0}) == 7.0

    def test_mul(self):
        expr = BinaryExpr(Variable("x"), ArithOp.MUL, Constant(2.0))
        assert expr.evaluate({"x": 5.0}) == 10.0

    def test_div(self):
        expr = BinaryExpr(Variable("x"), ArithOp.DIV, Constant(4.0))
        assert expr.evaluate({"x": 20.0}) == 5.0

    def test_div_by_zero(self):
        expr = BinaryExpr(Variable("x"), ArithOp.DIV, Constant(0.0))
        with pytest.raises(ZeroDivisionError):
            expr.evaluate({"x": 10.0})


# ── Relation ───────────────────────────────────────────────────────────

class TestRelation:
    def _env(self):
        return {"ego_speed": 25.0, "dist_front": 10.0}

    def test_lt_true(self):
        r = Relation(Variable("dist_front"), RelOp.LT, Constant(15.0))
        assert r.evaluate(self._env()) is True

    def test_lt_false(self):
        r = Relation(Variable("dist_front"), RelOp.LT, Constant(5.0))
        assert r.evaluate(self._env()) is False

    def test_le_boundary(self):
        r = Relation(Variable("dist_front"), RelOp.LE, Constant(10.0))
        assert r.evaluate(self._env()) is True

    def test_gt(self):
        r = Relation(Variable("ego_speed"), RelOp.GT, Constant(20.0))
        assert r.evaluate(self._env()) is True

    def test_ge(self):
        r = Relation(Variable("ego_speed"), RelOp.GE, Constant(25.0))
        assert r.evaluate(self._env()) is True

    def test_eq(self):
        r = Relation(Variable("ego_speed"), RelOp.EQ, Constant(25.0))
        assert r.evaluate(self._env()) is True

    def test_ne(self):
        r = Relation(Variable("ego_speed"), RelOp.NE, Constant(0.0))
        assert r.evaluate(self._env()) is True


# ── Conjunction ────────────────────────────────────────────────────────

class TestConjunction:
    def test_all_true(self):
        c = Conjunction([
            Relation(Variable("x"), RelOp.GT, Constant(5.0)),
            Relation(Variable("y"), RelOp.LT, Constant(20.0)),
        ])
        assert c.evaluate({"x": 10.0, "y": 15.0}) is True

    def test_one_false(self):
        c = Conjunction([
            Relation(Variable("x"), RelOp.GT, Constant(5.0)),
            Relation(Variable("y"), RelOp.LT, Constant(10.0)),
        ])
        assert c.evaluate({"x": 10.0, "y": 15.0}) is False

    def test_empty_conjunction_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            Conjunction([])


# ── Disjunction ────────────────────────────────────────────────────────

class TestDisjunction:
    def test_one_true(self):
        d = Disjunction([
            Relation(Variable("x"), RelOp.GT, Constant(100.0)),
            Relation(Variable("y"), RelOp.LT, Constant(20.0)),
        ])
        assert d.evaluate({"x": 5.0, "y": 10.0}) is True

    def test_both_false(self):
        d = Disjunction([
            Relation(Variable("x"), RelOp.GT, Constant(100.0)),
            Relation(Variable("y"), RelOp.GT, Constant(100.0)),
        ])
        assert d.evaluate({"x": 5.0, "y": 5.0}) is False

    def test_empty_disjunction_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            Disjunction([])


# ── GrammarConfig ──────────────────────────────────────────────────────

class TestGrammarConfig:
    def test_valid_config(self):
        gc = GrammarConfig(
            allowed_variables={"x", "y"},
            variable_bounds={"x": (0.0, 50.0)},
        )
        assert "x" in gc.allowed_variables
        assert gc.variable_bounds["x"] == (0.0, 50.0)

    def test_empty_variables_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            GrammarConfig(allowed_variables=set(), variable_bounds={})

    def test_inverted_bounds_raises(self):
        with pytest.raises(ValueError, match="lower.*upper"):
            GrammarConfig(
                allowed_variables={"x"},
                variable_bounds={"x": (100.0, 0.0)},
            )

    def test_default_ads_config(self):
        assert "ego_speed" in DEFAULT_ADS_CONFIG.allowed_variables
        assert "dist_front" in DEFAULT_ADS_CONFIG.allowed_variables
        assert DEFAULT_ADS_CONFIG.variable_bounds["ego_speed"] == (0.0, 50.0)
