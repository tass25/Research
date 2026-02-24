"""
Main pipeline: End-to-end rule inference and validation.

Runs Group A (data loading) → Group B (rule inference) → Layer 1 (syntactic
validation) → Group C (evaluation & selection) → Layer 2 (semantic validation)
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

# ── Layer 1: Syntactic Validators ────────────────────────────────────
from validators import PreParseValidator, StructureValidator, AbsoluteBoundValidator
from parsers.lark_parser import OperationalRuleParser
from core.config import GrammarConfig

# ── Layer 2: Semantic Validator ──────────────────────────────────────
from semantic import SemanticValidator
from cbf_data.adapter import cbf_to_semantic


def run_pipeline(system: str, controller: str, output_dir: str = "output",
                 pipeline_cfg=None):
    """Run the full inference + validation pipeline for one system/controller.

    Args:
        system: e.g., "unicycle_static_obstacle"
        controller: e.g., "robust_evolved"
        output_dir: Base output directory.
        pipeline_cfg: Optional PipelineConfig from YAML.  When supplied,
                      overrides the hardcoded defaults.
    """
    out = Path(output_dir) / system / controller
    out.mkdir(parents=True, exist_ok=True)

    feature_names = STATIC_FEATURES if "static" in system else DYNAMIC_FEATURES

    # ── Resolve parameters from config or defaults ───────────────────
    if pipeline_cfg is not None:
        cfg_t = pipeline_cfg.thresholds
        dt_depths       = pipeline_cfg.dt_depths
        dt_min_leaf     = pipeline_cfg.dt_min_samples_leaf
        rf_n_est        = pipeline_cfg.rf_n_estimators
        rf_max_depth    = pipeline_cfg.rf_max_depth
        hc_n_est        = pipeline_cfg.hc_n_estimators
        hc_max_depth    = pipeline_cfg.hc_max_depth
        hc_min_conf     = pipeline_cfg.hc_min_confidence
        hc_min_sup      = pipeline_cfg.hc_min_support
        top_k           = pipeline_cfg.top_k
        random_seed     = pipeline_cfg.random_seed
        max_depth       = cfg_t.max_depth
        max_predicates  = cfg_t.max_predicates
        grammar_config  = pipeline_cfg.grammar
    else:
        dt_depths       = [2, 3, 4, 5, None]
        dt_min_leaf     = 5
        rf_n_est        = 100
        rf_max_depth    = 4
        hc_n_est        = 200
        hc_max_depth    = 5
        hc_min_conf     = 0.75
        hc_min_sup      = 10
        top_k           = 10
        random_seed     = 42
        max_depth       = 10
        max_predicates  = 20
        grammar_config  = None

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
        depths=dt_depths,
        min_samples_leaf=dt_min_leaf,
        random_state=random_seed,
    )
    logger.info("Decision tree candidates: %d", len(dt_candidates))

    # Random forest rules
    rf_candidates, rf_clf = extract_rules_from_forest(
        d_legacy,
        n_estimators=rf_n_est,
        max_depth=rf_max_depth,
        min_samples_leaf=dt_min_leaf,
        random_state=random_seed,
        top_k_trees=5,
    )
    logger.info("Random forest candidates: %d", len(rf_candidates))

    # High-confidence rules
    hc_candidates = extract_high_confidence_rules(
        d_legacy,
        n_estimators=hc_n_est,
        max_depth=hc_max_depth,
        random_state=random_seed,
        min_confidence=hc_min_conf,
        min_support=hc_min_sup,
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
    # LAYER 1: Syntactic validation
    # ──────────────────────────────────────────────────────────────────────
    logger.info("[Layer 1] Running syntactic validation on %d candidates...",
                len(unique_candidates))

    feature_bounds = get_feature_bounds(system)

    # Build grammar config for the parser (allow the system's variables)
    if grammar_config is None:
        grammar_config = GrammarConfig(
            allowed_variables=set(feature_names),
            variable_bounds=feature_bounds,
        )

    preparse_validator = PreParseValidator()
    structure_validator = StructureValidator(
        max_depth=max_depth, max_predicates=max_predicates,
    )
    bounds_validator = AbsoluteBoundValidator(feature_bounds)

    try:
        parser = OperationalRuleParser(grammar_config)
    except Exception as e:
        logger.warning("Could not initialise Lark parser: %s — skipping Layer 1 typed checks", e)
        parser = None

    l1_passed = []
    l1_failed = 0
    for cand in unique_candidates:
        # Step 1: Pre-parse normalisation
        norm_text, pp_warnings, pp_violations = preparse_validator.normalize_and_validate(
            cand.rule_text,
        )
        for w in pp_warnings:
            logger.debug("L1 preparse warning [%s]: %s", w.category, w.message)
        if pp_violations:
            logger.info("L1 REJECT (preparse): %s — %s", cand.rule_text,
                        "; ".join(v.message for v in pp_violations))
            l1_failed += 1
            continue

        # Step 2: Parse into typed Rule object (if parser available)
        parsed_rule = None
        if parser is not None:
            parsed_rule, parse_errors = parser.parse_safe(norm_text)
            if parsed_rule is None:
                logger.debug("L1 parse skip: %s — %s", norm_text, parse_errors)
                # Don't reject — the rule is still valid as text; just can't
                # do typed checks.

        # Step 3: Structure validation (only if parsed)
        if parsed_rule is not None:
            struct_violations = structure_validator.validate(parsed_rule)
            if struct_violations:
                logger.info("L1 REJECT (structure): %s — %s", cand.rule_text,
                            "; ".join(v.message for v in struct_violations))
                l1_failed += 1
                continue

            # Step 4: Absolute-bound validation
            bound_violations = bounds_validator.validate(parsed_rule)
            if bound_violations:
                logger.info("L1 REJECT (bounds): %s — %s", cand.rule_text,
                            "; ".join(v.message for v in bound_violations))
                l1_failed += 1
                continue

        l1_passed.append(cand)

    logger.info("[Layer 1] %d passed, %d rejected", len(l1_passed), l1_failed)

    # Continue the pipeline with only Layer 1 passed candidates
    unique_candidates = l1_passed

    # ──────────────────────────────────────────────────────────────────────
    # GROUP C: Evaluate rules on D_evolved, select inconsistent rules
    # ──────────────────────────────────────────────────────────────────────
    logger.info("[Group C] Evaluating %d rules on D_evolved...", len(unique_candidates))

    evaluations = evaluate_all_rules(unique_candidates, d_evolved, feature_names)

    # Export evaluations
    eval_csv = export_evaluations_csv(evaluations, str(out / "rule_evaluations.csv"))
    logger.info("Evaluations exported to %s", eval_csv)

    # Select top-k inconsistent rules
    selected = select_with_relaxed_criteria(evaluations, top_k=top_k)
    logger.info("Selected %d inconsistent rules for refinement", len(selected))

    # Export selected rules
    selected_csv = export_selected_rules_csv(selected, str(out / "selected_rules.csv"))
    logger.info("Selected rules exported to %s", selected_csv)

    # Generate inconsistency examples + counterfactuals for each selected rule
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

    # ──────────────────────────────────────────────────────────────────────
    # LAYER 2: Semantic validation on selected rules
    # ──────────────────────────────────────────────────────────────────────
    if selected:
        logger.info("[Layer 2] Running semantic validation on %d selected rules...",
                    len(selected))

        # Convert cbf_data.SimulationDataset → data.SimulationDataset
        # so the semantic layer can operate on the correct schema.
        sem_dataset = cbf_to_semantic(d_evolved)

        sem_config = None
        if pipeline_cfg is not None:
            sem_config = {
                "consistency_threshold": pipeline_cfg.thresholds.consistency_threshold,
                "overfitting_threshold": pipeline_cfg.thresholds.overfitting_risk_threshold,
                "train_test_gap_threshold": pipeline_cfg.thresholds.train_test_gap,
            }

        semantic_results = []
        for sr in selected:
            ev = sr.evaluation
            rule_set_type = ev.rule_type if ev.rule_type in ("Pass", "Fail") else "Pass"

            sem_validator = SemanticValidator(
                rule_set_type=rule_set_type,
                variable_bounds=feature_bounds,
            )

            # Parse rule for semantic evaluation
            parsed = None
            if parser is not None:
                parsed, _ = parser.parse_safe(ev.rule_text)

            if parsed is not None:
                result = sem_validator.validate(
                    parsed,
                    sem_dataset,
                    config=sem_config,
                )
                semantic_results.append(result)
                logger.info(
                    "L2 %s: %s (consistency=%.2f, contradictions=%d, overfitting=%.2f)",
                    "PASS" if result.passed_validation else "FAIL",
                    ev.rule_text[:60],
                    result.consistency_score,
                    len(result.contradictions),
                    result.overfitting_risk,
                )

        # Export semantic results as JSON
        if semantic_results:
            import json
            sem_out = [r.to_dict() for r in semantic_results]
            sem_path = out / "semantic_validation.json"
            sem_path.write_text(json.dumps(sem_out, indent=2), encoding="utf-8")
            logger.info("Semantic validation results saved to %s", sem_path)

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
    pipeline_cfg = None
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
        run_pipeline(args.system, args.controller, args.output_dir, pipeline_cfg)
    elif args.system:
        # Run all controllers for this system
        for sys_name, ctrl in AVAILABLE_SYSTEMS:
            if sys_name == args.system:
                run_pipeline(sys_name, ctrl, args.output_dir, pipeline_cfg)
    else:
        # Run all
        for sys_name, ctrl in AVAILABLE_SYSTEMS:
            try:
                run_pipeline(sys_name, ctrl, args.output_dir, pipeline_cfg)
            except Exception as e:
                logger.error("FAILED: %s/%s: %s", sys_name, ctrl, e, exc_info=True)


if __name__ == "__main__":
    main()
