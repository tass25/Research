# Data — Result Structures & Evidence Models

This package defines all data structures used to represent simulation traces, counterfactual evidence, and validation results. It serves as the **shared data contract** between the `semantic/` and `minimality/` analysis pipelines.

## Why This Exists

Validation involves multiple stages (consistency checking, counterfactual analysis, minimality scoring), each producing structured results. Rather than scattering data definitions across modules, this package centralizes them, ensuring a single source of truth for all input/output data shapes.

## Files

### `simulation_trace.py` — Simulation Input Data

Defines the raw simulation data that drives semantic validation:

- **`SimulationTrace`** — A single simulation run containing:
  - `input_vector`: Variable assignments (e.g., `{"ego_speed": 25.0, "dist_front": 10.0}`)
  - `observed_outcome`: What actually happened (`"Pass"` or `"Fail"`)
  - `timestamp`: Optional execution timestamp
  - `metadata`: Extensible metadata dict

- **`SimulationDataset`** — A collection of traces with utility methods:
  - `filter_by_outcome()` — Filter traces by Pass/Fail
  - `get_all_variables()` — Extract all variable names used across traces
  - `split_train_test()` — Split into training/test sets for overfitting detection

**Why frozen?** `SimulationTrace` is frozen (immutable) because simulation data should never be modified after collection — it represents observed ground truth.

### `counterfactual_evidence.py` — Counterfactual Pairs

Implements the counterfactual analysis framework from the paper:

- **`CounterfactualPair`** — Links an original input `x` to a counterfactual `x'`:
  - `original_input` / `original_outcome` — The inconsistent case
  - `counterfactual_input` / `counterfactual_outcome` — The minimally-modified case
  - `perturbation` — The delta `Δ = x' - x`
  - `perturbation_magnitude()` — L1 distance between inputs
  - `get_changed_variables()` — Which variables were perturbed

- **`CounterfactualEvidence`** — Collection of pairs for a specific rule:
  - `get_decision_boundary_features()` — Identifies which variables are on the decision boundary (commonly perturbed across pairs)

**Why this matters:** Counterfactual evidence is the key to distinguishing justified refinements (grounded in boundary analysis) from unjustified tightenings (LLM over-conservatism).

### `semantic_result.py` — Semantic Validation Results

Contains all result types from the semantic validation pipeline:

- **`ConsistencyIssue`** — A single mismatch between rule verdict and observed outcome
- **`ContradictionIssue`** — A contradiction found between current and historical rules, including the conflicting input point and explanation
- **`OverfittingIndicator`** — Evidence of overfitting with type classification (`"boundary_sensitive"`, `"overly_specific"`, `"train_test_gap"`), severity score (0–1), and affected variables
- **`SemanticValidationResult`** — Complete semantic validation output aggregating consistency score, contradictions, overfitting risk, and a `passed_validation` decision

### `minimality_result.py` — Minimality Analysis Results

Contains result types for the minimality analysis pipeline:

- **`RelationChange`** — A single change in one relation between original and refined rules:
  - Tracks variable, operator, original/refined constants, delta, change type (`"tightening"`, `"loosening"`, `"unchanged"`), magnitude, and justification status
  - Provides a rich `__str__()` with direction arrows and justification marks

- **`MinimalityResult`** — Complete minimality analysis output:
  - `overall_score`: Minimality score (0.0 = bad, 1.0 = minimal)
  - `relation_changes`: All detected changes
  - `unjustified_tightenings` / `unjustified_loosenings`: Flagged changes
  - `passed_minimality`: Whether the score exceeds the threshold
  - `summary()`: Human-readable formatted report

### `__init__.py` — Package Exports

Re-exports all public data classes for convenient importing:
```python
from data import SimulationTrace, CounterfactualPair, RelationChange, MinimalityResult
```

## Dependencies

- Python standard library only (`dataclasses`, `typing`)
