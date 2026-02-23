"""Tests for rule_validation package: evaluator, selector, counterfactual_hints, validation_report."""

import pytest
import csv
from pathlib import Path

from cbf_data.loader import SimulationDataset, SimulationRun, STATIC_FEATURES, load_dataset
from rule_inference.tree_extractor import CandidateRule
from rule_validation.rule_evaluator import (
    RuleEvaluation,
    _parse_rule_predicate,
    _evaluate_predicate,
    evaluate_rule_text,
    evaluate_rule_on_dataset,
    evaluate_all_rules,
)
from rule_validation.rule_selector import (
    SelectionCriteria,
    SelectedRule,
    compute_selection_score,
    select_inconsistent_rules,
    select_with_relaxed_criteria,
)
from rule_validation.counterfactual_hints import (
    CounterfactualCandidate,
    InconsistentExample,
    compute_minimal_perturbation,
    _extract_predicates_from_rule,
    find_inconsistent_examples,
)
from rule_validation.validation_report import (
    export_evaluations_csv,
    export_selected_rules_csv,
    export_inconsistency_examples_csv,
    generate_selection_report,
)


# ── _parse_rule_predicate ────────────────────────────────────────────────

class TestParseRulePredicate:
    def test_le(self):
        p = _parse_rule_predicate("initial_speed <= 1.5")
        assert p["variable"] == "initial_speed"
        assert p["operator"] == "<="
        assert p["threshold"] == pytest.approx(1.5)

    def test_gt(self):
        p = _parse_rule_predicate("obstacle_radius > 0.8")
        assert p["operator"] == ">"

    def test_negative_threshold(self):
        p = _parse_rule_predicate("heading_error > -1.5")
        assert p["threshold"] == pytest.approx(-1.5)

    def test_invalid(self):
        assert _parse_rule_predicate("not a predicate") is None

    def test_ne(self):
        p = _parse_rule_predicate("x != 0")
        assert p["operator"] == "!="


# ── _evaluate_predicate ─────────────────────────────────────────────────

class TestEvaluatePredicate:
    @pytest.mark.parametrize("op,val,thresh,expected", [
        ("<", 1.0, 2.0, True),
        ("<", 2.0, 2.0, False),
        ("<=", 2.0, 2.0, True),
        (">", 3.0, 2.0, True),
        (">", 2.0, 2.0, False),
        (">=", 2.0, 2.0, True),
        ("=", 2.0, 2.0, True),
        ("!=", 2.0, 2.0, False),
        ("!=", 3.0, 2.0, True),
    ])
    def test_operators(self, op, val, thresh, expected):
        pred = {"variable": "x", "operator": op, "threshold": thresh}
        assert _evaluate_predicate(pred, {"x": val}) is expected

    def test_missing_variable(self):
        pred = {"variable": "missing", "operator": ">", "threshold": 0}
        assert _evaluate_predicate(pred, {"x": 1.0}) is False


# ── evaluate_rule_text ───────────────────────────────────────────────────

class TestEvaluateRuleText:
    def test_single_predicate(self):
        assert evaluate_rule_text("x > 5", {"x": 6.0}) is True
        assert evaluate_rule_text("x > 5", {"x": 4.0}) is False

    def test_conjunction(self):
        assert evaluate_rule_text("x > 1 AND y <= 3", {"x": 2, "y": 2}) is True
        assert evaluate_rule_text("x > 1 AND y <= 3", {"x": 0, "y": 2}) is False

    def test_disjunction(self):
        assert evaluate_rule_text("x > 10 OR y < 0", {"x": 11, "y": 5}) is True
        assert evaluate_rule_text("x > 10 OR y < 0", {"x": 5, "y": 5}) is False

    def test_dnf(self):
        rule = "(x > 5 AND y <= 3) OR (z > 10)"
        assert evaluate_rule_text(rule, {"x": 6, "y": 2, "z": 0}) is True
        assert evaluate_rule_text(rule, {"x": 1, "y": 2, "z": 11}) is True
        assert evaluate_rule_text(rule, {"x": 1, "y": 2, "z": 1}) is False

    def test_empty_rule(self):
        assert evaluate_rule_text("", {"x": 1}) is False


# ── evaluate_rule_on_dataset ────────────────────────────────────────────

