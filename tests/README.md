# Tests — Full Project Test Suite

**312 unit tests** across 16 test files covering all production packages. Written with `pytest`, configured via `pyproject.toml`.

## Why This Folder Exists

Each production package (`core`, `data`, `parsers`, `validators`, `shared`, `semantic`, `minimality`, `rule_inference`, `rule_validation`, `cbf_data`) has independent correctness criteria. This suite ensures every component handles edge cases correctly, the pipeline produces expected end-to-end results, scoring formulas behave as documented, and regressions are caught immediately. Current line coverage: **82.46%**.

## Folder Structure

```
tests/
├── __init__.py                       # Package init (pytest discovery)
├── test_bound_analyzer.py            # 11 tests — BoundAnalyzer severity
├── test_cbf_data.py                  # 28 tests — Loader, metadata, adapter
├── test_change_extractor.py          # 16 tests — Change detection
├── test_config_and_logging.py        # 20 tests — Config loading, logging setup
├── test_core.py                      # 39 tests — Types, schema, config
├── test_data_layer.py                # 17 tests — SimulationTrace, results
├── test_grammar_validation.py        # 22 tests — Grammar validation utilities
├── test_justification_checker.py     #  4 tests — Justification checking
├── test_minimality_examples.py       #  3 tests — Example regression tests
├── test_minimality_scorer.py         #  6 tests — Score computation
├── test_minimality_validator.py      #  5 tests — End-to-end minimality
├── test_parser.py                    # 19 tests — Lark parser
├── test_rule_inference.py            # 21 tests — Tree/forest extraction, export
├── test_rule_validation.py           # 41 tests — Evaluation, selection, reports
├── test_semantic.py                  # 30 tests — Consistency, contradiction, overfitting
└── test_validators.py                # 30 tests — Base, preparse, structure, bounds
```

## Files

### `test_core.py` — Core Types, Schema, Config (39 tests)

Tests `core/types.py`, `core/schema.py`, and `core/config.py`:
- `Relation`, `Conjunction`, `Disjunction` construction and string representations
- Operator normalisation (`<=` → `<=`, `≤` → `<=`)
- `RuleSchema` validation (valid variables, operators, variable bounds)
- `DEFAULT_ADS_CONFIG` integration
- Edge cases: empty rules, unknown operators, nested structures

### `test_config_and_logging.py` — Config Loader & Logging (20 tests)

Tests `core/config_loader.py` and `core/logging_config.py`:
- YAML config loading from `config.yaml`
- `ThresholdConfig`, `PipelineConfig` dataclass construction
- `load_config()`, `load_pipeline_config()` roundtrips
- `setup_logging()`, `get_logger()` with coloured output
- Error handling for missing files, invalid YAML

### `test_data_layer.py` — Data Layer (17 tests)

Tests `data/simulation_trace.py`, `data/counterfactual_evidence.py`, `data/semantic_result.py`, `data/minimality_result.py`:
- `SimulationTrace` and `SimulationDataset` construction
- `CounterfactualEvidence` with perturbation and pair data
- `SemanticValidationResult` aggregation
- `MinimalityResult` scoring and verdict

### `test_parser.py` — Lark Parser (19 tests)

Tests `parsers/lark_parser.py`:
- Simple and compound rule parsing
- Arithmetic expressions, nested parentheses
- Disjunction/conjunction precedence
- Unicode operator normalisation
- Expected parse failures for invalid syntax
- Integration with `DEFAULT_ADS_CONFIG`

### `test_validators.py` — Syntactic Validators (30 tests)

Tests `validators/base.py`, `validators/preparse.py`, `validators/structure.py`, `validators/absolute_bounds.py`:
- `BaseValidator` interface compliance
- Pre-parse character/pattern rejection
- Structure depth, width, nesting limits
- Absolute bounds checking against `RuleSchema` variable ranges
- Boundary values (edge of valid range)
- Disjunction-level validation

### `test_grammar_validation.py` — Grammar Utilities (22 tests)

