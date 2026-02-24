# Semantic — Semantic Validation Pipeline (Priority 2)

This package implements the **semantic validation layer** (Priority 2), which goes beyond syntax to verify that rules are *meaningful* — consistent with observed simulation data, free of contradictions with historical rules, and not overfitting to specific training cases.

## Why This Folder Exists

A rule can be syntactically perfect and within ODD bounds, yet still be **semantically broken**:
- It might predict "Pass" when simulations consistently show "Fail" (**inconsistency**)
- It might contradict an existing validated rule (**contradiction**)
- It might be fragile to small input perturbations (**overfitting**)

This package catches these deeper issues using simulation data and counterfactual analysis, as described in the SEAMS 2026 paper. It runs after Priority 1 (syntactic validation) has confirmed the rule is structurally sound.

## Folder Structure

```
semantic/
├── __init__.py                    # Re-exports all public classes
├── consistency_checker.py         # Rule vs. simulation data consistency
├── contradiction_checker.py       # Cross-rule contradiction detection
├── overfitting_detector.py        # Overfitting indicators (boundary sensitivity, constant specificity)
├── counterfactual_generator.py    # L1 minimal-change counterfactual search
└── semantic_validator.py          # Orchestrator combining all semantic checks
```

## Approach

The semantic validation pipeline is orchestrated by `SemanticValidator`, which coordinates three independent checkers. Each checker focuses on a different semantic property:

```
SemanticValidator.validate()
├── ConsistencyChecker       → Does the rule match observed outcomes?
├── ContradictionChecker     → Does the rule conflict with existing rules?
└── OverfittingDetector      → Is the rule too fragile / over-specific?
```

The overall decision: a rule **passes** if it is consistent (≥ 95%), contradiction-free, and has low overfitting risk (< 0.7).

## Files

### `consistency_checker.py` — Rule vs. Simulation Data

The `ConsistencyChecker` evaluates a rule against a `SimulationDataset` to check if rule verdicts match observed outcomes.

**Consistency table** (from paper Table 1):

| Rule Set | Rule Holds? | Verdict | Observed | Status |
|----------|-------------|---------|----------|--------|
| R_Pass | Yes | Pass | Pass | ✓ Consistent |
| R_Pass | Yes | Pass | Fail | ✗ Inconsistent |
| R_Fail | Yes | Fail | Fail | ✓ Consistent |
| R_Fail | Yes | Fail | Pass | ✗ Inconsistent |

**Algorithm:**
1. For each trace, evaluate the rule on the input vector
2. Determine the verdict based on the rule set type (`"Pass"` or `"Fail"`)
3. Compare verdict to observed outcome
4. Return consistency score (matches / total applicable) and list of `ConsistencyIssue` objects

> [!IMPORTANT]
> Returns `1.0` (vacuously consistent) when **no traces are applicable** — e.g., when rule conditions are never satisfied. This prevents false failures on unused rules.

### `contradiction_checker.py` — Cross-Rule Contradiction Detection

The `ContradictionChecker` ensures the current rule doesn't conflict with historical rules of the **opposite** type.

**From the paper:** *"No contradictions — there is no (x, y) such that a pass rule and a fail rule both hold on x."*

**Algorithm:**
1. Generate random test points within ODD bounds using `generate_test_points()` (default: 1000 points, **seeded RNG** for reproducibility)
2. For each test point, evaluate the current rule
3. If the current rule holds, check all historical rules of the opposite type
4. If any opposite-type rule also holds on the same point → **CONTRADICTION**
5. **Deduplicate** — only the first witness per rule pair is reported

**Reproducibility:** Uses `random.Random(seed)` (default seed=42) for deterministic test point generation.

**Input validation:** `current_rule_type` must be `"Pass"` or `"Fail"` — a `ValueError` is raised otherwise. Variables without bounds use a default range of `[-10, 10]` with a warning.

**Why random sampling?** Exhaustive enumeration over continuous variable spaces is impossible. Monte Carlo sampling provides good coverage while remaining computationally feasible.

### `counterfactual_generator.py` — L1 Minimal-Change Search

The `CounterfactualGenerator` implements the counterfactual analysis from the paper:

**From the paper:** *"L1 minimal-change search over the input space, which identifies the smallest modification that restores agreement between the rule verdict and the observed system behavior."*