class TestEvaluateRuleOnDataset:
    def _candidate(self, text, rtype="fail"):
        return CandidateRule(
            rule_id="test", rule_text=text, rule_type=rtype,
            train_accuracy=0.9, val_accuracy=0.9,
            train_f1=0.9, val_f1=0.9,
            complexity=1, support=10, confidence=1.0,
            source_model="test",
        )

    def _dataset(self, rows):
        runs = [
            SimulationRun(
                case_id=i, input_features=r["f"],
                label=r["l"], min_h=0, controller_error=False, case_runtime_s=0,
            )
            for i, r in enumerate(rows)
        ]
        return SimulationDataset("s", "c", "d", runs, list(rows[0]["f"].keys()))

    def test_perfect_fail_rule(self):
        # Rule fires on Fail outcomes only
        ds = self._dataset([
            {"f": {"x": 6.0}, "l": "Fail"},
            {"f": {"x": 3.0}, "l": "Pass"},
        ])
        cand = self._candidate("x > 5", rtype="fail")
        ev = evaluate_rule_on_dataset(cand, ds)
        assert isinstance(ev, RuleEvaluation)
        assert ev.true_positives == 1
        assert ev.true_negatives == 1
        assert ev.false_positives == 0
        assert ev.false_negatives == 0

    def test_accuracy_property(self):
        ev = RuleEvaluation(
            "r", "t", "pass", 100, 10, 0.9,
            0.1, 0.05, 80, 10, 5, 5,
        )
        assert ev.accuracy == pytest.approx(0.9)

    def test_meets_criteria(self):
        ev = RuleEvaluation(
            "r", "t", "fail", 100, 20, 0.8,
            0.25, 0.03, 70, 5, 20, 5,
            grammar_valid=True,
        )
        assert ev.meets_selection_criteria is True

    def test_does_not_meet_low_fp(self):
        ev = RuleEvaluation(
            "r", "t", "fail", 100, 5, 0.95,
            0.05, 0.01, 90, 5, 5, 0,
            grammar_valid=True,
        )
        assert ev.meets_selection_criteria is False

    def test_pass_rule_evaluation(self):
        """Cover the pass-rule branch of evaluate_rule_on_dataset."""
        ds = self._dataset([
            {"f": {"x": 6.0}, "l": "Pass"},
            {"f": {"x": 3.0}, "l": "Fail"},
        ])
        cand = self._candidate("x > 5", rtype="pass")
        ev = evaluate_rule_on_dataset(cand, ds)
        assert ev.true_positives == 1   # x=6 → fires, Pass → TP
        assert ev.true_negatives == 1   # x=3 → doesn't fire, Fail → TN
        assert ev.false_positives == 0
        assert ev.false_negatives == 0

    def test_evaluate_all_rules(self):
        ds = self._dataset([
            {"f": {"x": 6.0}, "l": "Fail"},
            {"f": {"x": 3.0}, "l": "Pass"},
        ])
        c1 = self._candidate("x > 5", rtype="fail")
        c2 = self._candidate("x <= 5", rtype="pass")
        evs = evaluate_all_rules([c1, c2], ds, ["x"])
        assert len(evs) == 2
        assert all(isinstance(e, RuleEvaluation) for e in evs)


# ── rule_selector ────────────────────────────────────────────────────────

class TestRuleSelector:
    def _ev(self, rid, fp, fn, mismatches=5, grammar=True):
        return RuleEvaluation(
            rule_id=rid, rule_text="x > 5", rule_type="fail",
            total_runs=100, n_mismatches=mismatches, decisiveness=1 - mismatches/100,
            false_positive_rate=fp, false_negative_rate=fn,
            true_positives=50, true_negatives=40,
            false_positives=int(fp * 100), false_negatives=int(fn * 100),
            grammar_valid=grammar,
        )

    def test_compute_score(self):
        ev = self._ev("r1", fp=0.3, fn=0.02, mismatches=10)
        s = compute_selection_score(ev)
        assert 0 < s <= 1

    def test_select_inconsistent_basic(self):
        evs = [
            self._ev("r1", fp=0.30, fn=0.02, mismatches=10),
            self._ev("r2", fp=0.10, fn=0.01, mismatches=2),  # below FP threshold
            self._ev("r3", fp=0.25, fn=0.04, mismatches=8),
        ]
        selected = select_inconsistent_rules(evs, top_k=5)
        ids = {s.evaluation.rule_id for s in selected}
        assert "r1" in ids
        assert "r3" in ids
        assert "r2" not in ids  # FP < 0.20

    def test_skips_grammar_invalid(self):
        evs = [self._ev("bad", fp=0.5, fn=0.0, mismatches=20, grammar=False)]
        selected = select_inconsistent_rules(evs, top_k=5)
        assert len(selected) == 0

    def test_relaxed_criteria(self):
        evs = [self._ev("r1", fp=0.12, fn=0.08, mismatches=5)]
        selected = select_with_relaxed_criteria(evs, top_k=1)
        # Should eventually relax enough to pick it up
        assert len(selected) >= 1


