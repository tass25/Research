# Rule Validation — Group C

Evaluation, selection, and counterfactual analysis of candidate operational rules.

## Purpose

Takes candidate rules produced by Group B, evaluates them against **D_evolved**
(the evolved/CBF controller dataset), selects the most interesting inconsistent
rules, and generates L1-minimal counterfactual perturbation hints.

## Files

| File | Description |
|------|-------------|
| `rule_evaluator.py` | `evaluate_rule_on_dataset()`, `evaluate_all_rules()` — Compute decisiveness (DG), FPR, FNR per rule |
| `rule_selector.py` | `select_inconsistent_rules()`, `select_with_relaxed_criteria()` — Pick top-*k* rules for refinement |
| `counterfactual_hints.py` | `compute_minimal_perturbation()`, `find_inconsistent_examples()` — L1-minimal single-variable perturbations |
| `validation_report.py` | CSV and text report exporters |
| `__init__.py` | Package init |

## Key Formulas

### Decisiveness (from the SEAMS 2026 paper, Section 4)

$$D_G = 1 - \frac{N_{mismatch}}{N}$$

A mismatch occurs when the rule fires but the observed outcome contradicts
the prediction (see paper Table 1).

### False Positive / False Negative Rates

For a **fail rule**:

| | Rule fires (predicts Fail) | Rule silent |
|---|---|---|
| **Outcome = Fail** | TP | FN |
| **Outcome = Pass** | **FP** (mismatch) | TN |

- FPR = FP / (FP + TN)
- FNR = FN / (FN + TP)

### Selection Criteria

Rules are selected for refinement when:
- FPR ≥ 20 % (many spurious failures)
- FNR ≤ 5 % (doesn't miss real violations)
- Grammar-valid

### Counterfactuals

For each mismatch, the smallest single-variable change that flips the rule
verdict is computed (sorted by L1 distance).

## Output

- `rule_evaluations.csv` — full confusion matrix per rule
- `selected_rules.csv` — top-10 rules ranked by selection score
- `inconsistency_examples_{rule_id}.csv` — per-rule mismatch details with counterfactual hints
- `selection_report.txt` — human-readable summary

## Quick Start

```python
from cbf_data.loader import load_dataset
from rule_validation.rule_evaluator import evaluate_all_rules

d_evolved = load_dataset("unicycle_static_obstacle", "robust_evolved", "evolved")
evaluations = evaluate_all_rules(candidates, d_evolved, feature_names)
```

## Extensibility

- Adjust selection thresholds via `SelectionCriteria` dataclass.
- Replace the single-variable perturbation strategy in `counterfactual_hints.py`
  with simulation-based falsification for stronger counterfactuals.
