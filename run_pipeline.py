"""
Main pipeline: End-to-end rule inference and validation.

Runs Group A (data loading) → Group B (rule inference) → Group C (validation & selection)
for all CBFKIT system configurations.

Usage:
    python run_pipeline.py
    python run_pipeline.py --system unicycle_static_obstacle --controller robust_evolved
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))

from cbf_data.loader import (
    load_dataset, load_paired_comparison, summarize_dataset,
    AVAILABLE_SYSTEMS, STATIC_FEATURES, DYNAMIC_FEATURES,
)
from cbf_data.metadata import get_system_metadata, get_feature_bounds, print_metadata

from rule_inference.tree_extractor import sweep_depths, extract_dnf_rules
from rule_inference.forest_extractor import extract_rules_from_forest, extract_high_confidence_rules
from rule_inference.grammar_checker import check_grammar_compliance
from rule_inference.rule_export import export_candidates_to_csv, generate_inference_report

from rule_validation.rule_evaluator import evaluate_all_rules
from rule_validation.rule_selector import select_with_relaxed_criteria
from rule_validation.counterfactual_hints import find_inconsistent_examples
from rule_validation.validation_report import (
    export_evaluations_csv,
    export_selected_rules_csv,
    export_inconsistency_examples_csv,
    generate_selection_report,
)


def run_pipeline(system: str, controller: str, output_dir: str = "output"):
    """Run the full inference + validation pipeline for one system/controller.

    Args:
        system: e.g., "unicycle_static_obstacle"
        controller: e.g., "robust_evolved"
        output_dir: Base output directory.
    """
    out = Path(output_dir) / system / controller
    out.mkdir(parents=True, exist_ok=True)

    feature_names = STATIC_FEATURES if "static" in system else DYNAMIC_FEATURES

    print(f"\n{'=' * 70}")
    print(f"PIPELINE: {system} / {controller}")
    print(f"{'=' * 70}")

    # ──────────────────────────────────────────────────────────────────────
    # GROUP A: Load data
    # ──────────────────────────────────────────────────────────────────────
    print("\n[Group A] Loading datasets...")

    d_legacy = load_dataset(system, controller, "legacy")
    d_evolved = load_dataset(system, controller, "evolved")
    pairs = load_paired_comparison(system, controller)

    print(f"\n  D_legacy:\n{summarize_dataset(d_legacy)}")
    print(f"\n  D_evolved:\n{summarize_dataset(d_evolved)}")

    n_inconsistent_pairs = sum(1 for p in pairs if p.is_inconsistent)
    print(f"\n  Paired comparisons: {len(pairs)} total, {n_inconsistent_pairs} inconsistent")
    print(f"  (Legacy=Fail but Evolved=Pass: {n_inconsistent_pairs})")

    # Metadata
    meta_str = print_metadata(system)
    meta_path = out / "system_metadata.txt"
    meta_path.write_text(meta_str, encoding="utf-8")
    print(f"\n  Metadata saved to {meta_path}")

    # ──────────────────────────────────────────────────────────────────────
    # GROUP B: Rule inference from D_legacy
    # ──────────────────────────────────────────────────────────────────────
    print("\n[Group B] Inferring rules from D_legacy...")

    # Decision tree rules across multiple depths
    dt_candidates = sweep_depths(
        d_legacy,
        depths=[2, 3, 4, 5, None],
        min_samples_leaf=5,
        random_state=42,
    )
    print(f"  Decision tree candidates: {len(dt_candidates)}")

    # Random forest rules
    rf_candidates, rf_clf = extract_rules_from_forest(
        d_legacy,
        n_estimators=100,
        max_depth=4,
        min_samples_leaf=5,
        random_state=42,
        top_k_trees=5,
    )
    print(f"  Random forest candidates: {len(rf_candidates)}")

    # High-confidence rules
    hc_candidates = extract_high_confidence_rules(
        d_legacy,
        n_estimators=200,
        max_depth=5,
        random_state=42,
        min_confidence=0.75,
        min_support=10,
    )
    print(f"  High-confidence candidates: {len(hc_candidates)}")

    # Combine all candidates (deduplicate by rule_text)
    all_candidates = dt_candidates + rf_candidates + hc_candidates
    seen_texts = set()
    unique_candidates = []
    for c in all_candidates:
        if c.rule_text not in seen_texts:
            seen_texts.add(c.rule_text)
            unique_candidates.append(c)

    print(f"  Total unique candidates: {len(unique_candidates)}")

    # Export candidate rules CSV
    candidates_csv = export_candidates_to_csv(
        unique_candidates,
        str(out / "candidate_rules.csv"),
        feature_names,
    )
    print(f"  Candidate rules exported to {candidates_csv}")

    # Inference report
    report = generate_inference_report(
        unique_candidates,
        f"{system} / {controller} / D_legacy ({d_legacy.n_runs} runs)",
        feature_names,
    )
    report_path = out / "inference_report.txt"
    report_path.write_text(report, encoding="utf-8")
    print(f"  Inference report saved to {report_path}")
    try:
        print(report)
    except UnicodeEncodeError:
        print(report.encode("ascii", errors="replace").decode("ascii"))

    # ──────────────────────────────────────────────────────────────────────
    # GROUP C: Evaluate rules on D_evolved, select inconsistent rules
    # ──────────────────────────────────────────────────────────────────────
    print(f"\n[Group C] Evaluating {len(unique_candidates)} rules on D_evolved...")

    evaluations = evaluate_all_rules(unique_candidates, d_evolved, feature_names)

    # Export evaluations
    eval_csv = export_evaluations_csv(evaluations, str(out / "rule_evaluations.csv"))
    print(f"  Evaluations exported to {eval_csv}")

    # Select top-k inconsistent rules
    selected = select_with_relaxed_criteria(evaluations, top_k=10)
    print(f"  Selected {len(selected)} inconsistent rules for refinement")

    # Export selected rules
    selected_csv = export_selected_rules_csv(selected, str(out / "selected_rules.csv"))
    print(f"  Selected rules exported to {selected_csv}")

    # Generate inconsistency examples + counterfactuals for each selected rule
    feature_bounds = get_feature_bounds(system)
    all_examples = []

    for sr in selected:
        ev = sr.evaluation
        examples = find_inconsistent_examples(
            rule_text=ev.rule_text,
            rule_type=ev.rule_type,
            dataset=d_evolved,
            mismatch_case_ids=ev.mismatch_case_ids,
            feature_bounds=feature_bounds,
            max_counterfactuals_per_example=3,
        )
        all_examples.extend(examples)

        if examples:
            ex_csv_path = out / f"inconsistency_examples_{ev.rule_id}.csv"
            export_inconsistency_examples_csv(
                examples,
                str(ex_csv_path),
                feature_names,
            )

    print(f"  Total inconsistent examples with counterfactuals: {len(all_examples)}")

    # Selection report
    sel_report = generate_selection_report(
        evaluations, selected, all_examples,
        f"{system} / {controller}",
    )
    sel_report_path = out / "selection_report.txt"
    sel_report_path.write_text(sel_report, encoding="utf-8")
    print(f"  Selection report saved to {sel_report_path}")
    try:
        print(sel_report)
    except UnicodeEncodeError:
        print(sel_report.encode("ascii", errors="replace").decode("ascii"))

    print(f"\n{'=' * 70}")
    print(f"PIPELINE COMPLETE: {system} / {controller}")
    print(f"All outputs in: {out}")
    print(f"{'=' * 70}")


def main():
    parser = argparse.ArgumentParser(
        description="Run rule inference and validation pipeline"
    )
    parser.add_argument(
        "--system", type=str, default=None,
        help="System name (e.g., unicycle_static_obstacle). Default: run all."
    )
    parser.add_argument(
        "--controller", type=str, default=None,
        help="Controller type (e.g., robust_evolved). Default: run all."
    )
    parser.add_argument(
        "--output-dir", type=str, default="output",
        help="Output directory. Default: output/"
    )
    args = parser.parse_args()

    if args.system and args.controller:
        run_pipeline(args.system, args.controller, args.output_dir)
    elif args.system:
        # Run all controllers for this system
        for sys_name, ctrl in AVAILABLE_SYSTEMS:
            if sys_name == args.system:
                run_pipeline(sys_name, ctrl, args.output_dir)
    else:
        # Run all
        for sys_name, ctrl in AVAILABLE_SYSTEMS:
            try:
                run_pipeline(sys_name, ctrl, args.output_dir)
            except Exception as e:
                print(f"\nERROR: {sys_name}/{ctrl}: {e}")
                import traceback
                traceback.print_exc()


if __name__ == "__main__":
    main()