# ── counterfactual_hints ─────────────────────────────────────────────────

class TestExtractPredicates:
    def test_single(self):
        preds = _extract_predicates_from_rule("x > 5")
        assert len(preds) == 1
        assert preds[0]["variable"] == "x"

    def test_conjunction(self):
        preds = _extract_predicates_from_rule("x > 5 AND y <= 3")
        assert len(preds) == 2

    def test_dnf(self):
        preds = _extract_predicates_from_rule("(x > 5 AND y <= 3) OR (z < 1)")
        assert len(preds) == 3


class TestComputeMinimalPerturbation:
    def test_returns_candidates(self):
        features = {"x": 6.0}
        cands = compute_minimal_perturbation(features, "x > 5")
        assert len(cands) >= 1
        assert isinstance(cands[0], CounterfactualCandidate)

    def test_respects_bounds(self):
        features = {"x": 0.5}
        bounds = {"x": (0.0, 10.0)}
        cands = compute_minimal_perturbation(features, "x > 5", feature_bounds=bounds)
        for c in cands:
            assert 0.0 <= c.perturbed_value <= 10.0

    def test_sorted_by_l1(self):
        features = {"x": 3.0, "y": 4.0}
        cands = compute_minimal_perturbation(features, "x > 5 AND y > 5")
        if len(cands) > 1:
            distances = [c.l1_distance for c in cands]
            assert distances == sorted(distances)


class TestFindInconsistentExamples:
    def test_finds_examples(self):
        runs = [
            SimulationRun(0, {"x": 6.0}, "Pass", 0.5, False, 0.1),
            SimulationRun(1, {"x": 3.0}, "Fail", -0.1, False, 0.1),
        ]
        ds = SimulationDataset("s", "c", "d", runs, ["x"])
        examples = find_inconsistent_examples(
            "x > 5", "fail", ds, mismatch_case_ids=[0]
        )
        assert len(examples) == 1
        assert examples[0].case_id == 0


# ── validation_report ───────────────────────────────────────────────────

class TestValidationReport:
    def _ev(self, rid="r1"):
        return RuleEvaluation(
            rule_id=rid, rule_text="x > 5", rule_type="fail",
            total_runs=100, n_mismatches=10, decisiveness=0.9,
            false_positive_rate=0.25, false_negative_rate=0.02,
            true_positives=60, true_negatives=25,
            false_positives=10, false_negatives=5,
            grammar_valid=True,
        )

    def test_export_evaluations_csv(self, tmp_path):
        evs = [self._ev("r1"), self._ev("r2")]
        path = export_evaluations_csv(evs, str(tmp_path / "eval.csv"))
        assert Path(path).exists()
        with open(path) as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        assert "rule_id" in rows[0]

    def test_export_selected_csv(self, tmp_path):
        ev = self._ev()
        sr = SelectedRule(evaluation=ev, rank=1, selection_score=0.8, selection_reason="test")
        path = export_selected_rules_csv([sr], str(tmp_path / "sel.csv"))
        assert Path(path).exists()

    def test_export_inconsistency_csv(self, tmp_path):
        cf = CounterfactualCandidate(
            case_id=0, original_features={"x": 6.0},
            perturbed_features={"x": 4.9},
            changed_variable="x", original_value=6.0,
            perturbed_value=4.9, l1_distance=1.1,
            rule_verdict_before=True, rule_verdict_after=False,
        )
        ex = InconsistentExample(
            case_id=0, input_features={"x": 6.0},
            observed_label="Pass", rule_verdict="Fail",
            rule_text="x > 5", rule_type="fail",
            counterfactuals=[cf],
        )
        path = export_inconsistency_examples_csv(
            [ex], str(tmp_path / "inc.csv"), ["x"]
        )
        assert Path(path).exists()

    def test_generate_report(self):
        evs = [self._ev()]
        sr = SelectedRule(evaluation=evs[0], rank=1, selection_score=0.8, selection_reason="test")
        report = generate_selection_report(evs, [sr], [], "test_system")
        assert "RULE SELECTION" in report
        assert "test_system" in report
