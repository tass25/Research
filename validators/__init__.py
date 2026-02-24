"""
Syntactic & structural validators (Priority 1).

Validates rules for:
- Pre-parse normalization (Unicode, hidden chars)
- Structural complexity (depth, predicate count)
- ODD absolute bound enforcement
"""

from .base import ValidationWarning, ValidationViolation
from .preparse import PreParseValidator
from .structure import StructureValidator
from .absolute_bounds import AbsoluteBoundValidator

__all__ = [
    "ValidationWarning",
    "ValidationViolation",
    "PreParseValidator",
    "StructureValidator",
    "AbsoluteBoundValidator",
]
