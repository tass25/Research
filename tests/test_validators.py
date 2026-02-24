"""Tests for validators package (Priority 1 syntactic validation)."""

import pytest
from validators.base import ValidationWarning, ValidationViolation
from validators.preparse import PreParseValidator
from validators.structure import StructureValidator
from validators.absolute_bounds import AbsoluteBoundValidator
from core.schema import Variable, Constant, Relation, Conjunction, Disjunction
from core.types import RelOp


# ── ValidationWarning / ValidationViolation ────────────────────────────

class TestBase:
    def test_warning_fields(self):
        w = ValidationWarning("cat", "msg", "orig", "fixed")
        assert w.category == "cat"
        assert w.message == "msg"
        assert w.original == "orig"
        assert w.corrected == "fixed"

    def test_violation_fields(self):
        v = ValidationViolation("cat", "error", "msg", "loc")
        assert v.category == "cat"
        assert v.severity == "error"
        assert v.message == "msg"
        assert v.location == "loc"

    def test_violation_default_location(self):
        v = ValidationViolation("cat", "error", "msg")
        assert v.location == ""


# ── PreParseValidator ──────────────────────────────────────────────────

class TestPreParseValidator:
    def setup_method(self):
        self.validator = PreParseValidator()

    def test_clean_input_no_changes(self):
        norm, warnings, violations = self.validator.normalize_and_validate(
            "(ego_speed > 10) ∧ (dist_front < 5)"
        )
        assert norm == "(ego_speed > 10) ∧ (dist_front < 5)"
        assert warnings == []
        assert violations == []

    def test_unicode_le_normalization(self):
        norm, warnings, violations = self.validator.normalize_and_validate(
            "ego_speed ≤ 10"
        )
        assert "<=" in norm
        assert "≤" not in norm
        assert len(warnings) == 1
        assert warnings[0].category == "unicode"

    def test_unicode_ge_normalization(self):
        norm, warnings, _ = self.validator.normalize_and_validate("ego_speed ≥ 20")
        assert ">=" in norm
        assert len(warnings) == 1

    def test_unicode_ne_normalization(self):
        norm, warnings, _ = self.validator.normalize_and_validate("ego_speed ≠ 0")
        assert "!=" in norm
        assert len(warnings) == 1

    def test_hidden_character_removal(self):
        norm, warnings, _ = self.validator.normalize_and_validate(
            "ego_speed\u200b > 10"
        )
        assert "\u200b" not in norm
        assert len(warnings) == 1
        assert warnings[0].category == "hidden"

    def test_multiple_hidden_chars(self):
        norm, warnings, _ = self.validator.normalize_and_validate(
            "\ufeffego_speed\u2060 > 10"
        )
        assert "\ufeff" not in norm
        assert "\u2060" not in norm
        assert len(warnings) == 2

    def test_invalid_operator_detected(self):
        _, _, violations = self.validator.normalize_and_validate("x << 5")
        assert len(violations) >= 1
        assert violations[0].category == "operators"

    def test_combined_normalization(self):
        norm, warnings, violations = self.validator.normalize_and_validate(
            "ego_speed ≤ 50 ⋀ dist_front ≥ 3"
        )
        assert "≤" not in norm
        assert "≥" not in norm
        assert "<=" in norm
        assert ">=" in norm
        assert len(warnings) >= 2
        assert violations == []


# ── StructureValidator ─────────────────────────────────────────────────

