"""
Pre-parse validator for LLM output normalization.

Handles Unicode variants, hidden characters, and alternative operator
representations before the parser sees the input.
"""
import re
from typing import List, Tuple
from validators.base import ValidationWarning, ValidationViolation


class PreParseValidator:
    """Normalizes LLM output before parsing.
    
    This is NOT redundant with grammar enforcement - it handles
    real-world LLM quirks that shouldn't burden the parser.
    """
    
    ALLOWED_OPERATORS = {"<", "<=", ">", ">=", "=", "!=", "∧", "∨"}

    def normalize_and_validate(
        self, rule_str: str
    ) -> Tuple[str, List[ValidationWarning], List[ValidationViolation]]:
        """Normalize and detect pre-parse issues.
        
        Args:
            rule_str: Raw string from LLM
            
        Returns:
            Tuple of (normalized_string, warnings, violations)
        """
        warnings, violations = [], []
        normalized = rule_str

        # Unicode operator normalization
        unicode_map = {'≤': '<=', '≥': '>=', '≠': '!=', '⋀': '∧', '⋁': '∨'}
        for u, r in unicode_map.items():
            if u in normalized:
                warnings.append(
                    ValidationWarning("unicode", "Normalized Unicode operator", u, r)
                )
                normalized = normalized.replace(u, r)

        # Remove hidden characters
        hidden = ['\u200b', '\ufeff', '\u2060']
        for h in hidden:
            if h in normalized:
                warnings.append(
                    ValidationWarning("hidden", "Removed hidden character", repr(h), "")
                )
                normalized = normalized.replace(h, "")

        # Detect invalid operators
        for op in re.findall(r'[<>=!∧∨&|]{2,}', normalized):
            if op not in self.ALLOWED_OPERATORS:
                violations.append(
                    ValidationViolation(
                        "operators", "error",
                        f"Invalid operator '{op}'", location=str(normalized.find(op))
                    )
                )

        return normalized, warnings, violations
