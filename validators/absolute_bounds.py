"""
Absolute bound validator for operational rules.

Validates that constants are within physically/logically admissible ranges
defined by the Operational Design Domain (ODD).
"""

from typing import Dict, List, Tuple
from core.schema import Rule, Relation, Conjunction, Disjunction, Variable, Constant
from validators.base import ValidationViolation


class AbsoluteBoundValidator:
    """Validates constants are within ODD-specified bounds.
    
    IMPORTANT: This checks ABSOLUTE bounds (physical limits), NOT relative
    tightening. Relative minimality is handled in Priority 3.
    
    Example:
        - ego_speed < 200 when ODD max is 50 → VIOLATION (caught here)
        - ego_speed < 1 when original was < 30 → NO VIOLATION (Priority 3)
    """
    
    def __init__(self, variable_bounds: Dict[str, Tuple[float, float]]):
        """Initialize with ODD bounds.
        
        Args:
            variable_bounds: Dict mapping variable names to (min, max) tuples.
        
        Raises:
            ValueError: If any bound has min > max.
        """
        for var, (lo, hi) in variable_bounds.items():
            if lo > hi:
                raise ValueError(f"Invalid bounds for '{var}': {lo} > {hi}")
        self.variable_bounds = variable_bounds

    def validate(self, rule: Rule):
        """Validate all constants are within ODD bounds.
        
        Returns:
            List of ValidationViolation objects (empty if valid)
        """
        violations = []

        for rel in self._relations(rule):
            # Check: Variable op Constant
            if isinstance(rel.left, Variable) and isinstance(rel.right, Constant):
                self._check(rel.left.name, rel.right.value, violations, rel)

            # Check: Constant op Variable
            if isinstance(rel.left, Constant) and isinstance(rel.right, Variable):
                self._check(rel.right.name, rel.left.value, violations, rel)

        return violations

    def _check(self, var, val, violations, rel):
        """Check a single constant against variable bounds."""
        if var in self.variable_bounds:
            lo, hi = self.variable_bounds[var]
            if not (lo <= val <= hi):
                violations.append(
                    ValidationViolation(
                        "bounds", 
                        "error",
                        f"Constant {val} for variable '{var}' is outside "
                        f"ODD bounds [{lo}, {hi}]",
                        location=str(rel),
                    )
                )

    def _relations(self, node):
        """Extract all relations from rule."""
        if isinstance(node, Relation):
            return [node]
        if isinstance(node, Conjunction):
            return sum((self._relations(item) for item in node.items), [])
        if isinstance(node, Disjunction):
            return sum((self._relations(item) for item in node.items), [])
        return []
