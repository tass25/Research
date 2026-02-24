# Shared — Cross-Group Utilities

Cross-group utilities used by both **Group B** (`rule_inference/`) and **Group C** (`rule_validation/`) to validate extracted rules against the formal grammar G.

## Why This Folder Exists

The SEAMS 2026 task assignment states:

> *"Group B and C should collaborate on a small utility to validate rule syntax against grammar G."*

Centralizing the validation logic here ensures:
1. **No divergence** between inference-time and evaluation-time grammar checks
2. **Single place to update** if grammar G is extended with new operators or constructs
3. **No circular dependencies** — both `rule_inference/` and `rule_validation/` import from `shared/` without depending on each other

## Folder Structure

```
shared/
├── __init__.py              # Package init
└── grammar_validation.py    # Grammar G compliance validation (single source of truth)
```

## Files

### `grammar_validation.py` — Grammar G Compliance

Provides functions to validate rule strings against Grammar G (SEAMS 2026 Paper, Section 3):

```
Rule  → Disj
Disj  → Conj  (OR  Conj)*
Conj  → Rel   (AND Rel)*
Rel   → Exp rop Exp
Exp   → var | const
rop   → < | <= | > | >= | = | !=
```

**Key functions:**

| Function | Signature | Purpose |
|----------|-----------|---------|
| `validate_rule(rule_text, allowed_variables)` | → `GrammarCheckResult` | Full validation with predicate count, variables, errors and warnings |
| `validate_dnf(rule_str)` | → `(bool, str)` | Check DNF structure (OR of ANDs of relations) |
| `is_grammar_valid(rule_text, allowed_variables)` | → `bool` | Quick boolean grammar check |
| `is_valid_dnf(rule_str)` | → `bool` | Quick boolean DNF check |

**`GrammarCheckResult` fields:** `is_valid`, `rule_text`, `errors` (list), `warnings` (list), `n_predicates`, `n_conjunctions`, `variables_used` (list).

### `__init__.py` — Package Init

Contains a module-level docstring describing the package purpose. Serves as the package marker for `shared/`.

## Usage

```python
from shared.grammar_validation import validate_rule, validate_dnf, is_grammar_valid

# Full validation with diagnostics
result = validate_rule("speed <= 30 AND dist > 5", ["speed", "dist"])
print(result.is_valid)        # True
print(result.n_predicates)    # 2
print(result.variables_used)  # ["speed", "dist"]

# Quick boolean check
ok = is_grammar_valid("speed <= 30", ["speed", "dist"])  # True

# DNF structure check
valid, msg = validate_dnf("(a <= 1 AND b > 2) OR (c >= 3)")
print(valid)  # True
```

## Where It's Used

| Consumer | How It's Used |
|----------|--------------|
| `rule_inference/grammar_checker.py` | Re-exports `validate_rule()` for inference-time checks |
| `rule_inference/tree_extractor.py` | Validates extracted decision tree paths against grammar G |
| `rule_inference/rule_export.py` | Includes grammar validity flag in CSV exports |
| `rule_validation/rule_selector.py` | Filters candidates by grammar validity before selection |

## Dependencies

- **Python standard library** (`re`, `typing`)
- **No internal dependencies** — this is intentionally dependency-free to avoid circular imports
