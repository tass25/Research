# Rule Inference — Group B

Machine-learning-based extraction of candidate operational rules from simulation data.

## Purpose

Trains decision trees and random forests on **D_legacy** to extract interpretable
safety rules in DNF (Disjunction of Conjunctions) form, then validates them
against the grammar *G* defined in the SEAMS 2026 paper.

## Files

| File | Description |
|------|-------------|
| `tree_extractor.py` | `extract_rules_from_tree()`, `extract_dnf_rules()`, `sweep_depths()` — Decision tree path extraction and DNF merging |
| `forest_extractor.py` | `extract_rules_from_forest()`, `extract_high_confidence_rules()` — Random forest top-*k* tree selection |
| `grammar_checker.py` | Thin wrapper that re-exports `shared.grammar_validation` — grammar G compliance checks |
| `rule_export.py` | `export_candidates_to_csv()`, `generate_inference_report()` — CSV and text report generation |
| `__init__.py` | Package init |

## Grammar Compliance

All extracted rules are checked against grammar G (via the **shared** utility
`shared.grammar_validation`):

```
Rule  → Disj
Disj  → Conj  (OR  Conj)*
Conj  → Rel   (AND Rel)*
Rel   → var rop const
rop   → < | <= | > | >= | = | !=
```

Rules that use arithmetic expressions or unknown variable names are flagged.

## Pipeline

```
D_legacy
  │
  ├── Decision Tree (depths 2–5, unlimited)
  │     ├── individual path rules
  │     └── merged DNF (pass / fail)
  │
  ├── Random Forest (100 estimators, top-5 trees)
  │     ├── individual path rules
  │     └── merged DNF per tree
  │
  └── High-confidence filter (confidence ≥ 0.75, support ≥ 10)
        └── deduplicated rules
```

## Output

- `candidate_rules.csv` — all unique candidates with grammar validity flags
- `inference_report.txt` — summary statistics and top fail rules

## Quick Start

```python
from cbf_data.loader import load_dataset
from rule_inference.tree_extractor import sweep_depths

d_legacy = load_dataset("unicycle_static_obstacle", "robust_evolved", "legacy")
candidates = sweep_depths(d_legacy, depths=[2, 3, 4])
```

## Extensibility

- Add new learners (e.g., gradient-boosted trees) by following the
  `CandidateRule` dataclass contract in `tree_extractor.py`.
- Grammar validation is centralised in `shared/grammar_validation.py`.
