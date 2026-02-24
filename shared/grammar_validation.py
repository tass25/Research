"""
Shared grammar validation utility for Group B and Group C.

Validates that rule text conforms to the operational rule grammar G
defined in the SEAMS 2026 paper (Section 3):

    Rule  → Disj
    Disj  → Conj  (OR  Conj)*
    Conj  → Rel   (AND Rel)*
    Rel   → Exp rop Exp
    Exp   → var | const
    rop   → < | <= | > | >= | = | !=

This module is deliberately kept self-contained so that both
rule_inference (Group B) and rule_validation (Group C) can import it
without circular dependencies.

Usage (Group B — export):
    from shared.grammar_validation import validate_rule, is_grammar_valid

Usage (Group C — evaluation):
    from shared.grammar_validation import validate_rule, validate_dnf
"""

import re
from typing import List, Tuple, Optional, Set
from dataclasses import dataclass, field


# ── Data classes ─────────────────────────────────────────────────────────

@dataclass
class GrammarCheckResult:
    """Result of checking a rule against grammar G."""
    is_valid: bool
    rule_text: str
    errors: List[str]
    warnings: List[str]
    n_predicates: int
    n_conjunctions: int       # Number of AND-clauses (disjuncts)
    variables_used: List[str]


# ── Tokeniser ────────────────────────────────────────────────────────────

_ALLOWED_OPS = frozenset({"<", "<=", ">", ">=", "=", "!="})
_ALLOWED_LOGICAL = frozenset({"AND", "OR"})
_ALLOWED_PARENS = frozenset({"(", ")"})


def _tokenize_rule(rule_text: str) -> List[str]:
    """Split a rule text into tokens, preserving multi-character operators.

    Negative numbers (e.g. ``-5.0``) are kept as single tokens when the
    minus sign is not preceded by a number or variable token.
    """
    text = rule_text
    # Pad multi-char operators first
    text = text.replace("<=", " <= ").replace(">=", " >= ").replace("!=", " != ")
    # Pad single-char < > = that are NOT part of <=, >=, !=
    text = re.sub(r'(?<![<>!])([<>])(?!=)', r' \1 ', text)
    text = re.sub(r'(?<![<>!])=(?!=)', r' = ', text)
    # Pad parentheses
    text = text.replace("(", " ( ").replace(")", " ) ")
    raw_tokens = [t for t in text.split() if t]

    # Merge a standalone '-' with the following numeric token to form
    # a negative number when the '-' is not preceded by a value token.
    merged: List[str] = []
    i = 0
    while i < len(raw_tokens):
        tok = raw_tokens[i]
        if tok == "-" and i + 1 < len(raw_tokens):
            # Check if next token is a number
            try:
                float(raw_tokens[i + 1])
                is_next_num = True
            except ValueError:
                is_next_num = False
            # Only merge if not preceded by a number or variable (i.e. subtraction)
            prev_is_value = False
            if merged:
                prev = merged[-1]
                try:
                    float(prev)
                    prev_is_value = True
                except ValueError:
                    if re.match(r'^[a-z_][a-z0-9_]*$', prev):
                        prev_is_value = True
            if is_next_num and not prev_is_value:
                merged.append(f"-{raw_tokens[i + 1]}")
                i += 2
                continue
        merged.append(tok)
        i += 1
    return merged


# ── Core validation ─────────────────────────────────────────────────────

