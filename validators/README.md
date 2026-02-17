# Validators — Syntactic & Structural Validation

This package implements the **first line of defense** against invalid rules: syntactic normalization, structural complexity checks, ODD bound enforcement, and rejection tracking. These validators run *before* semantic or minimality analysis, catching issues that would make downstream analysis meaningless.

## Why This Exists

LLM-generated rules frequently contain artifacts that a grammar parser alone cannot handle:
- **Unicode variants** (example, `≤` instead of `<=`, zero-width spaces)
- **Structural complexity** (deeply nested rules that are computationally intractable to verify)
- **Physically impossible constants** (example, `ego_speed > 200` when the ODD maximum is 50 m/s)

This package addresses each category with a dedicated, composable validator.

## Approach

The validators follow a **pipeline pattern**: each validator can be applied independently or chained. They produce typed `ValidationWarning` (non-fatal, auto-corrected) and `ValidationViolation` (fatal, rule rejected) objects, ensuring clear separation between recoverable issues and hard failures.

## Files

### `base.py` — Validation Data Types

Defines the two result types used by all validators:

- **`ValidationWarning`** — A non-fatal issue that was automatically corrected:
  - `category`: Type of issue (example, `"unicode"`, `"hidden"`)
  - `message`: Human-readable description
  - `original` / `corrected`: What was found and what it was normalized to

- **`ValidationViolation`** — A fatal issue that prevents rule acceptance:
  - `category`: Type of violation (example, `"bounds"`, `"structure"`, `"operators"`)
  - `severity`: Severity level (`"error"`)
  - `message`: Human-readable description
  - `location`: Where in the rule the violation was found

**Why separate types?** Warnings are informational (the system auto-corrects them), while violations are blocking. This distinction is important for rejection statistics and LLM feedback loops.

### `preparse.py` — LLM Output Normalization

The `PreParseValidator` handles real-world LLM quirks **before** the Lark parser sees the input:

1. **Unicode operator normalization** — Maps Unicode math symbols to their ASCII equivalents:
   - `≤` → `<=`, `≥` → `>=`, `≠` → `!=`
   - `⋀` → `∧`, `⋁` → `∨`

2. **Hidden character removal** — Strips zero-width spaces (`\u200b`), byte-order marks (`\ufeff`), and word joiners (`\u2060`) that LLMs sometimes inject

3. **Invalid operator detection** — Uses regex to find multi-character operator sequences not in the allowed set, flagging them as violations

**Why not handle this in the grammar?** The grammar should define the *correct* syntax. Pre-parse normalization handles *real-world deviations* — keeping the grammar clean and the normalization logic explicit.

### `structure.py` — Complexity Enforcement

The `StructureValidator` enforces two complexity bounds:

| Check | Default Limit | Rationale |
|-------|--------------|-----------|
| **Nesting depth** | 10 levels | Prevents exponential verification complexity; ensures human reviewability (ISO 26262) |
| **Predicate count** | 20 relations | Prevents combinatorial explosion in consistency/contradiction checking |

**Why these limits?**
1. **Verification tractability** — Formal verification cost grows exponentially with rule depth and size
2. **Human reviewability** — ISO 26262 requires that safety-critical rules be reviewable by humans
3. **DoS protection** — Prevents pathological LLM outputs from consuming excessive compute

The depth and count are computed recursively over the `Conjunction`/`Disjunction`/`Relation` tree.

### `absolute_bounds.py` — ODD Bound Validation

The `AbsoluteBoundValidator` ensures all constants are within the physically/logically admissible ranges defined by the ODD:

- Walks the rule tree to extract all `Relation` nodes
- For each `Variable op Constant` or `Constant op Variable` relation, checks whether the constant falls within the variable's ODD bounds
- Example: `ego_speed < 200` with ODD bounds `[0, 50]` → **VIOLATION** (200 > 50)

**Important distinction:** This validator checks **absolute bounds** (physical limits from the ODD). It does NOT check **relative tightening** (example, original rule had `< 30`, refined has `< 1`). Relative minimality analysis is handled by the `minimality/` package (Priority 3).

### `statistics.py` — Rejection Tracking

The `RejectionStatistics` dataclass tracks rejection reasons across validation runs:

| Counter | Tracks |
|---------|--------|
| `syntax_errors` | Lark parse failures |
| `invalid_operators` | Unknown operator sequences |
| `structure_errors` | Depth/predicate limit violations |
| `bound_errors` | ODD bound violations |
| `unicode_issues` | Unicode normalization occurrences |

**Why track rejections?** This enables:
1. **LLM comparison** — Which models produce which failure types?
2. **Prompt optimization** — Target common failure modes in LLM prompts
3. **Safety insights** — Are rejections clustering in safety-critical categories?

## Dependencies

- Python standard library (`dataclasses`, `typing`, `re`)
- Internal: `core.schema`, `validators.base`
