"""
Validation report generator for Group C.

Produces the final evaluation report with metrics, selected rules,
inconsistency examples, and counterfactual hints.
"""

import csv
from typing import List, Optional
from pathlib import Path
from dataclasses import dataclass

from rule_validation.rule_evaluator import RuleEvaluation
from rule_validation.rule_selector import SelectedRule
from rule_validation.counterfactual_hints import InconsistentExample


def export_evaluations_csv(
    evaluations: List[RuleEvaluation],
    output_path: str,
) -> str:
    """Export all rule evaluations to CSV.

    Args:
        evaluations: List of RuleEvaluation.
        output_path: Path to write CSV.

    Returns:
        Path to written file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "rule_id", "rule_type", "rule_text",
        "total_runs", "n_mismatches", "decisiveness",
        "false_positive_rate", "false_negative_rate",
        "true_positives", "true_negatives",
        "false_positives", "false_negatives",
        "accuracy", "grammar_valid", "meets_criteria",
    ]

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for ev in evaluations:
            writer.writerow({
                "rule_id": ev.rule_id,
                "rule_type": ev.rule_type,
                "rule_text": ev.rule_text,
                "total_runs": ev.total_runs,
                "n_mismatches": ev.n_mismatches,
                "decisiveness": f"{ev.decisiveness:.4f}",
                "false_positive_rate": f"{ev.false_positive_rate:.4f}",
                "false_negative_rate": f"{ev.false_negative_rate:.4f}",
                "true_positives": ev.true_positives,
                "true_negatives": ev.true_negatives,
                "false_positives": ev.false_positives,
                "false_negatives": ev.false_negatives,
                "accuracy": f"{ev.accuracy:.4f}",
                "grammar_valid": ev.grammar_valid,
                "meets_criteria": ev.meets_selection_criteria,
            })

    return str(path)


def export_selected_rules_csv(
    selected: List[SelectedRule],
    output_path: str,
) -> str:
    """Export selected inconsistent rules to CSV.

    Args:
        selected: List of SelectedRule from the selector.
        output_path: Path to write CSV.

    Returns:
        Path to written file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "rank", "rule_id", "rule_type", "rule_text",
        "selection_score", "decisiveness",
        "false_positive_rate", "false_negative_rate",
        "n_mismatches", "total_runs",
        "selection_reason",
    ]

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for sr in selected:
            ev = sr.evaluation
            writer.writerow({
                "rank": sr.rank,
                "rule_id": ev.rule_id,
                "rule_type": ev.rule_type,
                "rule_text": ev.rule_text,
                "selection_score": f"{sr.selection_score:.4f}",
                "decisiveness": f"{ev.decisiveness:.4f}",
                "false_positive_rate": f"{ev.false_positive_rate:.4f}",
                "false_negative_rate": f"{ev.false_negative_rate:.4f}",
                "n_mismatches": ev.n_mismatches,
                "total_runs": ev.total_runs,
                "selection_reason": sr.selection_reason,
            })

    return str(path)