class TestStructureValidator:
    def _rel(self, var="x", val=1.0, op=RelOp.GT):
        return Relation(Variable(var), op, Constant(val))

    def test_simple_relation_passes(self):
        v = StructureValidator(max_depth=5, max_predicates=10)
        violations = v.validate(self._rel())
        assert violations == []

    def test_conjunction_passes(self):
        v = StructureValidator(max_depth=5, max_predicates=10)
        rule = Conjunction([self._rel("x"), self._rel("y")])
        violations = v.validate(rule)
        assert violations == []

    def test_depth_exceeded(self):
        v = StructureValidator(max_depth=1, max_predicates=100)
        # Depth 2: Disjunction → Conjunction → Relation
        rule = Disjunction([Conjunction([self._rel()])])
        violations = v.validate(rule)
        assert len(violations) == 1
        assert "depth" in violations[0].message.lower()

    def test_predicate_count_exceeded(self):
        v = StructureValidator(max_depth=100, max_predicates=2)
        rule = Conjunction([self._rel("a"), self._rel("b"), self._rel("c")])
        violations = v.validate(rule)
        assert len(violations) == 1
        assert "predicate count" in violations[0].message.lower()

    def test_both_limits_exceeded(self):
        v = StructureValidator(max_depth=1, max_predicates=1)
        # Depth calculated from 0, relation at depth 0 is fine
        # but max_depth=0 won't allow nesting
        # Let's use proper nesting
        v2 = StructureValidator(max_depth=1, max_predicates=1)
        rule = Disjunction([Conjunction([self._rel("a"), self._rel("b")])])
        violations = v2.validate(rule)
        assert len(violations) == 2  # depth + predicates

    def test_invalid_max_depth(self):
        with pytest.raises(ValueError, match="max_depth must be positive"):
            StructureValidator(max_depth=0)

    def test_invalid_max_predicates(self):
        with pytest.raises(ValueError, match="max_predicates must be positive"):
            StructureValidator(max_predicates=0)

    def test_depth_computation_nested(self):
        v = StructureValidator(max_depth=10, max_predicates=100)
        # depth 0: relation
        assert v._depth(self._rel()) == 0
        # depth 1: conjunction containing relation
        assert v._depth(Conjunction([self._rel()])) == 1

    def test_count_computation(self):
        v = StructureValidator()
        rule = Disjunction([
            Conjunction([self._rel("a"), self._rel("b")]),
            self._rel("c"),
        ])
        assert v._count(rule) == 3


# ── AbsoluteBoundValidator ─────────────────────────────────────────────

class TestAbsoluteBoundValidator:
    def setup_method(self):
        self.bounds = {
            "ego_speed": (0.0, 50.0),
            "dist_front": (0.0, 200.0),
        }
        self.validator = AbsoluteBoundValidator(self.bounds)

    def test_within_bounds_passes(self):
        rule = Relation(Variable("ego_speed"), RelOp.GT, Constant(25.0))
        violations = self.validator.validate(rule)
        assert violations == []

    def test_above_upper_bound_fails(self):
        rule = Relation(Variable("ego_speed"), RelOp.LT, Constant(100.0))
        violations = self.validator.validate(rule)
        assert len(violations) == 1
        assert "outside" in violations[0].message.lower()

    def test_below_lower_bound_fails(self):
        rule = Relation(Variable("ego_speed"), RelOp.GT, Constant(-5.0))
        violations = self.validator.validate(rule)
        assert len(violations) == 1

    def test_unknown_variable_passes(self):
        rule = Relation(Variable("unknown_var"), RelOp.GT, Constant(999.0))
        violations = self.validator.validate(rule)
        assert violations == []

    def test_conjunction_all_valid(self):
        rule = Conjunction([
            Relation(Variable("ego_speed"), RelOp.GT, Constant(10.0)),
            Relation(Variable("dist_front"), RelOp.LT, Constant(100.0)),
        ])
        violations = self.validator.validate(rule)
        assert violations == []

    def test_conjunction_one_invalid(self):
        rule = Conjunction([
            Relation(Variable("ego_speed"), RelOp.GT, Constant(10.0)),
            Relation(Variable("dist_front"), RelOp.LT, Constant(500.0)),
        ])
        violations = self.validator.validate(rule)
        assert len(violations) == 1

    def test_constant_on_left_side(self):
        rule = Relation(Constant(999.0), RelOp.LT, Variable("ego_speed"))
        violations = self.validator.validate(rule)
        assert len(violations) == 1

    def test_boundary_value_passes(self):
        rule = Relation(Variable("ego_speed"), RelOp.LE, Constant(50.0))
        violations = self.validator.validate(rule)
        assert violations == []

    def test_invalid_bounds_constructor(self):
        with pytest.raises(ValueError, match="Invalid bounds"):
            AbsoluteBoundValidator({"x": (10.0, 5.0)})

    def test_disjunction_validation(self):
        rule = Disjunction([
            Relation(Variable("ego_speed"), RelOp.GT, Constant(25.0)),
            Relation(Variable("dist_front"), RelOp.LT, Constant(-10.0)),
        ])
        violations = self.validator.validate(rule)
        assert len(violations) == 1
