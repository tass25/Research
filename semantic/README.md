# Semantic — Semantic Validation Pipeline

This package implements the **semantic validation layer** (Priority 2), which goes beyond syntax to verify that rules are *meaningful* — consistent with observed simulation data, free of contradictions with historical rules, and not overfitting to specific training cases.

## Why This Exists

A rule can be syntactically perfect and within ODD bounds, yet still be **semantically broken**:
- It might predict "Pass" when simulations consistently show "Fail" (inconsistency)
- It might contradict an existing validated rule (contradiction)
- It might be fragile to small input perturbations (overfitting)

This package catches these deeper issues using simulation data and counterfactual analysis, as described in the SEAMS 2026 paper.

## Approach

The semantic validation pipeline is orchestrated by `SemanticValidator`, which coordinates three independent checkers. Each checker focuses on a different semantic property:

```
SemanticValidator.validate()
├── ConsistencyChecker       → Does the rule match observed outcomes?
├── ContradictionChecker     → Does the rule conflict with existing rules?
└── OverfittingDetector      → Is the rule too fragile / over-specific?
```

The overall decision: a rule **passes** if it is consistent (≥95%), contradiction-free, and has low overfitting risk (<0.7).

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
4. Return consistency score (matches / total applicable) and list of issues

**Why `rule_set_type`?** Rules belong to either R_Pass (conditions for passing) or R_Fail (conditions for failing). The same rule evaluation result means different things depending on which set the rule belongs to.

### `contradiction_checker.py` — Cross-Rule Contradiction Detection

The `ContradictionChecker` ensures the current rule doesn't conflict with historical rules of the **opposite** type.

**From the paper:** *"No contradictions — there is no (x, y) such that a pass rule and a fail rule both hold on x."*

**Algorithm:**
1. Generate random test points within ODD bounds using `generate_test_points()`
2. For each test point, evaluate the current rule
3. If the current rule holds, check all historical rules of the opposite type
4. If any opposite-type rule also holds → **CONTRADICTION**

**Why random sampling?** Exhaustive enumeration over continuous variable spaces is impossible. Monte Carlo sampling with 1000 test points provides good coverage while remaining computationally feasible.

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

**Why Dirichlet sampling?** The Dirichlet distribution naturally generates points on the simplex (non-negative values summing to a fixed total), making it ideal for distributing an L1 budget across variables.

### `overfitting_detector.py` — Overfitting Detection

The `OverfittingDetector` detects four types of overfitting, directly addressing Lesson 2 from the paper:

> *"LLMs tend to increase apparent safety by tightening bounds... this can over constrain the rule in a conservative way that is not correctly grounded in the provided ODD."*

| Indicator | Detection Method | Threshold |
|-----------|-----------------|-----------|
| **Boundary sensitivity** | Average perturbation magnitude needed to flip verdict | < 0.5 → flagged |
| **Overly specific constants** | Constants with > 1 decimal place precision (heuristic) | Any count > 0 → flagged |
| **Train/test gap** | Consistency score difference between training and test data | > 15% drop → flagged |
| **Unnecessary restrictions** | Placeholder for future expansion | — |

Also includes a helper function `extract_constants()` that recursively extracts all numeric constants from a rule tree.

### `semantic_validator.py` — Orchestrator

The `SemanticValidator` coordinates all semantic checks in a 3-step pipeline:

1. **Consistency** — Check rule against simulation data (threshold: 95%)
2. **Contradiction** — Check against historical rules using 1000 random test points
3. **Overfitting** — Detect overfitting indicators if counterfactual evidence is available

**Overall decision:** `passed = consistent AND contradiction-free AND overfitting_risk < 0.7`

### `__init__.py` — Package Exports

Re-exports all public classes.

## Dependencies

- **`numpy`** — Used for Dirichlet sampling in counterfactual generation and statistical computations in overfitting detection
- Internal: `core.schema`, `data.*`
