# Parsers — Rule String → Typed AST

This package transforms raw rule strings (e.g., from LLM output) into strongly-typed AST objects defined in `core/schema.py`.

## Why This Exists

LLM-generated rules arrive as plain text. Before any validation can occur, they must be parsed into a structured representation. This package bridges the gap between raw text and the typed `Rule` tree that all downstream validators and analyzers consume.

## Approach

We use a **two-phase parsing architecture**:

1. **Lark LALR parser** — Converts the string into a parse tree based on the grammar in `grammar/rules.lark`
2. **`RuleTransformer`** — Walks the parse tree bottom-up, converting each node into a typed `core.schema` object

This separation keeps the grammar clean (declarative) and the transformation logic explicit (imperative Python).

## File

### `lark_parser.py` — Parser & Transformer

Contains two classes:

#### `RuleTransformer(Transformer)`

A Lark `Transformer` that converts parse tree nodes into typed schema objects. Each method corresponds to a grammar rule:

| Method | Input | Output | Notes |
|--------|-------|--------|-------|
| `VARIABLE(token)` | Variable name string | `Variable` | Validates against `config.allowed_variables`; raises `ValueError` for unknown variables |
| `NUMBER(token)` | Numeric string | `Constant` | Converts to `float` |
| `AOP(token)` | Arithmetic op string | `ArithOp` | Uses `ArithOp.from_string()` |
| `ROP(token)` | Relational op string | `RelOp` | Uses `RelOp.from_string()` |
| `expression(items)` | List of transformed children | `Expr` or `BinaryExpr` | Handles single terms and binary expressions |
| `relation(items)` | `[Expr, RelOp, Expr]` | `Relation` | Includes defensive type checks for debugging |
| `conjunction(items)` | List of relations/conjunctions | `Conjunction` | **Flattens** nested conjunctions for a flat AND list |
| `disjunction(items)` | List of clauses | `Disjunction` | **Flattens** nested disjunctions for a flat OR list |
| `grouped_rule(items)` | Parenthesized sub-expression | Pass-through | Unwraps the parentheses |
| `__default__` | Any unhandled rule | Pass-through | Fallback for single-child rules |

**Variable validation happens at parse time**, not during a separate validation pass. This is intentional — an unknown variable means the rule is fundamentally invalid and should never enter the system.

#### `OperationalRuleParser`

High-level API wrapping the Lark parser:

- **`__init__(config)`** — Loads `grammar/rules.lark`, constructs the LALR parser with the transformer
- **`parse(rule_str)`** — Parse a rule string, normalize `AND`/`OR` keywords to `∧`/`∨`, ensure result is wrapped in a `Disjunction` (the top-level `Rule` type)
- **`parse_safe(rule_str)`** — Same as `parse()` but returns `(rule, errors)` instead of raising exceptions

**`AND`/`OR` normalization** (`parse()` method): The parser normalizes ASCII keywords to Unicode operators before parsing. This handles LLMs that output `AND` instead of `∧`.

## Usage

```python
from core.config import DEFAULT_ADS_CONFIG
from parsers.lark_parser import OperationalRuleParser

parser = OperationalRuleParser(DEFAULT_ADS_CONFIG)
rule, errors = parser.parse_safe("(dist_front < 5) ∧ (ego_speed > 0)")

if rule:
    result = rule.evaluate({"dist_front": 3.0, "ego_speed": 10.0})
```

## Dependencies

- **`lark`** — The Lark parsing library (`pip install lark`)
- Internal: `core.schema`, `core.types`, `core.config`
