"""
Inconsistent rule selector for Group C.

Selects the top-k rules that are best candidates for refinement:
- High false positive rate (>= 20%): many spurious failures
- Low false negative rate (<= 5%): conservative (doesn't miss real failures)
- Grammar compliant and interpretable
"""

from typing import List, Optional, Tuple
from dataclasses import dataclass, field

from rule_validation.rule_evaluator import RuleEvaluation


@dataclass
class SelectionCriteria:
    """Configurable selection thresholds."""
    min_false_positive_rate: float = 0.20   # >= 20% spurious failures
    max_false_negative_rate: float = 0.05   # <= 5% missed real failures
    require_grammar_valid: bool = True
    min_n_mismatches: int = 1               # At least 1 mismatch to be "inconsistent"
    max_complexity: Optional[int] = None    # Optional upper bound on complexity


@dataclass
class SelectedRule:
    """A rule selected for refinement with full context."""
    evaluation: RuleEvaluation
    rank: int
    selection_score: float          # Combined ranking score
    selection_reason: str           # Human-readable justification


def compute_selection_score(ev: RuleEvaluation) -> float:
    """Compute a composite score for ranking inconsistent rules.

    Higher score = better candidate for refinement.
    Balances high FP rate (more spurious failures to fix)
    with low FN rate (rule is still conservative).

    Score = FP_rate * (1 - FN_rate) * decisiveness_penalty
    """
    # Reward high FP (more inconsistencies to fix)
    fp_component = ev.false_positive_rate

    # Penalize high FN (rule misses real failures)
    fn_penalty = 1.0 - ev.false_negative_rate

    # Small bonus for having more total mismatches (more data to refine with)
    volume_bonus = min(ev.n_mismatches / 20.0, 1.0)

    return fp_component * fn_penalty * (0.7 + 0.3 * volume_bonus)


def select_inconsistent_rules(
    evaluations: List[RuleEvaluation],
    criteria: Optional[SelectionCriteria] = None,
    top_k: int = 10,
) -> List[SelectedRule]:
    """Select the top-k inconsistent rules for refinement.

    Filters by selection criteria, then ranks by selection score.

    Args:
        evaluations: List of RuleEvaluation from rule_evaluator.
        criteria: Selection thresholds (defaults to assignment spec).
        top_k: Number of rules to select (5-10 per assignment).

    Returns:
        List of SelectedRule, sorted by rank (best first).
    """
    if criteria is None:
        criteria = SelectionCriteria()

    # Filter candidates
    filtered = []
    for ev in evaluations:
        reasons = []

        # Must be grammar valid
        if criteria.require_grammar_valid and not ev.grammar_valid:
            continue

        # Must have minimum mismatches
        if ev.n_mismatches < criteria.min_n_mismatches:
            continue

        # FP rate threshold
        if ev.false_positive_rate < criteria.min_false_positive_rate:
            continue
        reasons.append(f"FP rate {ev.false_positive_rate:.1%} >= {criteria.min_false_positive_rate:.0%}")

        # FN rate threshold
        if ev.false_negative_rate > criteria.max_false_negative_rate:
            continue
        reasons.append(f"FN rate {ev.false_negative_rate:.1%} <= {criteria.max_false_negative_rate:.0%}")

        # Optional complexity filter
        if criteria.max_complexity is not None:
            # Count predicates from rule text
            n_preds = ev.rule_text.count("<=") + ev.rule_text.count(">=") + \
                      ev.rule_text.count("!=")
            # Also count single < > = not part of <=, >=, !=
            import re
            n_preds += len(re.findall(r'(?<![<>!])(<|>|=)(?!=)', ev.rule_text))
            if n_preds > criteria.max_complexity:
                continue

        reasons.append(f"{ev.n_mismatches} mismatches on {ev.total_runs} runs")
        filtered.append((ev, " | ".join(reasons)))

    # Score and rank
    scored = []
    for ev, reason in filtered:
        score = compute_selection_score(ev)
        scored.append((ev, score, reason))

    scored.sort(key=lambda x: x[1], reverse=True)

    # Select top-k
    selected = []
    for rank, (ev, score, reason) in enumerate(scored[:top_k], start=1):
        selected.append(SelectedRule(
            evaluation=ev,
            rank=rank,
            selection_score=score,
            selection_reason=reason,
        ))

    return selected


def select_with_relaxed_criteria(
    evaluations: List[RuleEvaluation],
    top_k: int = 10,
) -> List[SelectedRule]:
    """Select rules with progressively relaxed criteria.

    If strict criteria yield fewer than top_k rules,
    relax FP threshold down to 10% and FN threshold up to 10%.

    Returns:
        List of SelectedRule, up to top_k.
    """
    # Try strict first
    strict = SelectionCriteria(
        min_false_positive_rate=0.20,
        max_false_negative_rate=0.05,
    )
    selected = select_inconsistent_rules(evaluations, strict, top_k)

    if len(selected) >= top_k:
        return selected

    # Relax step 1: FP >= 15%, FN <= 10%
    relaxed1 = SelectionCriteria(
        min_false_positive_rate=0.15,
        max_false_negative_rate=0.10,
    )
    selected = select_inconsistent_rules(evaluations, relaxed1, top_k)

    if len(selected) >= top_k:
        return selected

    # Relax step 2: FP >= 10%, FN <= 15%
    relaxed2 = SelectionCriteria(
        min_false_positive_rate=0.10,
        max_false_negative_rate=0.15,
    )
    selected = select_inconsistent_rules(evaluations, relaxed2, top_k)

    if len(selected) >= top_k:
        return selected

    # Final: just take the top-k by score, no threshold filtering
    relaxed_final = SelectionCriteria(
        min_false_positive_rate=0.0,
        max_false_negative_rate=1.0,
        min_n_mismatches=0,
    )
    return select_inconsistent_rules(evaluations, relaxed_final, top_k)
