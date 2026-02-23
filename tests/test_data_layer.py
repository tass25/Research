"""Tests for data layer (simulation_trace, counterfactual_evidence, semantic_result, minimality_result)."""

import pytest
from data.simulation_trace import SimulationTrace, SimulationDataset
from data.counterfactual_evidence import CounterfactualPair, CounterfactualEvidence
from data.semantic_result import (
    ConsistencyIssue, ContradictionIssue,
    OverfittingIndicator, SemanticValidationResult,
)
from data.minimality_result import RelationChange, MinimalityResult


# ── SimulationTrace ────────────────────────────────────────────────────

class TestSimulationTrace:
    def test_creation(self):
        t = SimulationTrace(
            input_vector={"x": 1.0, "y": 2.0},
            observed_outcome="Pass",
        )
        assert t.input_vector["x"] == 1.0
        assert t.observed_outcome == "Pass"
        assert t.timestamp is None
        assert t.metadata == {}

    def test_with_metadata(self):
        t = SimulationTrace(
            input_vector={"x": 1.0},
            observed_outcome="Fail",
            timestamp=100.0,
            metadata={"case_id": 42},
        )
        assert t.timestamp == 100.0
        assert t.metadata["case_id"] == 42


class TestSimulationDataset:
    @pytest.fixture
    def dataset(self):
        traces = [
            SimulationTrace({"x": 1.0}, "Pass"),
            SimulationTrace({"x": 2.0}, "Pass"),
            SimulationTrace({"x": 3.0}, "Fail"),
            SimulationTrace({"x": 4.0}, "Fail"),
            SimulationTrace({"y": 5.0}, "Pass"),
        ]
        return SimulationDataset(traces=traces)

    def test_filter_by_outcome_pass(self, dataset):
        passes = dataset.filter_by_outcome("Pass")
        assert len(passes) == 3

    def test_filter_by_outcome_fail(self, dataset):
        fails = dataset.filter_by_outcome("Fail")
        assert len(fails) == 2

    def test_get_all_variables(self, dataset):
        vs = dataset.get_all_variables()
        assert vs == {"x", "y"}

    def test_split_train_test(self, dataset):
        train, test = dataset.split_train_test(test_ratio=0.4)
        assert len(train.traces) == 3
        assert len(test.traces) == 2

    def test_empty_dataset(self):
        ds = SimulationDataset(traces=[])
        assert ds.filter_by_outcome("Pass") == []
        assert ds.get_all_variables() == set()


# ── CounterfactualPair ──────────────────────────────────────────────────

class TestCounterfactualPair:
    def test_perturbation_magnitude(self):
        pair = CounterfactualPair(
            original_input={"x": 1.0, "y": 2.0},
            original_outcome="Fail",
            counterfactual_input={"x": 1.5, "y": 2.0},
            counterfactual_outcome="Pass",
            perturbation={"x": 0.5, "y": 0.0},
        )
        assert pair.perturbation_magnitude() == pytest.approx(0.5)

    def test_get_changed_variables(self):
        pair = CounterfactualPair(
            original_input={"x": 1.0, "y": 2.0, "z": 3.0},
            original_outcome="Fail",
            counterfactual_input={"x": 1.5, "y": 2.0, "z": 4.0},
            counterfactual_outcome="Pass",
            perturbation={"x": 0.5, "y": 0.0, "z": 1.0},
        )
        changed = pair.get_changed_variables()
        assert changed == {"x", "z"}


class TestCounterfactualEvidence:
    def test_decision_boundary_features(self):
        pairs = [
            CounterfactualPair(
                {"x": 1.0}, "Fail", {"x": 1.5}, "Pass", {"x": 0.5}
            ),
            CounterfactualPair(
                {"y": 2.0, "z": 3.0}, "Fail",
                {"y": 2.5, "z": 3.0}, "Pass",
                {"y": 0.5, "z": 0.0},
            ),
        ]
        ev = CounterfactualEvidence(inconsistent_rule="x > 1", pairs=pairs)
        boundary_feats = ev.get_decision_boundary_features()
        assert boundary_feats == {"x", "y"}

    def test_empty_evidence(self):
        ev = CounterfactualEvidence(inconsistent_rule="x > 1", pairs=[])
        assert ev.get_decision_boundary_features() == set()


# ── Semantic result data classes ───────────────────────────────────────

class TestSemanticResult:
    def test_consistency_issue(self):
        trace = SimulationTrace({"x": 1.0}, "Pass")
        issue = ConsistencyIssue(trace=trace, rule_verdict="Fail", observed_outcome="Pass")
        assert issue.rule_verdict == "Fail"
        assert issue.observed_outcome == "Pass"

    def test_contradiction_issue(self):
        issue = ContradictionIssue(
            current_rule="x > 5",
            historical_rule="x < 3",
            conflicting_input={"x": 4.0},
            explanation="Pass and Fail both hold",
        )
        assert issue.conflicting_input == {"x": 4.0}

    def test_overfitting_indicator(self):
        ind = OverfittingIndicator(
            indicator_type="boundary_sensitive",
            severity=0.8,
            evidence="small perturbation",
            affected_variables={"x", "y"},
        )
        assert ind.severity == 0.8

    def test_validation_result_summary(self):
        result = SemanticValidationResult(
            rule="x > 5",
            is_consistent=True,
            consistency_score=0.98,
            consistency_issues=[],
            has_contradictions=False,
            contradictions=[],
            overfitting_risk=0.1,
            overfitting_indicators=[],
            passed_validation=True,
        )
        summary = result.summary()
        assert "x > 5" in summary
        assert "True" in summary
        assert "98.00%" in summary


# ── MinimalityResult ───────────────────────────────────────────────────

class TestMinimalityResult:
    def test_relation_change_str(self):
        change = RelationChange(
            variable="dist_front",
            operator="<",
            original_constant=5.0,
            refined_constant=4.1,
            delta=-0.9,
            change_type="tightening",
            magnitude=0.18,
            is_justified=True,
            justification="Supported by cluster boundary",
        )
        s = str(change)
        assert "dist_front" in s
        assert "5.0" in s
        assert "4.1" in s

    def test_minimality_result_summary(self):
        change = RelationChange(
            "x", "<", 5.0, 4.0, -1.0, "tightening", 0.2, True, "Justified"
        )
        result = MinimalityResult(
            original_rule="x < 5",
            refined_rule="x < 4",
            overall_score=0.85,
            relation_changes=[change],
            unjustified_tightenings=[],
            unjustified_loosenings=[],
            total_changes=1,
            justified_changes=1,
            passed_minimality=True,
        )
        summary = result.summary()
        assert "PASS" in summary
        assert "85.00%" in summary
        assert "x < 5" in summary
