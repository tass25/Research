"""
Rule evaluator for Group C.

Evaluates candidate rules against D_evolved to compute:
- Decisiveness (consistency score)
- False positive rate (spurious Fail)
- False negative rate (missed Fail)
- Mismatch identification
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field

from cbf_data.loader import SimulationDataset, SimulationRun
from rule_inference.tree_extractor import CandidateRule


@dataclass
class RuleEvaluation:
    """Evaluation result of a single rule on D_evolved."""
    rule_id: str
    rule_text: str
    rule_type: str                  # "pass" or "fail"

    total_runs: int
    n_mismatches: int
    decisiveness: float             # 1 - (mismatches / total)

    # For Fail rules: FP = Pass outcome incorrectly flagged as Fail
    false_positive_rate: float      # FP / (FP + TN)
    false_negative_rate: float      # FN / (FN + TP)

    # Counts
    true_positives: int
    true_negatives: int
    false_positives: int
    false_negatives: int

    # The actual mismatched inputs
    mismatch_case_ids: List[int] = field(default_factory=list)

    # Grammar compliance
    grammar_valid: bool = True

    @property
    def accuracy(self) -> float:
        total = self.true_positives + self.true_negatives + self.false_positives + self.false_negatives
        return (self.true_positives + self.true_negatives) / total if total > 0 else 0.0

    @property
    def meets_selection_criteria(self) -> bool:
        """Check if rule meets Group C selection thresholds.

        Criteria:
        - High false positive rate >= 20% (many spurious failures)
        - Low false negative rate <= 5% (doesn't miss real violations)
        - Grammar valid
        """
        return (
            self.false_positive_rate >= 0.20
            and self.false_negative_rate <= 0.05
            and self.grammar_valid
        )


def _parse_rule_predicate(predicate_str: str) -> Optional[Dict]:
    """Parse a single predicate like 'var <= 1.5' into components.

    Returns:
        Dict with 'variable', 'operator', 'threshold' or None if unparseable.
    """
    pattern = r'^([a-z_][a-z0-9_]*)\s*(<=|>=|!=|<|>|=)\s*(-?[\d.]+)$'
    match = re.match(pattern, predicate_str.strip())
    if not match:
        return None
    return {
        "variable": match.group(1),
        "operator": match.group(2),
        "threshold": float(match.group(3)),
    }


def _evaluate_predicate(pred: Dict, features: Dict[str, float]) -> bool:
    """Evaluate a single parsed predicate against a feature dict."""
    var = pred["variable"]
    op = pred["operator"]
    thresh = pred["threshold"]

    if var not in features:
        return False

    val = features[var]
    if op == "<":
        return val < thresh
    elif op == "<=":
        return val <= thresh
    elif op == ">":
        return val > thresh
    elif op == ">=":
        return val >= thresh
    elif op == "=":
        return abs(val - thresh) < 1e-9
    elif op == "!=":
        return abs(val - thresh) >= 1e-9
    return False


def evaluate_rule_text(rule_text: str, features: Dict[str, float]) -> bool:
    """Evaluate a DNF rule string against a feature dictionary.

    Handles DNF format: (p1 AND p2) OR (p3 AND p4) OR ...

    Returns:
        True if the rule fires (predicts its class), False otherwise.
    """
    if not rule_text:
        return False

    # Split by OR to get clauses
    or_parts = re.split(r'\s+OR\s+', rule_text)

    for clause in or_parts:
        clause = clause.strip().strip("()")
        # Split by AND to get predicates
        and_parts = re.split(r'\s+AND\s+', clause)

        all_true = True
        for part in and_parts:
            pred = _parse_rule_predicate(part.strip())
            if pred is None:
                all_true = False
                break
            if not _evaluate_predicate(pred, features):
                all_true = False
                break

        if all_true:
            return True  # At least one conjunction is satisfied → DNF is true

    return False


def evaluate_rule_on_dataset(
    rule: CandidateRule,
    dataset: SimulationDataset,
    grammar_valid: bool = True,
) -> RuleEvaluation:
    """Evaluate a candidate rule against a simulation dataset.

    Mismatch definitions (per task assignment):
    - Pass rule: mismatch when rule(x)=true but outcome is Fail
    - Fail rule: mismatch when rule(x)=true but outcome is Pass

    For computing FP/FN rates:
    - Fail rule perspective (most interesting for refinement):
      - TP: rule says Fail AND outcome is Fail
      - FP: rule says Fail AND outcome is Pass (spurious failure!)
      - TN: rule says not-Fail AND outcome is Pass
      - FN: rule says not-Fail AND outcome is Fail (missed real failure)

    - Pass rule perspective:
      - TP: rule says Pass AND outcome is Pass
      - FP: rule says Pass AND outcome is Fail
      - TN: rule says not-Pass AND outcome is Fail
      - FN: rule says not-Pass AND outcome is Pass

    Args:
        rule: CandidateRule with rule_text and rule_type.
        dataset: SimulationDataset (typically D_evolved).
        grammar_valid: Whether rule passed grammar check.

    Returns:
        RuleEvaluation with all metrics.
    """
    tp = fp = tn = fn = 0
    mismatch_ids = []

    for run in dataset.runs:
        features = run.input_features
        rule_fires = evaluate_rule_text(rule.rule_text, features)
        outcome_pass = (run.label == "Pass")

        if rule.rule_type == "fail":
            # Rule predicts Fail when it fires
            if rule_fires:
                if not outcome_pass:
                    tp += 1  # Correctly flagged as Fail
                else:
                    fp += 1  # Spurious failure
                    mismatch_ids.append(run.case_id)
            else:
                if outcome_pass:
                    tn += 1
                else:
                    fn += 1

        else:  # pass rule
            # Rule predicts Pass when it fires
            if rule_fires:
                if outcome_pass:
                    tp += 1  # Correctly predicted Pass
                else:
                    fp += 1  # Wrongly predicted Pass
                    mismatch_ids.append(run.case_id)
            else:
                if not outcome_pass:
                    tn += 1
                else:
                    fn += 1

    total = tp + fp + tn + fn
    n_mismatches = fp  # Mismatches per the task definition

    # Decisiveness = 1 - (mismatches / total)
    decisiveness = 1.0 - (n_mismatches / total) if total > 0 else 0.0

    # FP rate = FP / (FP + TN) — among actual positives in the "not predicted class"
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    # FN rate = FN / (FN + TP)
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0

    return RuleEvaluation(
        rule_id=rule.rule_id,
        rule_text=rule.rule_text,
        rule_type=rule.rule_type,
        total_runs=total,
        n_mismatches=n_mismatches,
        decisiveness=decisiveness,
        false_positive_rate=fpr,
        false_negative_rate=fnr,
        true_positives=tp,
        true_negatives=tn,
        false_positives=fp,
        false_negatives=fn,
        mismatch_case_ids=mismatch_ids,
        grammar_valid=grammar_valid,
    )


def evaluate_all_rules(
    candidates: List[CandidateRule],
    dataset: SimulationDataset,
    allowed_variables: List[str],
) -> List[RuleEvaluation]:
    """Evaluate all candidate rules against D_evolved.

    Args:
        candidates: List of CandidateRule from Group B.
        dataset: SimulationDataset (D_evolved).
        allowed_variables: For grammar checking.

    Returns:
        List of RuleEvaluation, one per candidate.
    """
    from rule_inference.grammar_checker import check_grammar_compliance

    evaluations = []
    for rule in candidates:
        gc = check_grammar_compliance(rule.rule_text, allowed_variables)
        ev = evaluate_rule_on_dataset(rule, dataset, grammar_valid=gc.is_valid)
        evaluations.append(ev)

    return evaluations