def export_inconsistency_examples_csv(
    examples: List[InconsistentExample],
    output_path: str,
    feature_names: List[str],
) -> str:
    """Export inconsistent examples with counterfactual hints to CSV.

    Args:
        examples: List of InconsistentExample.
        output_path: Path to write CSV.
        feature_names: Feature column names.

    Returns:
        Path to written file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = (
        ["case_id", "observed_label", "rule_verdict", "rule_type", "rule_text"]
        + feature_names
        + ["cf_variable", "cf_original_value", "cf_perturbed_value",
           "cf_l1_distance", "cf_flips_verdict"]
    )

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for ex in examples:
            base_row = {
                "case_id": ex.case_id,
                "observed_label": ex.observed_label,
                "rule_verdict": ex.rule_verdict,
                "rule_type": ex.rule_type,
                "rule_text": ex.rule_text,
            }
            for feat in feature_names:
                base_row[feat] = f"{ex.input_features.get(feat, 0.0):.6f}"

            if ex.counterfactuals:
                for cf in ex.counterfactuals:
                    row = dict(base_row)
                    row["cf_variable"] = cf.changed_variable
                    row["cf_original_value"] = f"{cf.original_value:.6f}"
                    row["cf_perturbed_value"] = f"{cf.perturbed_value:.6f}"
                    row["cf_l1_distance"] = f"{cf.l1_distance:.6f}"
                    row["cf_flips_verdict"] = cf.rule_verdict_before != cf.rule_verdict_after
                    writer.writerow(row)
            else:
                row = dict(base_row)
                row["cf_variable"] = ""
                row["cf_original_value"] = ""
                row["cf_perturbed_value"] = ""
                row["cf_l1_distance"] = ""
                row["cf_flips_verdict"] = ""
                writer.writerow(row)

    return str(path)


def generate_selection_report(
    evaluations: List[RuleEvaluation],
    selected: List[SelectedRule],
    all_examples: List[InconsistentExample],
    system_info: str,
) -> str:
    """Generate the Group C selection and validation report.

    Returns:
        Multi-line string report.
    """
    lines = [
        "=" * 70,
        "RULE SELECTION & VALIDATION REPORT (Group C)",
        "=" * 70,
        "",
        f"System: {system_info}",
        f"Total rules evaluated: {len(evaluations)}",
        "",
    ]

    # Summary statistics
    pass_evals = [e for e in evaluations if e.rule_type == "pass"]
    fail_evals = [e for e in evaluations if e.rule_type == "fail"]

    lines.append(f"Pass rules evaluated: {len(pass_evals)}")
    lines.append(f"Fail rules evaluated: {len(fail_evals)}")

    meets = [e for e in evaluations if e.meets_selection_criteria]
    lines.append(f"Rules meeting strict criteria (FP>=20%, FN<=5%): {len(meets)}")

    # Selected rules
    lines.append(f"\n{'─' * 70}")
    lines.append(f"TOP-{len(selected)} SELECTED INCONSISTENT RULES")
    lines.append(f"{'─' * 70}")

    for sr in selected:
        ev = sr.evaluation
        lines.append(f"\n  Rank {sr.rank}: [{ev.rule_id}] ({ev.rule_type} rule)")
        lines.append(f"  Score: {sr.selection_score:.4f}")
        lines.append(f"  Rule: {ev.rule_text}")
        lines.append(
            f"  Decisiveness: {ev.decisiveness:.4f} | "
            f"FPR: {ev.false_positive_rate:.2%} | "
            f"FNR: {ev.false_negative_rate:.2%}"
        )
        lines.append(
            f"  Mismatches: {ev.n_mismatches}/{ev.total_runs} | "
            f"TP={ev.true_positives} TN={ev.true_negatives} "
            f"FP={ev.false_positives} FN={ev.false_negatives}"
        )
        lines.append(f"  Reason: {sr.selection_reason}")

    # Inconsistency examples summary
    lines.append(f"\n{'─' * 70}")
    lines.append("INCONSISTENCY EXAMPLES SUMMARY")
    lines.append(f"{'─' * 70}")
    lines.append(f"Total inconsistent examples collected: {len(all_examples)}")

    cf_with_flip = sum(
        1 for ex in all_examples
        for cf in ex.counterfactuals
        if cf.rule_verdict_before != cf.rule_verdict_after
    )
    lines.append(f"Counterfactuals that flip verdict: {cf_with_flip}")

    if all_examples:
        avg_l1 = sum(
            cf.l1_distance
            for ex in all_examples
            for cf in ex.counterfactuals
        )
        total_cfs = sum(len(ex.counterfactuals) for ex in all_examples)
        if total_cfs > 0:
            lines.append(f"Average L1 distance of perturbations: {avg_l1 / total_cfs:.6f}")

    lines.append(f"\n{'=' * 70}")
    return "\n".join(lines)
