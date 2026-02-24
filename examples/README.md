# Examples — Demonstration Scripts

Executable scripts that demonstrate each stage of the validation pipeline.

## Why This Folder Exists

The pipeline has three priority groups (syntactic, semantic, minimality) with many interacting modules. These self-contained demo scripts let users (and reviewers) run each stage independently, see concrete inputs and outputs, and verify the system works end-to-end without setting up datasets.

## Folder Structure

```
examples/
├── __init__.py              # Package init (empty)
├── paper_examples.py        # Priority 1 — Syntactic parsing + grammar enforcement
├── semantic_examples.py     # Priority 2 — Semantic validation
└── minimality_examples.py   # Priority 3 — Minimality analysis
```

## Files

### `paper_examples.py` — Grammar Enforcement Demo (Priority 1)

Demonstrates the core parsing and syntactic validation pipeline using examples from the SEAMS 2026 paper.

**What it does:**
1. Initialises the `OperationalRuleParser` with `DEFAULT_ADS_CONFIG`
2. Runs six test cases covering:
   - Valid rules from the paper (`r1` and its refined `r1★`)
   - Simple disjunction
   - Unicode operator normalisation (`≤`)
   - Unknown variable (`unknown_var`) → expected parse failure
   - Out-of-bounds constant (`ego_speed < 200`) → expected validation failure
3. For successfully parsed rules, evaluates them against a sample environment

**Run:**
```bash
python -m examples.paper_examples
```

### `semantic_examples.py` — Semantic Validation Demo (Priority 2)

Demonstrates the semantic validation pipeline: consistency checking, contradiction detection, and overfitting analysis.

**What it does:**
1. Creates a sample `SimulationDataset` with two traces (one Pass, one Fail)
2. Parses a rule: `(dist_front < 5) AND (ego_speed > 0)`
3. Runs the `SemanticValidator` with the rule against the dataset
4. Prints the full `SemanticValidationResult` summary

**Run:**
```bash
python -m examples.semantic_examples
```

### `minimality_examples.py` — Minimality Analysis Demo (Priority 3)

Demonstrates the minimality analysis pipeline with three scenarios covering the full spectrum of refinement quality.

| Example | Scenario | Expected Result |
|---------|----------|----------------|
| 1. Justified Tightening | `dist_front < 5` → `dist_front < 4.1` with evidence near 4.0 | PASS — change supported by counterfactual evidence |
| 2. Unjustified Tightening | `ego_speed < 30` → `ego_speed < 1` with evidence near 25 | FAIL — drastic tightening far beyond evidence |
| 3. No Evidence | `dist_front < 10` → `dist_front < 8` without any evidence | FAIL — no evidence means no justification |

Each example constructs complete `CounterfactualEvidence` objects with realistic counterfactual pairs.

**Run:**
```bash
python -m examples.minimality_examples
```

## Where It's Used

| Consumer | How It's Used |
|----------|--------------|
| `tests/test_minimality_examples.py` | Regression tests that programmatically verify example outputs |
| Paper reviewers | Run `python -m examples.<script>` to reproduce results |
| Users / developers | Quick validation that the pipeline works after installation |

## Dependencies

- **Internal:** `core`, `parsers`, `data`, `semantic`, `minimality`
- **External:** `lark`, `numpy`
