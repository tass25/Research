"""Tests for rule_inference package: tree_extractor, forest_extractor, rule_export, grammar_checker."""

import pytest
import csv
from pathlib import Path

from cbf_data.loader import load_dataset, SimulationDataset, SimulationRun, STATIC_FEATURES
from rule_inference.tree_extractor import (
    CandidateRule,
    _threshold_to_str,
    _path_to_rule_text,
    _merge_pass_rules_to_dnf,
    _merge_fail_rules_to_dnf,
    _extract_paths,
    extract_rules_from_tree,
    extract_dnf_rules,
    sweep_depths,
)
from rule_inference.forest_extractor import (
    extract_rules_from_forest,
    extract_high_confidence_rules,
)
from rule_inference.rule_export import export_candidates_to_csv, generate_inference_report
from rule_inference.grammar_checker import check_grammar_compliance, validate_dnf_structure


# ── threshold formatting ─────────────────────────────────────────────────

class TestThresholdToStr:
    def test_integer_value(self):
        assert _threshold_to_str(5.0) == "5"

    def test_decimal_value(self):
        result = _threshold_to_str(3.14159)
        assert result == "3.1416"

    def test_trailing_zeros(self):
        assert _threshold_to_str(2.1000) == "2.1"

    def test_negative(self):
        assert _threshold_to_str(-1.0) == "-1"


# ── path → rule text ─────────────────────────────────────────────────────

class TestPathToRuleText:
    def test_single_condition(self):
        text = _path_to_rule_text([("speed", ">", 5.0)])
        assert text == "speed > 5"

    def test_conjunction(self):
        text = _path_to_rule_text([("x", "<=", 3.0), ("y", ">", 1.0)])
        assert "AND" in text
        assert "x <= 3" in text
        assert "y > 1" in text


class TestMergeDNF:
    def test_single_pass_path(self):
        paths = [{"conditions": [("x", ">", 5.0)]}]
        dnf = _merge_pass_rules_to_dnf(paths)
        assert dnf == "x > 5"

    def test_multiple_pass_paths(self):
        paths = [
            {"conditions": [("x", ">", 5.0), ("y", "<=", 2.0)]},
            {"conditions": [("z", ">", 1.0)]},
        ]
        dnf = _merge_pass_rules_to_dnf(paths)
        assert "OR" in dnf
        assert "z > 1" in dnf

    def test_empty_paths(self):
        assert _merge_pass_rules_to_dnf([]) == ""

    def test_merge_fail_empty(self):
        assert _merge_fail_rules_to_dnf([]) == ""


# ── full tree extraction on real data ────────────────────────────────────

@pytest.fixture(scope="module")
def static_dataset():
    """Load a real dataset for tree extraction tests."""
    return load_dataset("unicycle_static_obstacle", "robust_evolved", "legacy")


class TestExtractRulesFromTree:
    def test_returns_candidates_and_model(self, static_dataset):
        candidates, clf = extract_rules_from_tree(
            static_dataset, max_depth=3, random_state=42
        )
        assert len(candidates) > 0
        assert all(isinstance(c, CandidateRule) for c in candidates)

    def test_candidate_fields(self, static_dataset):
        candidates, _ = extract_rules_from_tree(
            static_dataset, max_depth=2, random_state=42
        )
        c = candidates[0]
        assert c.rule_id.startswith("DT")
        assert c.rule_text  # non-empty
        assert c.rule_type in ("pass", "fail")
        assert 0 <= c.train_accuracy <= 1
        assert 0 <= c.val_accuracy <= 1
        assert c.source_model == "decision_tree"

    def test_extract_paths_from_fitted_tree(self, static_dataset):
        _, clf = extract_rules_from_tree(
            static_dataset, max_depth=2, random_state=42
        )
        paths = _extract_paths(clf, static_dataset.feature_names)
        assert len(paths) > 0
        for p in paths:
            assert "predicted_class" in p
            assert p["predicted_class"] in (0, 1)


class TestExtractDNFRules:
    def test_produces_dnf_text(self, static_dataset):
        candidates, clf = extract_dnf_rules(static_dataset, max_depth=3, random_state=42)
        assert isinstance(candidates, list)
        assert len(candidates) > 0
        for c in candidates:
            assert c.source_model == "decision_tree_dnf"
            assert c.rule_text  # non-empty


class TestSweepDepths:
    def test_returns_multiple_depths(self, static_dataset):
        all_candidates = sweep_depths(static_dataset, depths=[2, 3])
        assert len(all_candidates) > 0
        ids = {c.rule_id for c in all_candidates}
        assert any("_d2_" in rid for rid in ids)
        assert any("_d3_" in rid for rid in ids)


# ── forest extractor ─────────────────────────────────────────────────────

class TestForestExtractor:
    def test_extract_from_forest(self, static_dataset):
        candidates, clf = extract_rules_from_forest(
            static_dataset, n_estimators=10, max_depth=3, top_k_trees=2, random_state=42
        )
        assert len(candidates) > 0
        valid_models = {"random_forest", "random_forest_dnf"}
        assert all(c.source_model in valid_models for c in candidates)

    def test_high_confidence_rules(self, static_dataset):
        high_conf = extract_high_confidence_rules(
            static_dataset, n_estimators=10, max_depth=3, min_confidence=0.5, min_support=1
        )
        for c in high_conf:
            assert c.confidence >= 0.5


# ── rule export ──────────────────────────────────────────────────────────

class TestRuleExport:
    def test_export_csv(self, static_dataset, tmp_path):
        candidates, _ = extract_rules_from_tree(
            static_dataset, max_depth=2, random_state=42
        )
        out = tmp_path / "rules.csv"
        result_path = export_candidates_to_csv(
            candidates, str(out), STATIC_FEATURES
        )
        assert Path(result_path).exists()

        with open(result_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == len(candidates)
        assert "rule_text" in rows[0]
        assert "grammar_valid" in rows[0]

    def test_generate_report(self, static_dataset):
        candidates, _ = extract_rules_from_tree(
            static_dataset, max_depth=2, random_state=42
        )
        report = generate_inference_report(
            candidates, "test_dataset", STATIC_FEATURES
        )
        assert "OPERATIONAL RULE INFERENCE REPORT" in report
        assert "decision_tree" in report


# ── grammar_checker delegation ───────────────────────────────────────────

class TestGrammarCheckerDelegation:
    def test_check_grammar(self):
        r = check_grammar_compliance("initial_speed > 5", STATIC_FEATURES)
        assert r.is_valid is True

    def test_validate_dnf(self):
        ok, msg = validate_dnf_structure("initial_speed > 5")
        assert ok is True
