# Core — Type System, Configuration & Logging

This package defines the foundational type system, grammar schema, ODD (Operational Design Domain) configuration, YAML configuration loading, and centralized logging that all other modules depend on. It establishes the strongly-typed data model used throughout the entire project.

## Why This Folder Exists

LLM-generated rules are raw text. To validate them safely, we need a **typed intermediate representation** (IR) that the rest of the system can reason about programmatically. The `core/` package converts the problem from "string manipulation" into "typed tree operations", making validators, analyzers, and evaluators straightforward and type-safe.

Additionally, this package centralizes configuration and logging so that thresholds, bounds, and output formatting are consistent across all modules instead of being scattered and duplicated.

## Folder Structure

```
core/
├── __init__.py          # Package init — exports __version__ = "1.0.0"
├── types.py             # Operator enumerations (RelOp, ArithOp)
├── schema.py            # Grammar AST dataclasses (Rule tree)
├── config.py            # ODD configuration (GrammarConfig, DEFAULT_ADS_CONFIG)
├── config_loader.py     # YAML configuration loader (PipelineConfig, ThresholdConfig)
└── logging_config.py    # Centralized colored logging with optional file output
```

## Files

### `types.py` — Operator Enumerations

Defines two `Enum` classes that constrain all operators to a fixed, known set:

| Enum | Members | Purpose |
|------|---------|--------|
| `RelOp` | `<`, `<=`, `>`, `>=`, `=`, `!=` | Relational operators in predicates |
| `ArithOp` | `+`, `-`, `*`, `/` | Arithmetic operators in expressions |

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


### `config_loader.py` — YAML & Environment Configuration Loader

Replaces hardcoded `DEFAULT_ADS_CONFIG` for production use by loading configuration from YAML files, Python dictionaries, or `ADS_` prefixed environment variables. Now supports all pipeline thresholds as config options.

**Key classes:**

| Class | Purpose |
|-------|---------|
| `ThresholdConfig` | All configurable thresholds (consistency, minimality, overfitting, selection, structure, train/test gap) |
| `PipelineConfig` | Full pipeline config: `GrammarConfig` + `ThresholdConfig` + ML inference hyperparameters |

**Key functions:**

| Function | Purpose |
|----------|---------|
| `load_config(path)` | Load a `GrammarConfig` from a YAML file |
| `load_pipeline_config(path)` | Load a `PipelineConfig` (grammar + thresholds + inference settings) |
| `save_config(config, path)` | Serialize a `GrammarConfig` to YAML for reproducibility |
| `load_config_from_dict(d)` | Build `GrammarConfig` from a dict (for nested YAML sections) |

**Config-driven thresholds:** All semantic validation thresholds (consistency, overfitting, train/test gap, etc.) can now be set via the config dictionary or YAML. Pass the config to `SemanticValidator.validate()` for full control.

**Used by:** `run_pipeline.py` when `--config` is supplied, and by all semantic/minimality/validation modules for threshold wiring.

### `logging_config.py` — Centralized Logging

Provides pipeline-wide logging setup with colored console output (via `colorama`) and optional file logging.

**Key functions:**

| Function | Purpose |
|----------|---------|
| `setup_logging(level, log_file, fmt, datefmt)` | Configure root logger (call once at startup) |
| `get_logger(name)` | Convenience wrapper for `logging.getLogger(name)` |

**Features:**
- `ColoredFormatter` — ANSI color codes per log level (Windows-safe via `colorama`)
- Optional log file at DEBUG level regardless of console level
- Suppresses noisy third-party loggers (`lark`, `sklearn`)
- Idempotent — subsequent calls after first setup are no-ops

**Used by:** `run_pipeline.py` (first call), then every module via `get_logger(__name__)`.

### `__init__.py` — Package Init

Exports `__version__ = "1.0.0"` and serves as the package marker.

## Where It's Used

The `core/` package is imported by **every other package** in the project:

| Downstream Package | What It Imports |
|-------------------|-----------------|
| `parsers/` | `schema.*`, `types.*`, `config.GrammarConfig` |
| `validators/` | `schema.Relation`, `schema.Conjunction`, `schema.Disjunction` |
| `semantic/` | `schema.*` for rule evaluation |
| `minimality/` | `schema.*`, `types.RelOp` for change detection |
| `data/` | `schema.Disjunction` (type hints) |
| `shared/` | `config.GrammarConfig` |
| `rule_inference/` | — (via `shared/`) |
| `rule_validation/` | — (via `shared/`) |
| `run_pipeline.py` | `config_loader.*`, `logging_config.*` |

## Dependencies

- **Python standard library** (`dataclasses`, `enum`, `typing`, `logging`, `pathlib`)
- **`pyyaml`** — YAML file parsing (used by `config_loader.py`)
- **`colorama`** — Colored terminal output (optional; graceful fallback if missing)
