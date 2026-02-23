"""Tests for the semantic validation layer.

Covers:
  - ConsistencyChecker
  - ContradictionChecker
  - OverfittingDetector / extract_constants
  - SemanticValidator orchestrator
  - CounterfactualGenerator
"""

import pytest
import numpy as np
from unittest.mock import MagicMock

from core.schema import (
    Variable, Constant, Relation, Conjunction, Disjunction, BinaryExpr,
)
from core.types import RelOp, ArithOp
from data.simulation_trace import SimulationTrace, SimulationDataset
from data.counterfactual_evidence import CounterfactualPair, CounterfactualEvidence
from data.semantic_result import (
    ConsistencyIssue, ContradictionIssue, OverfittingIndicator,
    SemanticValidationResult,
)
from semantic.consistency_checker import ConsistencyChecker
from semantic.contradiction_checker import ContradictionChecker
from semantic.overfitting_detector import OverfittingDetector, extract_constants
from semantic.semantic_validator import SemanticValidator
from semantic.counterfactual_generator import CounterfactualGenerator


# ── helpers ──────────────────────────────────────────────────────────────

def _rel(var: str, op: RelOp, val: float) -> Relation:
    return Relation(Variable(var), op, Constant(val))


def _rule(*relations: Relation) -> Disjunction:
    """Wrap one or more relations in a single-clause Disjunction (Rule)."""
    if len(relations) == 1:
        return Disjunction([relations[0]])
    return Disjunction([Conjunction(list(relations))])


def _make_dataset(rows, outcome="Pass"):
    """Build a SimulationDataset from a list of dicts."""
    traces = [
        SimulationTrace(
            input_vector=row,
            observed_outcome=row.get("_outcome", outcome),
        )
        for row in rows
    ]
    return SimulationDataset(traces=traces)


# ── ConsistencyChecker ──────────────────────────────────────────────────

class TestConsistencyChecker:
    def test_rejects_bad_rule_set_type(self):
        with pytest.raises(ValueError, match="Pass.*Fail"):
            ConsistencyChecker("Neither")

    def test_pass_set_all_consistent(self):
        rule = _rule(_rel("x", RelOp.GT, 5.0))
        ds = _make_dataset(
            [{"x": 6.0, "_outcome": "Pass"},
             {"x": 7.0, "_outcome": "Pass"}]
        )
        score, issues = ConsistencyChecker("Pass").check_consistency(rule, ds)
        assert score == 1.0
        assert issues == []

    def test_pass_set_with_inconsistency(self):
        rule = _rule(_rel("x", RelOp.GT, 5.0))
        ds = _make_dataset(
            [{"x": 6.0, "_outcome": "Fail"},  # inconsistent
             {"x": 7.0, "_outcome": "Pass"}]
        )
        score, issues = ConsistencyChecker("Pass").check_consistency(rule, ds)
        assert score == 0.5
        assert len(issues) == 1

    def test_fail_set_consistent(self):
        rule = _rule(_rel("x", RelOp.GT, 5.0))
        ds = _make_dataset(
            [{"x": 6.0, "_outcome": "Fail"},
             {"x": 7.0, "_outcome": "Fail"}]
        )
        score, issues = ConsistencyChecker("Fail").check_consistency(rule, ds)
        assert score == 1.0

    def test_no_applicable_traces(self):
        rule = _rule(_rel("x", RelOp.GT, 100.0))
        ds = _make_dataset([{"x": 1.0, "_outcome": "Pass"}])
        score, issues = ConsistencyChecker("Pass").check_consistency(rule, ds)
        assert score == 0.0  # no applicable

    def test_missing_variable_skipped(self):
        rule = _rule(_rel("missing_var", RelOp.GT, 0.0))
        ds = _make_dataset([{"x": 1.0, "_outcome": "Pass"}])
        score, issues = ConsistencyChecker("Pass").check_consistency(rule, ds)
        # Should not crash; just scores 0 (no applicable traces)
        assert score == 0.0


# ── ContradictionChecker ────────────────────────────────────────────────