**Algorithm:**
1. Start from an inconsistent input `x`
2. Incrementally expand the L1 radius (0.1 to 10.0 in steps of 0.1)
3. At each radius, generate 100 candidate inputs within the L1 ball using Dirichlet-distributed perturbations
4. Evaluate each candidate: if the rule verdict flips → return as counterfactual
5. Return the first (minimal) flip found

**Why L1 distance?** L1 (Manhattan distance) penalizes changes equally across dimensions, producing interpretable counterfactuals where the total change budget is split across variables.

**Why Dirichlet sampling?** The Dirichlet distribution naturally generates points on the simplex (non-negative values summing to a fixed total), ideal for distributing an L1 budget across variables.

### `overfitting_detector.py` — Overfitting Detection

The `OverfittingDetector` detects four types of overfitting, directly addressing Lesson 2 from the paper:

> *"LLMs tend to increase apparent safety by tightening bounds... this can over constrain the rule in a conservative way that is not correctly grounded in the provided ODD."*

| Indicator | Detection Method | Threshold (configurable) |
|-----------|-----------------|-------------------------|
| **Boundary sensitivity** | Average perturbation magnitude needed to flip verdict | < 0.5 (default, configurable) |
| **Overly specific constants** | Constants with > 1 decimal place precision (heuristic) | Any count > 0 |
| **Train/test gap** | Consistency score difference between training and test data | > 0.15 (default, configurable) |
| **Unnecessary restrictions** | Try removing each predicate; if consistency doesn't drop, flag it | Any removable predicate |

> [!NOTE]
> `_check_train_test_gap` now uses `self.rule_set_type` (passed from `SemanticValidator`) instead of hardcoding `"Pass"`. This ensures Fail-set rules are evaluated with correct semantics.

Also includes `extract_constants()` — a helper that recursively extracts all numeric constants from a rule tree.


### `semantic_validator.py` — Orchestrator

The `SemanticValidator` coordinates all semantic checks in a 3-step pipeline, now fully configurable via a `config` dictionary:

1. **Consistency** — Check rule against simulation data (default threshold: 0.95, configurable via `consistency_threshold`)
2. **Contradiction** — Check against historical rules using 1000 random test points
3. **Overfitting** — Detect overfitting indicators if counterfactual evidence is available (risk threshold: 0.7, configurable via `overfitting_threshold`; train/test gap threshold configurable via `train_test_gap_threshold`)

**Overall decision:**

```python
passed = is_consistent and not has_contradictions and overfitting_risk < threshold_overfitting
```

All thresholds can be set via the `config` argument to `SemanticValidator.validate()`. This enables fine-tuning for different domains or stricter/looser validation as needed.

**Serialization:** `SemanticValidationResult` supports `to_dict()` and `to_json()` for persistence. All nested types (`ConsistencyIssue`, `ContradictionIssue`, `OverfittingIndicator`) also support `to_dict()`.

### `__init__.py` — Package Exports

Re-exports all public classes:
```python
from semantic import (
    ConsistencyChecker, ContradictionChecker, OverfittingDetector,
    CounterfactualGenerator, SemanticValidator,
)
```

## Usage

```python
from semantic import SemanticValidator, ConsistencyChecker
from data import SimulationDataset, SimulationTrace

# Build simulation dataset
traces = [
    SimulationTrace({"dist_front": 3.0, "ego_speed": 10.0}, "Fail"),
    SimulationTrace({"dist_front": 50.0, "ego_speed": 5.0}, "Pass"),
]
dataset = SimulationDataset(traces=traces)

# Example config for custom thresholds
config = {
    "consistency_threshold": 0.98,
    "overfitting_threshold": 0.6,
    "train_test_gap_threshold": 0.10,
}

# Run full semantic validation
validator = SemanticValidator(rule_set_type="Fail", variable_bounds=config.variable_bounds)
result = validator.validate(
    rule=parsed_rule,
    training_data=dataset,
    config=config
)
print(result.passed_validation)
print(result.consistency_score)
for ind in result.overfitting_indicators:
    print(ind)
```

## Where It's Used

| Consumer | How It's Used |
|----------|--------------|
| `run_pipeline.py` | Layer 2 semantic validation on selected rules (exports JSON) |
| `examples/semantic_examples.py` | Full semantic validation demo |
| `cbf_data/adapter.py` | Converts CBF datasets for use with semantic checkers |
| `tests/test_semantic.py` | Comprehensive unit tests for all checkers |

## Dependencies

- **`numpy`** — Dirichlet sampling in counterfactual generation, statistical computations
- **Internal:** `core.schema`, `core.config`, `data.*` (all result structures)
