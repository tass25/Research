# Rule Inference — Group B

Machine-learning-based extraction of candidate operational rules from simulation data.

## Why This Folder Exists

To close the loop between simulation and formal safety rules, we need a way to **automatically extract** interpretable rules from data. This package trains decision trees and random forests on **D_legacy** (the legacy/vanilla controller dataset), then converts the learned splits into human-readable DNF (Disjunction of Conjunctions) rules. These candidates are the starting point for Group C's evaluation and the LLM refinement pipeline.

## Folder Structure

```
rule_inference/
├── __init__.py            # Package init
├── tree_extractor.py      # Decision tree path → DNF rules, depth sweep
├── forest_extractor.py    # Random forest top-k tree extraction
├── grammar_checker.py     # Thin wrapper → shared.grammar_validation
└── rule_export.py         # CSV export and inference reports
```

## Files

### `tree_extractor.py` — Decision Tree Rule Extraction

**Key classes and functions:**

| Name | Purpose |
|------|---------|
| `CandidateRule` | Dataclass holding `rule_id`, `rule_text`, `rule_type` (pass/fail), `train_accuracy`, `val_accuracy`, `train_f1`, `val_f1`, `complexity`, `support`, `confidence`, `source_model`, `feature_importances` |
| `extract_rules_from_tree(dataset, max_depth, ...)` | Train a `DecisionTreeClassifier` on a `SimulationDataset`, extract all root-to-leaf paths as `CandidateRule` objects; returns `(candidates, fitted_clf)` |
| `extract_dnf_rules(dataset, max_depth, ...)` | Merge per-class leaf paths into pass-DNF and fail-DNF rules; returns `(List[CandidateRule], DecisionTreeClassifier)` |
| `sweep_depths(dataset, depths, ...)` | Train decision trees at multiple depths (e.g., `[2, 3, 4, 5, None]`), extract and deduplicate all candidates |

### `forest_extractor.py` — Random Forest Rule Extraction

| Function | Purpose |
|----------|---------|
| `extract_rules_from_forest(dataset, n_estimators, ...)` | Train a `RandomForestClassifier`, select top-k trees by accuracy, extract rules from each |
| `extract_high_confidence_rules(dataset, ...)` | Filter forest rules by minimum confidence (≥ 0.75) and support (≥ 10 samples), deduplicate |

**Top-k tree selection:** Trees are ranked by accuracy on the training data, and only the top-k (default: 5) are used for rule extraction, discarding noisy estimators.

### `grammar_checker.py` — Grammar G Wrapper

Thin re-export of `shared.grammar_validation` into the `rule_inference` namespace via `check_grammar_compliance()`. Ensures inference-time grammar checks use the same logic as evaluation-time.

### `rule_export.py` — CSV & Report Generation

| Function | Purpose |
|----------|---------|
| `export_candidates_to_csv(candidates, output_path, allowed_variables)` | Write all candidates to CSV with 15 columns: rule_id, rule_text, rule_type, train_accuracy, val_accuracy, train_f1, val_f1, complexity, support, confidence, source_model, grammar_valid, dnf_valid, variables_used, n_predicates |
| `generate_inference_report(candidates, dataset_info, allowed_variables)` | Generate human-readable summary: counts by source/type, top fail rules, grammar compliance stats |

Also exports `validate_dnf_structure()` from `grammar_checker.py` for DNF structural validation.

## Pipeline Flow

```
D_legacy (from cbf_data/loader.py)
  │
  ├── Decision Tree (depths 2–5, unlimited)
  │     ├── individual path rules (CandidateRule objects)
  │     └── merged DNF (pass / fail)
  │
  ├── Random Forest (100 estimators, top-5 trees)
  │     ├── individual path rules
  │     └── merged DNF per tree
  │
  └── High-confidence filter (confidence ≥ 0.75, support ≥ 10)
        └── deduplicated rules
                │
                ▼
        candidate_rules.csv + inference_report.txt
```

## Grammar Compliance

All extracted rules are checked against grammar G (via `shared.grammar_validation`):

```
Rule  → Disj
Disj  → Conj  (OR  Conj)*
Conj  → Rel   (AND Rel)*
Rel   → var rop const
rop   → < | <= | > | >= | = | !=
```

Rules that use arithmetic expressions or unknown variable names are flagged as grammar-invalid in the CSV output.

## Output Files

| File | Contents |
|------|----------|
| `candidate_rules.csv` | All unique candidates with grammar validity flags |
| `inference_report.txt` | Summary statistics and top fail rules |

## Usage

```python
from cbf_data.loader import load_dataset
from rule_inference.tree_extractor import sweep_depths, extract_dnf_rules
from rule_inference.forest_extractor import extract_rules_from_forest

# Decision tree sweep
d_legacy = load_dataset("unicycle_static_obstacle", "robust_evolved", "legacy")
dt_candidates = sweep_depths(d_legacy, depths=[2, 3, 4, 5, None])

# Random forest
rf_candidates, rf_clf = extract_rules_from_forest(d_legacy, n_estimators=100)

# Export
from rule_inference.rule_export import export_candidates_to_csv
export_candidates_to_csv(dt_candidates + rf_candidates, "output/candidates.csv", d_legacy.feature_names)
```

## Where It's Used

| Consumer | How It's Used |
|----------|--------------|
| `run_pipeline.py` | Group B stage: trains models, extracts candidates, exports CSV |
| `rule_validation/` (Group C) | Receives `CandidateRule` objects for evaluation on D_evolved |
| `tests/test_rule_inference.py` | Unit tests for all extraction functions |

## Extensibility

- Add new learners (e.g., gradient-boosted trees) by following the `CandidateRule` dataclass contract
- Grammar validation is centralized in `shared/grammar_validation.py`

## Dependencies

- **`scikit-learn`** — `DecisionTreeClassifier`, `RandomForestClassifier`
- **`pandas`** — Data manipulation
- **Internal:** `cbf_data.loader` (dataset loading), `shared.grammar_validation` (grammar checks)