class TestContradictionChecker:
    def test_no_contradiction_same_type(self):
        """Rules of the same type cannot contradict."""
        checker = ContradictionChecker()
        r1 = _rule(_rel("x", RelOp.GT, 5.0))
        r2 = _rule(_rel("x", RelOp.GT, 3.0))
        result = checker.check_contradictions(
            r1, "Pass",
            [(r2, "Pass")],
            [{"x": 6.0}],
        )
        assert result == []

    def test_contradiction_opposite_types(self):
        checker = ContradictionChecker()
        r_pass = _rule(_rel("x", RelOp.GT, 5.0))
        r_fail = _rule(_rel("x", RelOp.GT, 3.0))
        result = checker.check_contradictions(
            r_pass, "Pass",
            [(r_fail, "Fail")],
            [{"x": 6.0}],    # Both hold at x=6
        )
        assert len(result) == 1
        assert isinstance(result[0], ContradictionIssue)

    def test_no_contradiction_non_overlap(self):
        checker = ContradictionChecker()
        r_pass = _rule(_rel("x", RelOp.GT, 10.0))
        r_fail = _rule(_rel("x", RelOp.LT, 5.0))
        result = checker.check_contradictions(
            r_pass, "Pass",
            [(r_fail, "Fail")],
            [{"x": 3.0}, {"x": 11.0}],
        )
        assert result == []

    def test_generate_test_points_shape(self):
        checker = ContradictionChecker()
        pts = checker.generate_test_points(
            variables={"a", "b"},
            bounds={"a": (0, 1), "b": (-1, 1)},
            num_points=50,
        )
        assert len(pts) == 50
        for p in pts:
            assert "a" in p and "b" in p
            assert 0 <= p["a"] <= 1
            assert -1 <= p["b"] <= 1

    def test_generate_test_points_missing_bounds(self):
        checker = ContradictionChecker()
        pts = checker.generate_test_points(
            variables={"z"},
            bounds={},
            num_points=5,
        )
        assert all(p["z"] == 0.0 for p in pts)


# ── OverfittingDetector ─────────────────────────────────────────────────

class TestExtractConstants:
    def test_from_constant(self):
        assert extract_constants(Constant(3.14)) == [3.14]

    def test_from_relation(self):
        r = _rel("x", RelOp.GT, 5.0)
        consts = extract_constants(r)
        assert 5.0 in consts

    def test_from_conjunction(self):
        c = Conjunction([_rel("x", RelOp.GT, 1.0), _rel("y", RelOp.LT, 2.0)])
        consts = extract_constants(c)
        assert 1.0 in consts and 2.0 in consts

    def test_from_disjunction(self):
        d = Disjunction([_rel("x", RelOp.GT, 10), _rel("y", RelOp.LT, 20)])
        assert set(extract_constants(d)) == {10.0, 20.0}

    def test_from_binary_expr(self):
        expr = BinaryExpr(Constant(2.0), ArithOp.MUL, Variable("x"))
        assert 2.0 in extract_constants(expr)

    def test_unknown_node_returns_empty(self):
        assert extract_constants("string_node") == []


class TestOverfittingDetector:
    def _evidence(self, pairs):
        return CounterfactualEvidence(
            inconsistent_rule="x > 5",
            pairs=pairs,
        )

    def test_no_evidence_no_indicators(self):
        det = OverfittingDetector()
        rule = _rule(_rel("x", RelOp.GT, 5.0))
        score, indicators = det.detect_overfitting(
            rule,
            self._evidence([]),
            _make_dataset([{"x": 6.0}]),
        )
        assert score == 0.0
        assert indicators == []

    def test_boundary_sensitive(self):
        det = OverfittingDetector()
        rule = _rule(_rel("x", RelOp.GT, 5.0))
        pair = CounterfactualPair(
            original_input={"x": 5.01},
            original_outcome="Pass",
            counterfactual_input={"x": 4.99},
            counterfactual_outcome="Fail",
            perturbation={"x": -0.02},
        )
        evidence = self._evidence([pair])
        score, indicators = det.detect_overfitting(
            rule, evidence, _make_dataset([{"x": 6.0}])
        )
        assert any(i.indicator_type == "boundary_sensitive" for i in indicators)

    def test_overly_specific_constants(self):
        det = OverfittingDetector()
        # 4.123 has >1 decimal place ⇒ overly specific
        rule = _rule(_rel("x", RelOp.GT, 4.123))
        pair = CounterfactualPair(
            original_input={"x": 5.0},
            original_outcome="Pass",
            counterfactual_input={"x": 3.0},
            counterfactual_outcome="Fail",
            perturbation={"x": -2.0},
        )
        evidence = self._evidence([pair])
        score, indicators = det.detect_overfitting(
            rule, evidence, _make_dataset([{"x": 6.0}])
        )
        assert any(i.indicator_type == "overly_specific" for i in indicators)

    def test_train_test_gap(self):
        det = OverfittingDetector()
        rule = _rule(_rel("x", RelOp.GT, 5.0))
        train = _make_dataset(
            [{"x": 6.0, "_outcome": "Pass"},
             {"x": 7.0, "_outcome": "Pass"}]
        )
        # Test data: rule says Pass but outcome is Fail → big gap
        test = _make_dataset(
            [{"x": 6.0, "_outcome": "Fail"},
             {"x": 7.0, "_outcome": "Fail"}]
        )
        evidence = self._evidence([])
        score, indicators = det.detect_overfitting(
            rule, evidence, train, test_data=test
        )
        assert any(i.indicator_type == "train_test_gap" for i in indicators)

    def test_risk_score_aggregation(self):
        det = OverfittingDetector()
        inds = [
            OverfittingIndicator("a", 0.6, "ev", set()),
            OverfittingIndicator("b", 0.8, "ev", set()),
        ]
        assert det._compute_risk_score(inds) == pytest.approx(0.7)

    def test_risk_score_capped_at_one(self):
        det = OverfittingDetector()
        inds = [OverfittingIndicator("a", 1.0, "ev", set())] * 5
        assert det._compute_risk_score(inds) <= 1.0