def validate_rule(
    rule_text: str,
    allowed_variables: List[str],
) -> GrammarCheckResult:
    """Check whether *rule_text* conforms to grammar G.

    Grammar G allows:
    - Variables from the *allowed_variables* set
    - Numeric constants (including negative, e.g. ``-1.32``)
    - Relational operators:  ``<  <=  >  >=  =  !=``
    - Logical connectives:   ``AND  OR``
    - Parentheses for grouping conjunctions in DNF
    - **No** arithmetic expressions (only ``var rop const``)

    Parameters
    ----------
    rule_text : str
        Rule string to validate.
    allowed_variables : list[str]
        Valid variable names for the system under test.

    Returns
    -------
    GrammarCheckResult
        Includes ``is_valid``, diagnostic ``errors`` / ``warnings``,
        and structural metrics.
    """
    errors: List[str] = []
    warnings: List[str] = []
    variables_used: List[str] = []

    if not rule_text or not rule_text.strip():
        return GrammarCheckResult(
            is_valid=False, rule_text=rule_text or "",
            errors=["Empty rule text"], warnings=[],
            n_predicates=0, n_conjunctions=0, variables_used=[],
        )

    allowed_set: Set[str] = set(allowed_variables)
    tokens = _tokenize_rule(rule_text)

    # ── token-level checks ───────────────────────────────────────────
    for token in tokens:
        if token in _ALLOWED_OPS or token in _ALLOWED_LOGICAL or token in _ALLOWED_PARENS:
            continue
        # Number?
        try:
            float(token)
            continue
        except ValueError:
            pass
        # Variable?
        if token in allowed_set:
            if token not in variables_used:
                variables_used.append(token)
            continue
        # Unknown
        if re.match(r'^[a-z_][a-z0-9_]*$', token):
            errors.append(
                f"Unknown variable '{token}'. "
                f"Allowed: {sorted(allowed_variables)}"
            )
        else:
            errors.append(f"Invalid token: '{token}'")

    # ── structural checks ────────────────────────────────────────────
    n_predicates = 0
    n_conjunctions = 0
    depth = 0
    current_conj_preds = 0

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "(":
            depth += 1
        elif tok == ")":
            depth -= 1
            if depth < 0:
                errors.append("Unmatched closing parenthesis")
        elif tok == "OR":
            if current_conj_preds > 0:
                n_conjunctions += 1
                current_conj_preds = 0
        elif tok in _ALLOWED_OPS:
            n_predicates += 1
            current_conj_preds += 1
        i += 1

    if current_conj_preds > 0:
        n_conjunctions += 1

    if depth != 0:
        errors.append(f"Unmatched parentheses (depth={depth})")

    # ── arithmetic guard ─────────────────────────────────────────────
    for arith_op in ["+", "*", "/"]:
        if arith_op in rule_text:
            if re.search(rf'(?<!\d)\{arith_op}(?!\d)', rule_text):
                warnings.append(
                    f"Possible arithmetic operator '{arith_op}' found. "
                    f"Grammar G allows only simple comparisons (var rop const)."
                )

    # Check for '-' used as subtraction (variable_or_number - number_or_variable)
    if re.search(r'[a-z0-9_]\s+-\s+[a-z0-9_]', rule_text, re.IGNORECASE):
        warnings.append(
            "Possible arithmetic operator '-' found. "
            "Grammar G allows only simple comparisons (var rop const)."
        )

    # ── complexity warning ───────────────────────────────────────────
    if n_predicates > 10:
        warnings.append(
            f"High complexity ({n_predicates} predicates). "
            f"Consider simplification."
        )

    return GrammarCheckResult(
        is_valid=len(errors) == 0,
        rule_text=rule_text,
        errors=errors,
        warnings=warnings,
        n_predicates=n_predicates,
        n_conjunctions=n_conjunctions,
        variables_used=variables_used,
    )


# ── DNF structure verification ───────────────────────────────────────────

_PREDICATE_RE = re.compile(
    r'^[a-z_][a-z0-9_]*\s*(<=|>=|!=|<|>|=)\s*-?[\d.]+$'
)


def _strip_outer_parens(text: str) -> str:
    """Remove matched outer parenthesis pairs, one at a time.

    Unlike ``str.strip('()')``, this only removes parens that truly
    wrap the entire string as a balanced pair.
    """
    s = text.strip()
    while s.startswith("(") and s.endswith(")"):
        depth = 0
        matched = True
        for i, ch in enumerate(s):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if depth == 0 and i < len(s) - 1:
                matched = False
                break
        if matched:
            s = s[1:-1].strip()
        else:
            break
    return s


def validate_dnf(rule_text: str) -> Tuple[bool, str]:
    """Verify the rule is in proper DNF (disjunction of conjunctions).

    DNF = clause₁ OR clause₂ OR ...
    Where each clause = pred₁ AND pred₂ AND ...
    And each predicate = ``variable rop constant``

    Parameters
    ----------
    rule_text : str
        The rule string to check.

    Returns
    -------
    tuple[bool, str]
        ``(is_valid_dnf, explanation)``
    """
    if not rule_text:
        return False, "Empty rule"

    or_parts = re.split(r'\s+OR\s+', rule_text)

    for i, clause in enumerate(or_parts):
        clause = _strip_outer_parens(clause.strip())
        and_parts = re.split(r'\s+AND\s+', clause)
        for part in and_parts:
            part = _strip_outer_parens(part.strip())
            if not _PREDICATE_RE.match(part.strip()):
                return False, (
                    f"Clause {i + 1}, predicate '{part}' is not a simple "
                    f"comparison (expected: variable rop constant)"
                )

    return True, f"Valid DNF with {len(or_parts)} clause(s)"


# ── Convenience helpers ──────────────────────────────────────────────────

def is_grammar_valid(
    rule_text: str,
    allowed_variables: List[str],
) -> bool:
    """Return ``True`` iff *rule_text* passes all grammar G checks."""
    return validate_rule(rule_text, allowed_variables).is_valid


def is_valid_dnf(rule_text: str) -> bool:
    """Return ``True`` iff *rule_text* is well-formed DNF."""
    ok, _ = validate_dnf(rule_text)
    return ok
