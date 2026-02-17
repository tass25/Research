# Minimality — Change Minimality Analysis (Priority 3)

This package implements **Priority 3** from the paper: detecting overly conservative refinements where an LLM tightens bounds more than justified by the counterfactual evidence. It is the core contribution for ensuring that rule refinements are *minimal* — changing only what the evidence supports.

## Why This Exists

LLMs have a well-documented tendency to over-tighten safety bounds (Lesson 2 from the paper). For example:
- Original rule: `ego_speed < 30`
- Evidence suggests boundary near 25
- LLM refines to: `ego_speed < 1` ← **Unjustified!** Tightened far beyond what evidence supports

This package catches such cases by comparing each relation-level change against counterfactual evidence, computing whether the tightening is *justified* by the data.

## Approach

The minimality analysis follows a **5-stage pipeline**, orchestrated by `MinimalityValidator`:

```
MinimalityValidator.validate()
│
├── 1. ChangeExtractor.extract_changes()      → Detect what changed
├── 2. JustificationChecker.check_justification()  → Is each change evidence-backed?
├── 3. MinimalityScorer.compute_score()        → Quantify overall minimality
├── 4. Categorize changes                      → Flag unjustified tightenings/loosenings
└── 5. Pass/fail decision                      → Score ≥ threshold?
```

## Files

### `change_extractor.py` — Relation-Level Change Detection

The `ChangeExtractor` identifies what changed between an original and refined rule at the **individual relation level**.

**Algorithm:**
1. Recursively extract all `Relation` objects from both rules
2. Parse each relation into `(variable, operator, constant)` triples
3. Match relations by `(variable, operator)` — same variable and same operator
4. For matched pairs, compute:
   - `delta = refined_constant - original_constant`
   - `magnitude = |delta| / |original_constant|` (relative change)
   - `change_type` = tightening, loosening, or unchanged

**Change classification logic:**

| Operator | Negative delta | Positive delta | Meaning |
|----------|---------------|----------------|---------|
| `<`, `<=` | Tightening ↓ | Loosening ↑ | Smaller upper bound = tighter |
| `>`, `>=` | Loosening ↓ | Tightening ↑ | Larger lower bound = tighter |
| `=`, `!=` | Tightening | Tightening | Any change to equality is considered tightening |

**Operator flipping:** Handles both `Variable op Constant` and `Constant op Variable` by flipping the operator (example, `5 > x` becomes `x < 5`).

### `bound_analyzer.py` — Tightening Severity Analysis

The `BoundAnalyzer` computes how severe a tightening is relative to the ODD bounds:

**Severity formula** (for upper bounds like `variable < constant`):
```
original_range = original_constant - ODD_lower_bound
refined_range  = refined_constant  - ODD_lower_bound
severity = (original_range - refined_range) / original_range
```

**Example:**
- Original: `ego_speed < 30`, ODD: `[0, 50]`
- Refined: `ego_speed < 1`
- `original_range = 30 - 0 = 30`, `refined_range = 1 - 0 = 1`
- `severity = (30 - 1) / 30 = 0.97` → **97% of the available range was eliminated!**

Severity categories: `minor` (< 0.1), `moderate` (< 0.3), `severe` (< 0.7), `extreme` (≥ 0.7).

### `justification_checker.py` — Evidence-Based Justification

The `JustificationChecker` determines whether a bound change is supported by counterfactual evidence.

**Justification criteria** (checked in order):

1. **Clustering check** — Do counterfactual values cluster near the refined constant?
   - Computes average distance from counterfactual values to the new bound
   - Threshold: distance must be within 50% of the change magnitude
   - If yes → **Justified** (evidence supports the new boundary position)

2. **Boundary alignment check** — Do a majority of counterfactuals concentrate near the new bound?
   - Counts how many counterfactual values fall within 50% of the delta from the refined constant
   - If ≥ 50% of counterfactuals are near the bound → **Justified**

3. **Not justified** — If neither check passes, the change is flagged as unjustified with the average distance to evidence reported

### `minimality_scorer.py` — Quantitative Scoring

The `MinimalityScorer` computes a single minimality score from 0.0 (bad) to 1.0 (perfectly minimal):

**Default scoring formula** (`compute_score()`):
```
justified_weight = justified_count / total_count
magnitude_penalty = 1 - avg(magnitude of unjustified tightenings)
score = (justified_weight + magnitude_penalty) / 2
```

| Score Range | Interpretation |
|-------------|---------------|
| 1.0 | All changes minimal and justified |
| 0.7 – 0.9 | Mostly justified (good) |
| 0.4 – 0.7 | Mixed justification (questionable) |
| 0.0 – 0.4 | Mostly unjustified (bad) |

**Custom weighted scoring** (`compute_weighted_score()`):
```
score = (justification_weight × justified_ratio) + (magnitude_weight × magnitude_penalty)
```
Allows emphasizing justification vs. magnitude based on domain requirements.

**Key design decision:** Loosening changes are NOT penalized in the magnitude component. Loosening makes rules less restrictive, which is generally safe (the concern is over-tightening, not over-loosening).

### `minimality_validator.py` — Pipeline Orchestrator

The `MinimalityValidator` coordinates the full pipeline:

1. **Extract changes** using `ChangeExtractor`
2. **Check justifications** for each change using `JustificationChecker` (if counterfactual evidence is provided)
3. **Compute score** using `MinimalityScorer`
4. **Categorize** unjustified tightenings and loosenings
5. **Decide pass/fail** based on score ≥ threshold (default: 0.7)

Returns a `MinimalityResult` with all details.

**No evidence mode:** If no counterfactual evidence is provided, all changes are treated as unjustified. This is intentional — without evidence, there's no basis to consider any change justified.

### `__init__.py` — Package Exports

Re-exports all public classes: `ChangeExtractor`, `BoundAnalyzer`, `JustificationChecker`, `MinimalityScorer`, `MinimalityValidator`.

## Dependencies

- Python standard library only (`typing`, `dataclasses`)
- Internal: `core.schema`, `core.types`, `data.minimality_result`, `data.counterfactual_evidence`
