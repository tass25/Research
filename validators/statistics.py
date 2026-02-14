"""
Rejection statistics tracker.

Tracks breakdown of why rules were rejected for LLM comparison.
"""

from dataclasses import dataclass


@dataclass
class RejectionStatistics:
    """Tracks rejection reasons for paper extension value.
    
    Enables:
    1. LLM comparison (which models fail how?)
    2. Prompt optimization (target common failure modes)
    3. Safety insights (rejection clusters in safety-critical categories?)
    """
    syntax_errors: int = 0
    invalid_operators: int = 0
    structure_errors: int = 0
    bound_errors: int = 0
    unicode_issues: int = 0

    def total(self) -> int:
        """Total number of rejections."""
        return sum(vars(self).values())
