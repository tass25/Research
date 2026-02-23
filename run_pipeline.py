"""
Main pipeline: End-to-end rule inference and validation.

Runs Group A (data loading) → Group B (rule inference) → Group C (validation & selection)
for all CBFKIT system configurations.

Usage:
    python run_pipeline.py
    python run_pipeline.py --system unicycle_static_obstacle --controller robust_evolved
    python run_pipeline.py --config config.yaml --verbose
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))

from core.logging_config import setup_logging, get_logger

logger = get_logger(__name__)

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

    logger.info("=" * 70)
    logger.info("PIPELINE: %s / %s", system, controller)
    logger.info("=" * 70)

    # ──────────────────────────────────────────────────────────────────────
    # GROUP A: Load data
    # ──────────────────────────────────────────────────────────────────────
    logger.info("[Group A] Loading datasets...")

    d_legacy = load_dataset(system, controller, "legacy")
    d_evolved = load_dataset(system, controller, "evolved")
    pairs = load_paired_comparison(system, controller)

    logger.info("D_legacy:\n%s", summarize_dataset(d_legacy))
    logger.info("D_evolved:\n%s", summarize_dataset(d_evolved))

    n_inconsistent_pairs = sum(1 for p in pairs if p.is_inconsistent)
    logger.info(
        "Paired comparisons: %d total, %d inconsistent (Legacy=Fail, Evolved=Pass)",
        len(pairs), n_inconsistent_pairs,
    )

    # Metadata
    meta_str = print_metadata(system)
    meta_path = out / "system_metadata.txt"
    meta_path.write_text(meta_str, encoding="utf-8")
    logger.info("Metadata saved to %s", meta_path)

    # ──────────────────────────────────────────────────────────────────────
    # GROUP B: Rule inference from D_legacy
    # ──────────────────────────────────────────────────────────────────────
    logger.info("[Group B] Inferring rules from D_legacy...")

    # Decision tree rules across multiple depths
    dt_candidates = sweep_depths(
        d_legacy,
        depths=[2, 3, 4, 5, None],
        min_samples_leaf=5,
        random_state=42,
    )
    logger.info("Decision tree candidates: %d", len(dt_candidates))

    # Random forest rules
    rf_candidates, rf_clf = extract_rules_from_forest(
        d_legacy,
        n_estimators=100,
        max_depth=4,
        min_samples_leaf=5,
        random_state=42,
        top_k_trees=5,
    )
    logger.info("Random forest candidates: %d", len(rf_candidates))

    # High-confidence rules
    hc_candidates = extract_high_confidence_rules(
        d_legacy,
        n_estimators=200,
        max_depth=5,
        random_state=42,
        min_confidence=0.75,
        min_support=10,
    )
    logger.info("High-confidence candidates: %d", len(hc_candidates))

    # Combine all candidates (deduplicate by normalized rule_text)
    all_candidates = dt_candidates + rf_candidates + hc_candidates
    seen_texts = set()
    unique_candidates = []
    for c in all_candidates:
        # Normalize: strip outer parentheses for dedup comparison
        normalized = c.rule_text.strip()
        while normalized.startswith("(") and normalized.endswith(")"):
            inner = normalized[1:-1]
            # Only strip if the outer parens wrap the whole expression
            depth = 0
            balanced = True
            for ch in inner:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                if depth < 0:
                    balanced = False
                    break
            if balanced and depth == 0:
                normalized = inner.strip()
            else:
                break
        if normalized not in seen_texts:
            seen_texts.add(normalized)
            unique_candidates.append(c)

    logger.info("Total unique candidates: %d", len(unique_candidates))

    # Export candidate rules CSV
    candidates_csv = export_candidates_to_csv(
        unique_candidates,
        str(out / "candidate_rules.csv"),
        feature_names,
    )
    logger.info("Candidate rules exported to %s", candidates_csv)

    # Inference report
    report = generate_inference_report(
        unique_candidates,
        f"{system} / {controller} / D_legacy ({d_legacy.n_runs} runs)",
        feature_names,
    )
    report_path = out / "inference_report.txt"
    report_path.write_text(report, encoding="utf-8")
    logger.info("Inference report saved to %s", report_path)
    logger.debug("Inference report:\n%s", report)

    # ──────────────────────────────────────────────────────────────────────
    # GROUP C: Evaluate rules on D_evolved, select inconsistent rules
    # ──────────────────────────────────────────────────────────────────────
    logger.info("[Group C] Evaluating %d rules on D_evolved...", len(unique_candidates))

    evaluations = evaluate_all_rules(unique_candidates, d_evolved, feature_names)

    # Export evaluations
    eval_csv = export_evaluations_csv(evaluations, str(out / "rule_evaluations.csv"))
    logger.info("Evaluations exported to %s", eval_csv)

    # Select top-k inconsistent rules
    selected = select_with_relaxed_criteria(evaluations, top_k=10)
    logger.info("Selected %d inconsistent rules for refinement", len(selected))

    # Export selected rules
    selected_csv = export_selected_rules_csv(selected, str(out / "selected_rules.csv"))
    logger.info("Selected rules exported to %s", selected_csv)

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

    logger.info("Total inconsistent examples with counterfactuals: %d", len(all_examples))

    # Selection report
    sel_report = generate_selection_report(
        evaluations, selected, all_examples,
        f"{system} / {controller}",
    )
    sel_report_path = out / "selection_report.txt"
    sel_report_path.write_text(sel_report, encoding="utf-8")
    logger.info("Selection report saved to %s", sel_report_path)
    logger.debug("Selection report:\n%s", sel_report)

    logger.info("=" * 70)
    logger.info("PIPELINE COMPLETE: %s / %s", system, controller)
    logger.info("All outputs in: %s", out)
    logger.info("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run rule inference and validation pipeline (SEAMS 2026)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python run_pipeline.py\n"
            "  python run_pipeline.py --system unicycle_static_obstacle --controller robust_evolved\n"
            "  python run_pipeline.py --verbose --log-file pipeline.log\n"
            "  python run_pipeline.py --config config.yaml\n"
        ),
    )
    parser.add_argument(
        "--system", type=str, default=None,
        choices=[s for s, _ in AVAILABLE_SYSTEMS],
        help="System name. Default: run all.",
    )
    parser.add_argument(
        "--controller", type=str, default=None,
        choices=list({c for _, c in AVAILABLE_SYSTEMS}),
        help="Controller type. Default: run all.",
    )
    parser.add_argument(
        "--output-dir", type=str, default="output",
        help="Output directory. Default: output/",
    )
    parser.add_argument(
        "--config", type=str, default=None,
        help="Path to YAML config file (overrides defaults).",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable DEBUG-level logging.",
    )
    parser.add_argument(
        "--log-file", type=str, default=None,
        help="Also write logs to this file.",
    )
    args = parser.parse_args()

    # ── Logging setup ────────────────────────────────────────────────
    setup_logging(
        level="DEBUG" if args.verbose else "INFO",
        log_file=args.log_file,
    )

    # ── Optional YAML config ─────────────────────────────────────────
    if args.config:
        from core.config_loader import load_pipeline_config
        try:
            pipeline_cfg = load_pipeline_config(args.config)
            logger.info("Loaded pipeline config from %s", args.config)
        except Exception as e:
            logger.error("Failed to load config %s: %s", args.config, e)
            sys.exit(1)

    # ── Validate system/controller ───────────────────────────────────
    valid_systems = {s for s, _ in AVAILABLE_SYSTEMS}
    if args.system and args.system not in valid_systems:
        logger.error(
            "Unknown system '%s'. Available: %s", args.system, sorted(valid_systems)
        )
        sys.exit(1)

    # ── Run ──────────────────────────────────────────────────────────
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
                logger.error("FAILED: %s/%s: %s", sys_name, ctrl, e, exc_info=True)


if __name__ == "__main__":
    main()
