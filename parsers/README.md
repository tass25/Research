# Parsers — Rule String → Typed AST

This package transforms raw rule strings (e.g., from LLM output) into strongly-typed AST objects defined in `core/schema.py`.

## Why This Folder Exists

LLM-generated rules arrive as plain text. Before any validation can occur, they must be parsed into a structured representation. This package bridges the gap between raw text and the typed `Rule` tree that all downstream validators and analyzers consume. Without it, every downstream module would need to implement its own ad-hoc string parsing — error-prone and inconsistent.

## Folder Structure

```
parsers/
└── lark_parser.py    # Parser & Transformer (RuleTransformer + OperationalRuleParser)
```

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
| `term(items)` | Term children | `Expr` | Ensures terminals become schema objects |
| `expression(items)` | List of transformed children | `Expr` or `BinaryExpr` | Handles single terms and binary expressions |
| `relation(items)` | `[Expr, RelOp, Expr]` | `Relation` | Includes defensive type checks for debugging |
| `conjunction(items)` | List of relations/conjunctions | `Conjunction` | **Flattens** nested conjunctions for a flat AND list |
| `disjunction(items)` | List of clauses | `Disjunction` | **Flattens** nested disjunctions for a flat OR list |
| `grouped_rule(items)` | Parenthesized sub-expression | Pass-through | Unwraps the parentheses |
| `__default__` | Any unhandled rule | Pass-through | Fallback for single-child rules |

**Variable validation happens at parse time**, not during a separate validation pass. This is intentional — an unknown variable means the rule is fundamentally invalid and should never enter the system.

#### `OperationalRuleParser`

High-level API wrapping the Lark parser:

| Method | Purpose |
|--------|---------|
| `__init__(config)` | Loads `grammar/rules.lark`, constructs the LALR parser with the transformer |
| `parse(rule_str)` | Parse a rule string, normalize `AND`/`OR` to `∧`/`∨`, ensure result is wrapped in a `Disjunction` |
| `parse_safe(rule_str)` | Same as `parse()` but returns `(rule, errors)` instead of raising exceptions |


**`AND`/`OR` normalization**: The parser normalizes ASCII keywords to Unicode operators before parsing. This handles LLMs that output `AND` instead of `∧`.

**Config-driven parsing:** The parser now fully supports config-driven variable and operator validation. Pass the config object to ensure only allowed variables and bounds are accepted.


## Usage

```python
from core.config import DEFAULT_ADS_CONFIG
from parsers.lark_parser import OperationalRuleParser

# Pass config for variable/operator validation
parser = OperationalRuleParser(DEFAULT_ADS_CONFIG)
rule, errors = parser.parse_safe("(dist_front < 5) ∧ (ego_speed > 0)")

if rule:
    result = rule.evaluate({"dist_front": 3.0, "ego_speed": 10.0,
                            "lane_offset": 0.0, "rel_speed": 0.0})
    # → True
```

## Where It's Used

| Consumer | How It Uses the Parser |
|----------|----------------------|
| `validators/absolute_bounds.py` | Receives already-parsed `Rule` objects (does not call parser directly) |
| `semantic/consistency_checker.py` | Evaluates parsed rules against simulation data |
| `examples/paper_examples.py` | Demonstrates parsing and evaluation |
| `examples/semantic_examples.py` | Parses rules for semantic validation demo |
| `shared/grammar_validation.py` | Uses `OperationalRuleParser` for grammar G compliance checks |

## Dependencies

- **`lark`** — The Lark parsing library (`pip install lark`)
- **Internal:** `core.schema`, `core.types`, `core.config`, `grammar/rules.lark`
