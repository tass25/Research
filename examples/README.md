# Examples — Demonstration Scripts

This folder contains executable scripts that demonstrate the system's capabilities. Each script is self-contained and can be run independently to see a specific validation pipeline in action.

## Files

### `paper_examples.py` — Grammar Enforcement Demo (Part 1)

Demonstrates the core parsing and syntactic validation pipeline using examples from the SEAMS 2026 paper.

**What it does:**
1. Initializes the `OperationalRuleParser` with `DEFAULT_ADS_CONFIG`
2. Runs six test cases covering:
   - ✅ Valid rules from the paper (e.g., `r1` and its refined `r1★`)
   - ✅ Simple disjunction
   - ✅ Unicode operator normalization (`≤`)
   - ❌ Unknown variable (`unknown_var`) → expected parse failure
   - ❌ Out-of-bounds constant (`ego_speed < 200`) → expected validation failure
3. For successfully parsed rules, evaluates them against a sample environment

**Run:**
```bash
python -m examples.paper_examples
```

### `semantic_examples.py` — Semantic Validation Demo (Part 2)

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

### `minimality_examples.py` — Minimality Analysis Demo (Part 3)

Demonstrates the minimality analysis pipeline with three scenarios that cover the full spectrum of refinement quality.

**What it does:**

| Example | Scenario | Expected Result |
|---------|----------|----------------|
| 1. Justified Tightening | `dist_front < 5` → `dist_front < 4.1` with evidence near 4.0 | PASS — change is supported by counterfactual evidence |
| 2. Unjustified Tightening | `ego_speed < 30` → `ego_speed < 1` with evidence near 25 | FAIL — drastic tightening far beyond evidence |
| 3. No Evidence | `dist_front < 10` → `dist_front < 8` without any evidence | FAIL — no evidence means no justification |

Each example constructs complete `CounterfactualEvidence` objects with realistic counterfactual pairs (original/counterfactual inputs, outcomes, perturbations).

**Run:**
```bash
python -m examples.minimality_examples
```

## Dependencies

- All project packages (`core`, `parsers`, `data`, `semantic`, `minimality`)
- External: `lark`, `numpy`
