# Tests — Minimality Analysis Test Suite

This folder contains 45 unit tests covering the minimality analysis pipeline (`minimality/` package). Tests are written using `pytest` and are configured via `pytest.ini` in the project root.

## Why This Test Suite Exists

The minimality analysis involves multiple interacting components (change extraction, bound analysis, justification checking, scoring, orchestration). Each component has specific correctness criteria that must be verified independently and in integration. This test suite ensures:
- Each component handles edge cases correctly
- The pipeline produces expected results end-to-end
- Scoring formulas behave as documented
- Regressions are caught immediately

## Test Configuration

```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

**Run all tests:**
```bash
python -m pytest
```

**Run a specific test file:**
```bash
python -m pytest tests/test_minimality_scorer.py -v
```

## Files

### `test_change_extractor.py` — Change Detection Tests

Tests the `ChangeExtractor` component with 9 tests across 2 test classes:

**`TestChangeExtraction`:**
- Tightening detection for `<` operators (negative delta)
- Tightening detection for `>` operators (positive delta)
- Loosening detection for both operator types
- No-change detection (identical rules)
- Multiple simultaneous changes

**`TestRelationMatching`:**
- Correct matching by `(variable, operator)`
- Handling of unmatched relations (different variables)
- Operator flipping for `Constant op Variable` patterns
- Magnitude computation correctness

### `test_bound_analyzer.py` — Severity Analysis Tests

Tests the `BoundAnalyzer` component with 9 tests across 2 test classes:

**`TestTighteningSeverity`:**
- Upper bound tightening severity (e.g., `ego_speed < 30` → `< 1`)
- Lower bound tightening severity
- Loosening returns zero severity
- No change returns zero severity
- Clamping to [0, 1] range

**`TestSeverityCategorization`:**
- `minor` classification (< 0.1)
- `moderate` classification (< 0.3)
- `severe` classification (< 0.7)
- `extreme` classification (≥ 0.7)

### `test_justification_checker.py` — Justification Tests

Tests the `JustificationChecker` component with 7 tests across 2 test classes:

**`TestJustificationChecking`:**
- Justified when evidence clusters near refined value
- Unjustified when evidence is far from refined value
- Handling of no relevant counterfactuals
- Handling of empty evidence

**`TestBoundaryAlignment`:**
- Majority-near-bound detection
- Direction alignment for tightenings
- Multi-variable evidence handling

### `test_minimality_scorer.py` — Scoring Tests

Tests the `MinimalityScorer` component with 7 tests across 2 test classes:

**`TestScoreComputation`:**
- Perfect score (1.0) for no changes
- Perfect score (1.0) for all justified changes
- Low score for unjustified high-magnitude tightenings
- Moderate score for mixed justified/unjustified
- Loosening not penalized in magnitude component

**`TestWeightedScoring`:**
- Custom weight behavior: emphasizing justification vs. magnitude produces different scores when the two components differ

### `test_minimality_validator.py` — End-to-End Pipeline Tests

Tests the `MinimalityValidator` orchestrator with 6 tests across 2 test classes:

**`TestEndToEndValidation`:**
- Justified refinement passes minimality check
- Unjustified refinement fails minimality check
- No-change rules always pass
- Multiple changes with mixed justification

**`TestValidationWithoutEvidence`:**
- All changes treated as unjustified when no evidence is provided

### `test_minimality_examples.py` — Integration/Regression Tests

Tests the example scenarios from `examples/minimality_examples.py` with 8 tests across 3 test classes:

**`TestJustifiedTightening`:**
- Score > 0.7. The justified tightening example passes the minimality threshold

**`TestUnjustifiedTightening`:**
- Score < 0.7. The over-tightening example fails the threshold
- Detects unjustified tightenings in the changes list

**`TestNoEvidence`:**
- Without evidence, all changes are unjustified
- Score reflects the lack of justification

### `__init__.py`

Empty init file marking the `tests/` directory as a Python package (required for pytest discovery with the project's import structure).

## Dependencies

- **`pytest`** — Test framework
- **`pytest-cov`** (optional) — Coverage reporting
- Internal: all `minimality/`, `data/`, `core/`, `parsers/` packages