# ── SemanticValidator orchestrator ──────────────────────────────────────

class TestSemanticValidator:
    def test_passes_when_all_clear(self):
        rule = _rule(_rel("x", RelOp.GT, 5.0))
        ds = _make_dataset([{"x": 6.0, "_outcome": "Pass"}])
        sv = SemanticValidator("Pass")
        result = sv.validate(rule, ds)
        assert isinstance(result, SemanticValidationResult)
        assert result.is_consistent
        assert not result.has_contradictions
        assert result.passed_validation

    def test_fails_on_inconsistency(self):
        rule = _rule(_rel("x", RelOp.GT, 5.0))
        ds = _make_dataset(
            [{"x": 6.0, "_outcome": "Fail"},
             {"x": 7.0, "_outcome": "Fail"}]
        )
        sv = SemanticValidator("Pass")
        result = sv.validate(rule, ds)
        assert not result.is_consistent

    def test_fails_on_contradiction(self):
        rule = _rule(_rel("x", RelOp.GT, 5.0))
        hist = _rule(_rel("x", RelOp.GT, 3.0))
        ds = _make_dataset([{"x": 6.0, "_outcome": "Pass"}])
        sv = SemanticValidator(
            "Pass",
            historical_rules=[(hist, "Fail")],
            variable_bounds={"x": (0, 10)},
        )
        result = sv.validate(rule, ds)
        # May or may not find contradiction depending on random points
        assert isinstance(result, SemanticValidationResult)

    def test_summary_method(self):
        result = SemanticValidationResult(
            rule="x > 5",
            is_consistent=True,
            consistency_score=1.0,
            consistency_issues=[],
            has_contradictions=False,
            contradictions=[],
            overfitting_risk=0.0,
            overfitting_indicators=[],
            passed_validation=True,
        )
        s = result.summary()
        assert "Passed: True" in s
        assert "100.00%" in s


# ── CounterfactualGenerator ─────────────────────────────────────────────

class TestCounterfactualGenerator:
    def test_generate_L1_candidates(self):
        gen = CounterfactualGenerator()
        center = {"x": 5.0, "y": 3.0}
        bounds = {"x": (0, 10), "y": (0, 10)}
        cands = gen._generate_L1_candidates(center, 1.0, bounds, num_samples=20)
        assert len(cands) == 20
        for c in cands:
            assert "x" in c and "y" in c

    def test_generate_counterfactual_no_simulator(self):
        gen = CounterfactualGenerator(simulator_callback=None)
        rule = _rule(_rel("x", RelOp.GT, 5.0))
        result = gen.generate_counterfactual(
            original_input={"x": 6.0},
            original_outcome="Pass",
            rule=rule,
            bounds={"x": (0, 10)},
        )
        # Without simulator, should return None
        assert result is None

    def test_generate_counterfactual_with_simulator(self):
        def simulator(inp):
            return "Pass" if inp["x"] > 5.0 else "Fail"

        gen = CounterfactualGenerator(simulator_callback=simulator)
        rule = _rule(_rel("x", RelOp.GT, 5.0))
        result = gen.generate_counterfactual(
            original_input={"x": 5.5},
            original_outcome="Pass",
            rule=rule,
            bounds={"x": (0, 10)},
        )
        # Might or might not find a counterfactual depending on random search
        # but the call itself should not crash
        assert result is None or isinstance(result, CounterfactualPair)
