"""
Grammar compliance checker for extracted rules (Group B utility).

Validates that rule text conforms to the operational rule grammar G:
- Allowed operators: <, >, <=, >=, =, !=
- Logical connectives: AND (∧), OR (∨)
- Variables must match feature names
- Rules must be in DNF form (disjunction of conjunctions)
- No nested arithmetic beyond simple comparisons
"""

from typing import List, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path
import re


@dataclass
class GrammarCheckResult:
    """Result of checking a rule against grammar G."""
    is_valid: bool
    rule_text: str
    errors: List[str]
    warnings: List[str]
    n_predicates: int
    n_conjunctions: int
    variables_used: List[str]


def _tokenize_rule(rule_text: str) -> List[str]:
    """Split a rule text into tokens, respecting operators."""
    # Replace multi-char operators first
    text = rule_text.replace("<=", " <= ").replace(">=", " >= ").replace("!=", " != ")
    # Handle single-char operators that aren't part of multi-char ones
    text = re.sub(r'(?<![<>!])([<>])(?!=)', r' \1 ', text)
    text = re.sub(r'(?<![<>!])=(?!=)', r' = ', text)
    # Parentheses
    text = text.replace("(", " ( ").replace(")", " ) ")
    tokens = text.split()
    return [t for t in tokens if t]


def check_grammar_compliance(
    rule_text: str,
    allowed_variables: List[str],
) -> GrammarCheckResult:
    """Check if a rule string complies with grammar G.

    Grammar G allows:
    - Variables from the allowed set
    - Numeric constants
    - Relational operators: <, <=, >, >=, =, !=
    - Logical: AND, OR
    - Parentheses for grouping conjunctions in DNF
    - No arithmetic expressions (only var op const)

    Args:
        rule_text: The rule string to validate.
        allowed_variables: Set of valid variable names.

    Returns:
        GrammarCheckResult with validity and diagnostics.
    """
    errors = []
    warnings = []
    variables_used = []

    if not rule_text or not rule_text.strip():
        return GrammarCheckResult(
            is_valid=False,
            rule_text=rule_text,
            errors=["Empty rule text"],
            warnings=[],
            n_predicates=0,
            n_conjunctions=0,
            variables_used=[],
        )

    allowed_ops = {"<", "<=", ">", ">=", "=", "!="}
    allowed_logical = {"AND", "OR"}
    allowed_parens = {"(", ")"}

    tokens = _tokenize_rule(rule_text)

    # Check each token
    for token in tokens:
        if token in allowed_ops or token in allowed_logical or token in allowed_parens:
            continue
        # Check if it's a number
        try:
            float(token)
            continue
        except ValueError:
            pass
        # Check if it's a variable
        if token in allowed_variables:
            if token not in variables_used:
                variables_used.append(token)
            continue
        # Unknown token
        if re.match(r'^[a-z_][a-z0-9_]*$', token):
            errors.append(f"Unknown variable '{token}'. Allowed: {sorted(allowed_variables)}")
        else:
            errors.append(f"Invalid token: '{token}'")

    # Check structure: should be alternating predicate/logical
    # Count predicates (each var op const group)
    n_predicates = 0
    n_conjunctions = 0
    i = 0
    depth = 0  # Paren depth
    current_conjunction_predicates = 0

    while i < len(tokens):
        tok = tokens[i]
        if tok == "(":
            depth += 1
            i += 1
        elif tok == ")":
            depth -= 1
            if depth < 0:
                errors.append("Unmatched closing parenthesis")
            i += 1
        elif tok == "OR":
            if current_conjunction_predicates > 0:
                n_conjunctions += 1
                current_conjunction_predicates = 0
            i += 1
        elif tok == "AND":
            i += 1
        elif tok in allowed_ops:
            # Part of a predicate — this is the operator
            n_predicates += 1
            current_conjunction_predicates += 1
            i += 1
        else:
            i += 1

    if current_conjunction_predicates > 0:
        n_conjunctions += 1

    if depth != 0:
        errors.append(f"Unmatched parentheses (depth={depth})")

    # Check for arithmetic operators (not allowed in grammar G)
    for arith_op in ["+", "-", "*", "/"]:
        # Negative numbers are okay, but binary arithmetic is not
        if arith_op in ["+", "*", "/"]:
            if arith_op in rule_text:
                # Check it's not inside a number
                if re.search(rf'(?<!\d)\{arith_op}(?!\d)', rule_text):
                    warnings.append(
                        f"Possible arithmetic operator '{arith_op}' found. "
                        f"Grammar G allows only simple comparisons."
                    )

    # Warnings for complexity
    if n_predicates > 10:
        warnings.append(f"High complexity ({n_predicates} predicates). Consider simplification.")

    return GrammarCheckResult(
        is_valid=len(errors) == 0,
        rule_text=rule_text,
        errors=errors,
        warnings=warnings,
        n_predicates=n_predicates,
        n_conjunctions=n_conjunctions,
        variables_used=variables_used,
    )


def validate_dnf_structure(rule_text: str) -> Tuple[bool, str]:
    """Verify the rule is in proper DNF (disjunction of conjunctions).

    DNF = clause1 OR clause2 OR ...
    Where each clause = pred1 AND pred2 AND ...

    Returns:
        (is_valid_dnf, explanation)
    """
    if not rule_text:
        return False, "Empty rule"

    # Split by OR to get clauses
    or_parts = re.split(r'\s+OR\s+', rule_text)

    for i, clause in enumerate(or_parts):
        clause = clause.strip().strip("()")
        # Each clause should be AND-connected predicates
        and_parts = re.split(r'\s+AND\s+', clause)
        for part in and_parts:
            part = part.strip().strip("()")
            # Each part should be: variable op constant
            if not re.match(
                r'^[a-z_][a-z0-9_]*\s*(<=|>=|!=|<|>|=)\s*-?[\d.]+$',
                part.strip()
            ):
                return False, (
                    f"Clause {i + 1}, predicate '{part}' is not a simple comparison "
                    f"(expected: variable op constant)"
                )

    return True, f"Valid DNF with {len(or_parts)} clause(s)"