Tests `shared/grammar_validation.py`:
- `validate_rule_grammar()` on valid/invalid rule strings
- `is_grammar_valid()` boolean wrapper
- `extract_rule_components()` — variable names, operators, constants
- `normalise_rule_text()` — whitespace/operator canonical form
- Edge cases: empty strings, Unicode, very long rules

### `test_semantic.py` — Semantic Validation (30 tests)

Tests `semantic/consistency_checker.py`, `semantic/contradiction_checker.py`, `semantic/overfitting_detector.py`, `semantic/counterfactual_generator.py`, `semantic/semantic_validator.py`:
- Consistency scores against simulation traces
- Contradiction detection between rule pairs
- Overfitting detection (rules with 100% false-positive rate)
- Counterfactual generation from perturbation hints
- `SemanticValidator` orchestrator end-to-end

### `test_bound_analyzer.py` — Bound Severity (11 tests)

Tests `minimality/bound_analyzer.py`:
- Tightening severity for upper/lower bounds
- Loosening returns zero severity
- Unknown variable fallback behaviour
- Percentage change calculation
- Severity categorisation: minor, moderate, severe, extreme

### `test_change_extractor.py` — Change Detection (16 tests)

Tests `minimality/change_extractor.py`:
- Tightening/loosening detection for `<`, `>`, `<=`, `>=`
- No-change detection (identical rules)
- Multiple simultaneous changes
- Relation matching by `(variable, operator)`
- Unmatched relations, operator flipping, magnitude computation

### `test_justification_checker.py` — Justification (4 tests)

Tests `minimality/justification_checker.py`:
- Justified when evidence clusters near refined value
- Unjustified when evidence is far from refined value
- Empty evidence handling

### `test_minimality_scorer.py` — Scoring (6 tests)

Tests `minimality/minimality_scorer.py`:
- Perfect score (1.0) for no changes / all justified changes
- Low score for unjustified high-magnitude tightenings
- Mixed justified/unjustified scoring
- Loosening not penalised

### `test_minimality_validator.py` — E2E Minimality (5 tests)

Tests `minimality/minimality_validator.py`:
- Justified refinement passes minimality check
- Unjustified refinement fails
- No-change rules always pass
- Missing evidence treated as unjustified

### `test_minimality_examples.py` — Example Regression (3 tests)

Verifies the three scenarios from `examples/minimality_examples.py` produce expected score ranges.

### `test_rule_inference.py` — Rule Inference (21 tests)

Tests `rule_inference/tree_extractor.py`, `rule_inference/forest_extractor.py`, `rule_inference/grammar_checker.py`, `rule_inference/rule_export.py`:
- Decision tree path extraction at multiple depths
- Random forest DNF extraction
- Grammar checking of extracted rules
- CSV export roundtrip
- Edge cases: single-leaf trees, all-same labels

### `test_rule_validation.py` — Rule Validation (41 tests)

Tests `rule_validation/rule_evaluator.py`, `rule_validation/rule_selector.py`, `rule_validation/counterfactual_hints.py`, `rule_validation/validation_report.py`:
- Per-rule TP/FP/TN/FN, decisiveness, FPR, FNR computation
- Selection criteria (FPR ≥ 20%, FNR ≤ 5%)
- Relaxed selection with ranking
- L1-minimal perturbation computation
- CSV and text report generation
- `SelectionCriteria` dataclass configuration

### `test_cbf_data.py` — CBF Data Layer (28 tests)

Tests `cbf_data/loader.py`, `cbf_data/metadata.py`, `cbf_data/adapter.py`:
- Dataset loading from CSV files
- Feature matrix extraction (`get_feature_matrix()`)
- Paired comparison loading
- System/feature metadata lookup
- `cbf_to_semantic()` and `semantic_to_cbf()` roundtrip
- `AVAILABLE_SYSTEMS` enumeration

## Running Tests

```bash
# All tests
python -m pytest

# Single file
python -m pytest tests/test_semantic.py -v

# With coverage
python -m pytest --cov=. --cov-report=term-missing

# Using Makefile
make test
```

## Test Configuration

Configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-v --tb=short"
```

## Dependencies

- **`pytest`** — Test framework
- **`pytest-cov`** — Coverage reporting
- **Internal:** all production packages
