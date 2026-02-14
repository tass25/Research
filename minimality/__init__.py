"""Change minimality analysis package.

This package implements Priority 3: detecting overly conservative refinements
that tighten bounds more than justified by counterfactual evidence.
"""

from .change_extractor import ChangeExtractor
from .bound_analyzer import BoundAnalyzer
from .justification_checker import JustificationChecker
from .minimality_scorer import MinimalityScorer
from .minimality_validator import MinimalityValidator

__all__ = [
    "ChangeExtractor",
    "BoundAnalyzer",
    "JustificationChecker",
    "MinimalityScorer",
    "MinimalityValidator",
]
