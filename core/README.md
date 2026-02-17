# Core — Type System & Configuration

This package defines the foundational type system, grammar schema, and ODD (Operational Design Domain) configuration that all other modules depend on. It establishes the strongly-typed data model used throughout the entire project.

## Why This Exists

LLM-generated rules are raw text. To validate them safely, we need a **typed intermediate representation** (IR) that the rest of the system can reason about programmatically. The `core/` package converts the problem from "string manipulation" into "typed tree operations", making validators, analyzers, and evaluators straightforward and type-safe.

## Files

### `types.py` — Operator Enumerations

Defines three `Enum` classes that constrain all operators to a fixed, known set:

| Enum | Members | Purpose |
|------|---------|---------|
| `RelOp` | `<`, `<=`, `>`, `>=`, `=`, `!=` | Relational operators in predicates |
| `ArithOp` | `+`, `-`, `*`, `/` | Arithmetic operators in expressions |
| `LogicOp` | `∧`, `∨` | Logical connectives between predicates |

Each enum provides a `from_string()` class method for safe parsing from string tokens. Invalid operators raise `ValueError`, preventing unknown operators from entering the system.

**Why enums?** Using enums instead of raw strings ensures:
- Compile-time completeness checks (every operator must be handled)
- No typos or invalid operator variants slip through
- Pattern matching in validators/analyzers is exhaustive

### `schema.py` — Grammar Dataclasses (AST Nodes)

Defines the Abstract Syntax Tree (AST) for parsed operational rules using frozen `dataclass` objects:

```
Rule (= Disjunction)
├── Disjunction          # c₁ ∨ c₂ ∨ ... (OR of clauses)
│   └── items: List[ClauseItem]
├── Conjunction          # p₁ ∧ p₂ ∧ ... (AND of predicates)
│   └── items: List[PredicateItem]
├── Relation             # expr rop expr  (e.g., ego_speed > 5)
│   ├── left: Expr
│   ├── op: RelOp
│   └── right: Expr
└── Expr (base class)
    ├── Variable         # Named variable (e.g., "dist_front")
    ├── Constant         # Numeric literal (e.g., 5.0)
    └── BinaryExpr       # Arithmetic (e.g., speed * 2)
```

Every node implements an `evaluate(env)` method:
- **Expressions** evaluate to `float` given a variable environment `Dict[str, float]`
- **Relations** evaluate to `bool` (comparison result)
- **Conjunctions/Disjunctions** evaluate to `bool` (logical result)

**Why frozen dataclasses?** Immutability guarantees that once a rule is parsed, it cannot be accidentally mutated during validation — critical for safety-critical systems.

**Why `evaluate()`?** Enables direct rule execution against simulation data for consistency checking in the `semantic/` package.

### `config.py` — ODD Configuration

Defines `GrammarConfig`, a frozen dataclass containing:
- **`allowed_variables`**: The set of variable names permitted in rules (e.g., `ego_speed`, `dist_front`)
- **`variable_bounds`**: Physical/operational limits per variable from the ODD specification

A pre-built `DEFAULT_ADS_CONFIG` is provided for Autonomous Driving Systems with four variables:

| Variable | Bounds | Meaning |
|----------|--------|---------|
| `ego_speed` | [0, 50] m/s | Ego vehicle speed |
| `dist_front` | [0, 200] m | Distance to front vehicle |
| `lane_offset` | [-5, 5] m | Lateral offset from lane center |
| `rel_speed` | [-50, 50] m/s | Relative speed to front vehicle |

**Why a config object?** Separating the ODD specification from validation logic allows:
- Different domains (highway, urban, parking) to use different configs
- Bounds to be loaded from external files or databases
- Easy testing with custom configurations

## Dependencies

- Python standard library only (`dataclasses`, `enum`, `typing`)
- No external packages required
