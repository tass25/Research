"""
Rule export utilities for Group B.

Exports candidate rules to CSV table format and generates
summary reports for handover to Group C.
"""

import csv
from typing import List
from pathlib import Path

from rule_inference.tree_extractor import CandidateRule
from rule_inference.grammar_checker import check_grammar_compliance, validate_dnf_structure


def export_candidates_to_csv(
    candidates: List[CandidateRule],
    output_path: str,
    allowed_variables: List[str],
) -> str:
    """Export candidate rules to CSV with full metrics.

    CSV columns match the Group B deliverable spec:
    rule_id, rule_text, rule_type, train_accuracy, val_accuracy,
    train_f1, val_f1, complexity, support, confidence, source_model,
    grammar_valid, dnf_valid

    Args:
        candidates: List of CandidateRule objects.
        output_path: Path to write CSV.
        allowed_variables: Valid variable names for grammar check.

    Returns:
        Path to the written CSV file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "rule_id", "rule_text", "rule_type",
        "train_accuracy", "val_accuracy",
        "train_f1", "val_f1",
        "complexity", "support", "confidence",
        "source_model", "grammar_valid", "dnf_valid",
        "variables_used", "n_predicates",
    ]

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for rule in candidates:
            # Check grammar compliance
            gc = check_grammar_compliance(rule.rule_text, allowed_variables)
            dnf_ok, _ = validate_dnf_structure(rule.rule_text)

            writer.writerow({
                "rule_id": rule.rule_id,
                "rule_text": rule.rule_text,
                "rule_type": rule.rule_type,
                "train_accuracy": f"{rule.train_accuracy:.4f}",
                "val_accuracy": f"{rule.val_accuracy:.4f}",
                "train_f1": f"{rule.train_f1:.4f}",
                "val_f1": f"{rule.val_f1:.4f}",
                "complexity": rule.complexity,
                "support": rule.support,
                "confidence": f"{rule.confidence:.4f}",
                "source_model": rule.source_model,
                "grammar_valid": gc.is_valid,
                "dnf_valid": dnf_ok,
                "variables_used": "; ".join(gc.variables_used),
                "n_predicates": gc.n_predicates,
            })

    return str(path)


def generate_inference_report(
    candidates: List[CandidateRule],
    dataset_info: str,
    allowed_variables: List[str],
) -> str:
    """Generate a brief text report summarizing the rule learning results.

    Returns:
        Multi-line string report.
    """
    lines = [
        "=" * 70,
        "OPERATIONAL RULE INFERENCE REPORT (Group B)",
        "=" * 70,
        "",
        f"Dataset: {dataset_info}",
        f"Total candidate rules extracted: {len(candidates)}",
        "",
    ]

    # Group by source model
    models = {}
    for c in candidates:
        models.setdefault(c.source_model, []).append(c)

    for model, rules in models.items():
        lines.append(f"  [{model}] {len(rules)} rules")

    # Group by type
    pass_rules = [c for c in candidates if c.rule_type == "pass"]
    fail_rules = [c for c in candidates if c.rule_type == "fail"]
    lines.append(f"\n  Pass rules: {len(pass_rules)}")
    lines.append(f"  Fail rules: {len(fail_rules)}")

    # Grammar compliance
    valid_count = 0
    dnf_count = 0
    for c in candidates:
        gc = check_grammar_compliance(c.rule_text, allowed_variables)
        dnf_ok, _ = validate_dnf_structure(c.rule_text)
        if gc.is_valid:
            valid_count += 1
        if dnf_ok:
            dnf_count += 1

    lines.append(f"\n  Grammar-compliant: {valid_count}/{len(candidates)}")
    lines.append(f"  Valid DNF: {dnf_count}/{len(candidates)}")

    # Accuracy ranges
    if candidates:
        accs = [c.val_accuracy for c in candidates]
        lines.append(f"\n  Validation accuracy range: [{min(accs):.4f}, {max(accs):.4f}]")

        f1s = [c.val_f1 for c in candidates]
        lines.append(f"  Validation F1 range: [{min(f1s):.4f}, {max(f1s):.4f}]")

    # Top fail rules (most useful for Group C)
    lines.append(f"\n{'─' * 70}")
    lines.append("TOP FAIL RULES (candidates for inconsistency detection):")
    lines.append(f"{'─' * 70}")

    # Sort fail rules by confidence descending
    fail_sorted = sorted(fail_rules, key=lambda r: r.confidence, reverse=True)
    for i, rule in enumerate(fail_sorted[:10]):
        gc = check_grammar_compliance(rule.rule_text, allowed_variables)
        lines.append(f"\n  [{rule.rule_id}] (grammar_valid={gc.is_valid})")
        lines.append(f"  Text: {rule.rule_text}")
        lines.append(
            f"  Conf={rule.confidence:.2f}, Support={rule.support}, "
            f"ValAcc={rule.val_accuracy:.4f}, Complexity={rule.complexity}"
        )

    lines.append(f"\n{'=' * 70}")
    return "\n".join(lines)
