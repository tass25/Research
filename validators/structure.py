"""
Structure validator for operational rules.

Validates complexity bounds (depth, predicate count) to ensure
verification tractability and human reviewability.
"""

from core.schema import Rule, Relation, Conjunction, Disjunction, BinaryExpr
from validators.base import ValidationViolation


class StructureValidator:
    """Validates structural properties and enforces complexity limits.
    
    These limits serve as safety guards and DoS protection:
    1. Verification tractability (exponential complexity in depth/size)
    2. Human reviewability (ISO 26262 requirement)
    3. DoS protection (prevent pathological LLM outputs)
    """
    
    def __init__(self, max_depth: int = 10, max_predicates: int = 20):
        """Initialize with complexity bounds.
        
        Args:
            max_depth: Maximum nesting depth (must be > 0)
            max_predicates: Maximum total number of relations (must be > 0)
        
        Raises:
            ValueError: If bounds are non-positive.
        """
        if max_depth <= 0:
            raise ValueError(f"max_depth must be positive, got {max_depth}")
        if max_predicates <= 0:
            raise ValueError(f"max_predicates must be positive, got {max_predicates}")
        self.max_depth = max_depth
        self.max_predicates = max_predicates

    def validate(self, rule: Rule):
        """Validate rule structure and complexity.
        
        Returns:
            List of ValidationViolation objects (empty if valid)
        """
        violations = []

        if rule is None:
            raise TypeError("Rule cannot be None")

        depth = self._depth(rule)
        if depth > self.max_depth:
            violations.append(
                ValidationViolation(
                    "structure", 
                    "error", 
                    f"Nesting depth {depth} exceeds maximum {self.max_depth}"
                )
            )

        count = self._count(rule)
        if count > self.max_predicates:
            violations.append(
                ValidationViolation(
                    "structure", 
                    "error", 
                    f"Predicate count {count} exceeds maximum {self.max_predicates}"
                )
            )

        return violations

    def _depth(self, node, d=0):
        """Compute maximum nesting depth."""
        if isinstance(node, Relation):
            return d
        if isinstance(node, BinaryExpr):
            return max(self._depth(node.left, d + 1), self._depth(node.right, d + 1))
        if isinstance(node, Conjunction):
            return max((self._depth(item, d + 1) for item in node.items), default=d)
        if isinstance(node, Disjunction):
            return max((self._depth(item, d + 1) for item in node.items), default=d)
        return d

    def _count(self, node):
        """Count total number of relational predicates."""
        if isinstance(node, Relation):
            return 1
        if isinstance(node, BinaryExpr):
            return self._count(node.left) + self._count(node.right)
        if isinstance(node, Conjunction):
            return sum(self._count(item) for item in node.items)
        if isinstance(node, Disjunction):
            return sum(self._count(item) for item in node.items)
        return 0
