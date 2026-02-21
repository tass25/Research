# Shared Utilities

Cross-group utilities used by both **Group B** (rule_inference) and **Group C** (rule_validation).

## Purpose

Provides a single, authoritative implementation of grammar G validation so
that rule syntax checking is consistent across inference and evaluation.

## Files

| File | Description |
|------|-------------|
| `grammar_validation.py` | `validate_rule()`, `validate_dnf()`, `is_grammar_valid()`, `is_valid_dnf()` — Grammar G compliance and DNF structure checks |
| `__init__.py` | Package init |

## Grammar G (SEAMS 2026 Paper, Section 3)

```
Rule  → Disj
Disj  → Conj  (OR  Conj)*
Conj  → Rel   (AND Rel)*
Rel   → Exp rop Exp
Exp   → var | const
rop   → < | <= | > | >= | = | !=
```

## Usage

```python
from shared.grammar_validation import validate_rule, validate_dnf

# Full validation
result = validate_rule("speed <= 30 AND dist > 5", ["speed", "dist"])
print(result.is_valid)        # True
print(result.n_predicates)    # 2

# Quick boolean check
from shared.grammar_validation import is_grammar_valid
ok = is_grammar_valid("speed <= 30", ["speed", "dist"])  # True

# DNF structure check
valid, msg = validate_dnf("(a <= 1 AND b > 2) OR (c >= 3)")
```

## Why a Shared Module?

The task assignment states:

> *Group B and C should collaborate on a small utility to validate
> rule syntax against grammar G.*

Centralising the validation logic here ensures:
1. No divergence between inference-time and evaluation-time checks.
2. A single place to update if grammar G is extended.
3. Both packages can import without circular dependencies.
