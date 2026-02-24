# Rule Validation — Group C

Evaluation, selection, and counterfactual analysis of candidate operational rules.

## Why This Folder Exists

Candidate rules extracted by Group B are syntactically valid but may not behave correctly on the **evolved** (CBF) controller. This package evaluates each candidate against **D_evolved**, identifies rules with high inconsistency (rules that fire on passing cases or miss failing ones), and generates L1-minimal counterfactual perturbation hints. The selected rules become the input for LLM refinement.

## Folder Structure

```
rule_validation/
├── __init__.py                # Package init
├── rule_evaluator.py          # Decisiveness, FPR, FNR computation per rule
├── rule_selector.py           # Top-k inconsistent rule selection
├── counterfactual_hints.py    # L1-minimal single-variable perturbations
└── validation_report.py       # CSV and text report generation
```

## Files

### `rule_evaluator.py` — Rule Evaluation on D_evolved

| Function | Purpose |
|----------|---------|
| `evaluate_rule_on_dataset(rule, dataset, grammar_valid)` | Evaluate a single `CandidateRule` against a `SimulationDataset`: compute TP, FP, TN, FN, decisiveness, FPR, FNR |
| `evaluate_all_rules(candidates, dataset, allowed_variables)` | Evaluate all candidates in batch, return list of `RuleEvaluation` objects |

**`RuleEvaluation` dataclass fields:** `rule_id`, `rule_text`, `rule_type`, `total_runs`, `n_mismatches`, `decisiveness`, `false_positive_rate`, `false_negative_rate`, `true_positives`, `true_negatives`, `false_positives`, `false_negatives`, `mismatch_case_ids`, `grammar_valid`.

> [!NOTE]
> **Evaluation Semantics:** `rule_evaluator.py` uses exact floating-point equality (`==`, `!=`) for `=` and `!=` operators. This perfectly aligns with the typed AST evaluation in `core.schema.Relation` preventing edge-case divergence between Group C selection and semantic validation.

### `rule_selector.py` — Inconsistent Rule Selection

| Function | Purpose |
|----------|---------|
| `select_inconsistent_rules(evaluations, criteria, top_k)` | Select top-k rules by strict criteria (FPR ≥ 20%, FNR ≤ 5%, grammar-valid); `criteria` defaults to `SelectionCriteria()` |
| `select_with_relaxed_criteria(evaluations, top_k)` | Relaxed selection: any rule with mismatches, ranked by selection score |

**`SelectionCriteria` dataclass:** Configurable thresholds for `min_false_positive_rate`, `max_false_negative_rate`, `require_grammar_valid`, `min_n_mismatches`, and `max_complexity`.

### `counterfactual_hints.py` — L1-Minimal Perturbations

| Function | Purpose |
|----------|---------|
| `compute_minimal_perturbation(features, rule_text, feature_bounds, epsilon)` | Find smallest single-variable change that flips the rule verdict |
| `find_inconsistent_examples(rule_text, rule_type, dataset, mismatch_case_ids, feature_bounds)` | For each mismatch, compute perturbation hints |

**`InconsistentExample` dataclass:** `case_id`, `input_features`, `observed_label`, `rule_verdict`, `rule_text`, `rule_type`, `counterfactuals` (list of `CounterfactualCandidate`).

**`CounterfactualCandidate` dataclass:** `case_id`, `original_features`, `perturbed_features`, `changed_variable`, `original_value`, `perturbed_value`, `l1_distance`, `rule_verdict_before`, `rule_verdict_after`.

### `validation_report.py` — Report Generation

| Function | Purpose |
|----------|---------|
| `export_evaluations_csv(evaluations, path)` | Write full confusion matrix per rule to CSV |
| `export_selected_rules_csv(selected, path)` | Write selected rules with selection scores |
| `export_inconsistency_examples_csv(examples, path, feature_names)` | Per-rule mismatch details with counterfactual hints |
| `generate_selection_report(evaluations, selected, all_examples, system_info)` | Human-readable text summary |

## Key Formulas

### Decisiveness (SEAMS 2026 paper, Section 4)

$$D_G = 1 - \frac{N_{\text{mismatch}}}{N}$$

A mismatch occurs when the rule fires but the observed outcome contradicts the prediction.

### Confusion Matrix (for a fail rule)

| | Rule fires (predicts Fail) | Rule silent |
|---|---|---|
| **Outcome = Fail** | TP | FN |
| **Outcome = Pass** | **FP** (mismatch) | TN |

- $\text{FPR} = \text{FP} / (\text{FP} + \text{TN})$
- $\text{FNR} = \text{FN} / (\text{FN} + \text{TP})$

### Selection Criteria

Rules are selected for refinement when:
- FPR ≥ 20% (many spurious failures — rule incorrectly fires on passing cases)
- FNR ≤ 5% (doesn't miss real violations)
- Grammar-valid (passes `shared.grammar_validation`)

### Counterfactuals

For each mismatch, the smallest single-variable change that flips the rule verdict is computed (sorted by L1 distance). These hints guide the LLM toward evidence-based refinements.

## Output Files

| File | Contents |
|------|----------|
| `rule_evaluations.csv` | Full confusion matrix per rule |
| `selected_rules.csv` | Top-10 rules ranked by selection score |
| `inconsistency_examples_{rule_id}.csv` | Per-rule mismatch details with counterfactual hints |
| `selection_report.txt` | Human-readable summary |

## Usage

```python
from cbf_data.loader import load_dataset
from rule_validation.rule_evaluator import evaluate_all_rules
from rule_validation.rule_selector import select_with_relaxed_criteria

d_evolved = load_dataset("unicycle_static_obstacle", "robust_evolved", "evolved")
evaluations = evaluate_all_rules(candidates, d_evolved, d_evolved.feature_names)
selected = select_with_relaxed_criteria(evaluations, top_k=10)
```

## Where It's Used

| Consumer | How It's Used |
|----------|--------------|
| `run_pipeline.py` | Group C stage: evaluates candidates, selects top-k, generates reports |
| `tests/test_rule_validation.py` | Unit tests for evaluation, selection, and counterfactuals |

## Extensibility

- Adjust selection thresholds via `SelectionCriteria` dataclass
- Replace the single-variable perturbation strategy in `counterfactual_hints.py` with simulation-based falsification for stronger counterfactuals

## Dependencies

- **`pandas`** — DataFrame operations for report generation
- **Internal:** `cbf_data.loader` (dataset), `shared.grammar_validation` (grammar checks)
