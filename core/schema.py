"""
Strongly-typed grammar schema for operational rules.

Implements the BNF grammar as Python dataclasses with proper type support
for nested structures.
"""

from dataclasses import dataclass
from typing import Dict, List, Union
from core.types import RelOp, ArithOp


class Expr:
    """Base class for all expressions."""
    def evaluate(self, env: Dict[str, float]) -> float:
        raise NotImplementedError


@dataclass(frozen=True)
class Variable(Expr):
    """A variable reference (e.g., ego_speed, dist_front)."""
    name: str

    def evaluate(self, env: Dict[str, float]) -> float:
        if self.name not in env:
            raise KeyError(f"Variable '{self.name}' not in environment")
        return env[self.name]


@dataclass(frozen=True)
class Constant(Expr):
    """A numeric constant (e.g., 5.0, 3.14)."""
    value: float

    def evaluate(self, env: Dict[str, float]) -> float:
        return self.value


@dataclass(frozen=True)
class BinaryExpr(Expr):
    """Binary arithmetic expression (e.g., speed * 2)."""
    left: Expr
    op: ArithOp
    right: Expr

    def evaluate(self, env: Dict[str, float]) -> float:
        l, r = self.left.evaluate(env), self.right.evaluate(env)
        if self.op == ArithOp.ADD:
            return l + r
        if self.op == ArithOp.SUB:
            return l - r
        if self.op == ArithOp.MUL:
            return l * r
        if self.op == ArithOp.DIV:
            if r == 0:
                raise ZeroDivisionError("Division by zero in expression")
            return l / r
        raise ValueError(f"Unknown arithmetic operator: {self.op}")


@dataclass(frozen=True)
class Relation:
    """Relational predicate (e.g., ego_speed > 5)."""
    left: Expr
    op: RelOp
    right: Expr

    def evaluate(self, env: Dict[str, float]) -> bool:
        l, r = self.left.evaluate(env), self.right.evaluate(env)
        return {
            RelOp.LT: l < r,
            RelOp.LE: l <= r,
            RelOp.GT: l > r,
            RelOp.GE: l >= r,
            RelOp.EQ: l == r,
            RelOp.NE: l != r,
        }[self.op]


# Forward reference for recursive types
PredicateItem = Union[Relation, 'Conjunction']
ClauseItem = Union[Relation, 'Conjunction']


@dataclass(frozen=True)
class Conjunction:
    """Conjunction of predicates (p1 ∧ p2 ∧ ...).
    
    Can contain Relations or nested Conjunctions.
    """
    items: List[PredicateItem]

    def evaluate(self, env: Dict[str, float]) -> bool:
        return all(item.evaluate(env) for item in self.items)


@dataclass(frozen=True)
class Disjunction:
    """Disjunction of clauses (c1 ∨ c2 ∨ ...).
    
    Can contain Relations or Conjunctions.
    """
    items: List[ClauseItem]

    def evaluate(self, env: Dict[str, float]) -> bool:
        return any(item.evaluate(env) for item in self.items)


# Top-level rule type
Rule = Disjunction