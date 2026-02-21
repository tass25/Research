"""
Counterfactual candidate generator for Group C.

For each inconsistent example (where rule verdict != observed outcome),
computes L1-minimal perturbation candidates that would flip the rule verdict.
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field

from cbf_data.loader import SimulationDataset, SimulationRun
from rule_validation.rule_evaluator import evaluate_rule_text, _parse_rule_predicate


@dataclass
class CounterfactualCandidate:
    """A suggested L1-minimal perturbation for an inconsistent example."""
    case_id: int
    original_features: Dict[str, float]
    perturbed_features: Dict[str, float]
    changed_variable: str
    original_value: float
    perturbed_value: float
    l1_distance: float
    rule_verdict_before: bool       # Rule fires on original
    rule_verdict_after: bool        # Rule fires on perturbed


@dataclass
class InconsistentExample:
    """An input where rule verdict != observed outcome, with counterfactual hints."""
    case_id: int
    input_features: Dict[str, float]
    observed_label: str             # "Pass" or "Fail"
    rule_verdict: str               # What the rule predicts
    rule_text: str
    rule_type: str
    counterfactuals: List[CounterfactualCandidate] = field(default_factory=list)


def _extract_predicates_from_rule(rule_text: str) -> List[Dict]:
    """Extract all predicates from a DNF rule text.

    Returns list of dicts with 'variable', 'operator', 'threshold'.
    """
    predicates = []
    # Split by OR then AND
    or_parts = re.split(r'\s+OR\s+', rule_text)
    for clause in or_parts:
        clause = clause.strip().strip("()")
        and_parts = re.split(r'\s+AND\s+', clause)
        for part in and_parts:
            pred = _parse_rule_predicate(part.strip())
            if pred:
                predicates.append(pred)
    return predicates


def compute_minimal_perturbation(
    features: Dict[str, float],
    rule_text: str,
    feature_bounds: Optional[Dict[str, Tuple[float, float]]] = None,
    epsilon: float = 0.001,
) -> List[CounterfactualCandidate]:
    """Compute L1-minimal perturbations that would flip the rule verdict.

    Strategy: For each predicate in the rule, compute the smallest
    change to a single variable that would flip that predicate.
    Return the candidates sorted by L1 distance.

    Args:
        features: Original input feature values.
        rule_text: The rule text to analyze.
        feature_bounds: Optional physical bounds for clamping.
        epsilon: Small offset past the threshold.

    Returns:
        List of CounterfactualCandidate sorted by L1 distance.
    """
    predicates = _extract_predicates_from_rule(rule_text)
    original_fires = evaluate_rule_text(rule_text, features)
    candidates = []

    for pred in predicates:
        var = pred["variable"]
        op = pred["operator"]
        thresh = pred["threshold"]

        if var not in features:
            continue

        current_val = features[var]

        # Compute the perturbation that would flip this predicate
        perturbed_val = None

        if op == "<=":
            if current_val <= thresh:
                # Currently satisfied; flip by going above threshold
                perturbed_val = thresh + epsilon
            else:
                # Currently not satisfied; flip by going below/equal threshold
                perturbed_val = thresh - epsilon
        elif op == "<":
            if current_val < thresh:
                perturbed_val = thresh + epsilon
            else:
                perturbed_val = thresh - epsilon
        elif op == ">":
            if current_val > thresh:
                perturbed_val = thresh - epsilon
            else:
                perturbed_val = thresh + epsilon
        elif op == ">=":
            if current_val >= thresh:
                perturbed_val = thresh - epsilon
            else:
                perturbed_val = thresh + epsilon
        elif op == "=":
            if abs(current_val - thresh) < 1e-9:
                perturbed_val = thresh + epsilon
            else:
                perturbed_val = thresh
        elif op == "!=":
            if abs(current_val - thresh) >= 1e-9:
                perturbed_val = thresh
            else:
                perturbed_val = thresh + epsilon

        if perturbed_val is None:
            continue

        # Clamp to physical bounds if provided
        if feature_bounds and var in feature_bounds:
            lo, hi = feature_bounds[var]
            perturbed_val = max(lo, min(hi, perturbed_val))

        # Build perturbed feature set
        perturbed_features = dict(features)
        perturbed_features[var] = perturbed_val

        # Check if the rule verdict actually flips
        perturbed_fires = evaluate_rule_text(rule_text, perturbed_features)

        l1_dist = abs(perturbed_val - current_val)

        candidates.append(CounterfactualCandidate(
            case_id=-1,  # Will be set by caller
            original_features=dict(features),
            perturbed_features=perturbed_features,
            changed_variable=var,
            original_value=current_val,
            perturbed_value=perturbed_val,
            l1_distance=l1_dist,
            rule_verdict_before=original_fires,
            rule_verdict_after=perturbed_fires,
        ))

    # Sort by L1 distance (minimal perturbation first)
    candidates.sort(key=lambda c: c.l1_distance)

    # Only keep candidates that actually flip the verdict
    flipping = [c for c in candidates if c.rule_verdict_before != c.rule_verdict_after]

    # If no single-variable flip works, return all sorted by distance
    return flipping if flipping else candidates[:3]


def find_inconsistent_examples(
    rule_text: str,
    rule_type: str,
    dataset: SimulationDataset,
    mismatch_case_ids: List[int],
    feature_bounds: Optional[Dict[str, Tuple[float, float]]] = None,
    max_counterfactuals_per_example: int = 3,
) -> List[InconsistentExample]:
    """Find and annotate inconsistent examples with counterfactual hints.

    Args:
        rule_text: The rule string.
        rule_type: "pass" or "fail".
        dataset: SimulationDataset (D_evolved).
        mismatch_case_ids: Case IDs flagged as mismatches by the evaluator.
        feature_bounds: Physical bounds for perturbation clamping.
        max_counterfactuals_per_example: Max counterfactuals per example.

    Returns:
        List of InconsistentExample with counterfactual candidates.
    """
    mismatch_set = set(mismatch_case_ids)
    examples = []

    for run in dataset.runs:
        if run.case_id not in mismatch_set:
            continue

        rule_fires = evaluate_rule_text(rule_text, run.input_features)
        rule_verdict = rule_type.capitalize() if rule_fires else ("Pass" if rule_type == "fail" else "Fail")

        # Compute counterfactuals
        cfs = compute_minimal_perturbation(
            run.input_features,
            rule_text,
            feature_bounds=feature_bounds,
        )
        # Set case_id and limit
        for cf in cfs:
            cf.case_id = run.case_id
        cfs = cfs[:max_counterfactuals_per_example]

        examples.append(InconsistentExample(
            case_id=run.case_id,
            input_features=dict(run.input_features),
            observed_label=run.label,
            rule_verdict=rule_verdict,
            rule_text=rule_text,
            rule_type=rule_type,
            counterfactuals=cfs,
        ))

    return examples
