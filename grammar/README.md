# Grammar — Lark Grammar Definition

This folder contains the formal grammar specification for operational safety rules, written in [Lark](https://lark-parser.readthedocs.io/) syntax.

## Why Lark?

We chose Lark over alternatives (PLY, ANTLR, pyparsing) for several reasons:
1. **LALR(1) parsing** — Deterministic, linear-time parsing with no ambiguity; critical for safety-critical rule validation where parse results must be predictable
2. **Native Python** — No external code generation step; the grammar integrates seamlessly with the Python transformer pattern
3. **Readable EBNF-like syntax** — The grammar file is self-documenting and closely mirrors the BNF notation used in the research paper
4. **Small dependency footprint** — Single `pip install lark` with no transitive dependencies

## File

### `rules.lark` — Grammar Specification

Defines the complete grammar for operational rules in a hierarchical structure:

```
Rule → Disjunction
Disjunction → Conjunction (∨ Conjunction)*
Conjunction → Relation (∧ Relation)*
Relation → Expression ROP Expression | ( Disjunction )
Expression → Term (AOP Term)*
Term → VARIABLE | NUMBER | ( Expression )
```

**Operator precedence** (lowest to highest):
1. `∨` (OR) — Disjunction
2. `∧` (AND) — Conjunction
3. Relational operators (`<`, `<=`, `>`, `>=`, `=`, `!=`)
4. Arithmetic operators (`+`, `-`, `*`, `/`)

**Key design decisions:**

| Feature | Implementation | Rationale |
|---------|---------------|-----------|
| `?` prefix on rules | `?start`, `?rule`, etc. | Inline single-child rules to simplify the parse tree |
| `->` alias | `grouped_rule` | Named alias for parenthesized sub-expressions so the transformer can handle them distinctly |
| Dual operator syntax | `AND`/`∧`, `OR`/`∨` | Support both Unicode and ASCII for LLM compatibility |
| `SIGNED_NUMBER` import | From Lark common | Handles negative numbers, decimals, and scientific notation |
| Variable pattern | `/[a-z_][a-z0-9_]*/` | Lowercase snake_case only, preventing LLMs from introducing arbitrary identifiers |

## How It's Used

The grammar file is loaded at runtime by `parsers/lark_parser.py`:
```python
grammar_path = Path(__file__).parent.parent / "grammar" / "rules.lark"
self.parser = Lark(grammar_content, parser="lalr", transformer=RuleTransformer(config))
```

The LALR parser is constructed once and reused for all rule parsing operations.
