"""
Grammar compliance checker for extracted rules (Group B utility).

Validates that rule text conforms to the operational rule grammar G.
Delegates to the shared.grammar_validation module so that both Group B
and Group C use the same validation logic.

Public API (unchanged):
    check_grammar_compliance(rule_text, allowed_variables) -> GrammarCheckResult
    validate_dnf_structure(rule_text) -> (bool, str)
"""

from shared.grammar_validation import (
    GrammarCheckResult,
    validate_rule as check_grammar_compliance,
    validate_dnf as validate_dnf_structure,
)
