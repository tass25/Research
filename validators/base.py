"""
Base classes for validators.

Defines common data structures used across all validators.
"""

from dataclasses import dataclass


@dataclass
class ValidationWarning:
    """Non-fatal warning that was handled (example, normalized Unicode)."""
    category: str
    message: str
    original: str
    corrected: str


@dataclass
class ValidationViolation:
    """Fatal violation that prevents rule acceptance."""
    category: str
    severity: str
    message: str
    location: str = ""
