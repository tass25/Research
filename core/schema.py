# Importing modules we need

from dataclasses import dataclass
from typing import Dict, List
from core.types import RelOp, ArithOp


# Base class for all expressions
# An "expression" can be a number, variable, or a calculation
class Expr:
    def evaluate(self, env: Dict[str, float]) -> float:
        raise NotImplementedError


# Represents a variable, like x or y
@dataclass(frozen=True)
class Variable(Expr):
    name: str  # The name of the variable

    def evaluate(self, env: Dict[str, float]) -> float:
        # To evaluate a variable, we look up its value in the environment dictionary
        return env[self.name]


# Represents a constant number, like 5 or 3.14
@dataclass(frozen=True)
class Constant(Expr):
    value: float  # The numeric value

    def evaluate(self, env: Dict[str, float]) -> float:
        # Constants evaluate to themselves
        return self.value


# Represents a binary operation (like addition, subtraction, multiplication, division)
@dataclass(frozen=True)
class BinaryExpr(Expr):
    left: Expr    # Left side of the operation (can be a Variable, Constant, or another BinaryExpr)
    op: ArithOp   # The arithmetic operation to perform (+, -, *, /)
    right: Expr   # Right side of the operation

    def evaluate(self, env: Dict[str, float]) -> float:
        # First, evaluate both sides recursively
        l, r = self.left.evaluate(env), self.right.evaluate(env)

        # Perform the operation based on 'op'
        if self.op == ArithOp.ADD:
            return l + r
        if self.op == ArithOp.SUB:
            return l - r
        if self.op == ArithOp.MUL:
            return l * r
        if self.op == ArithOp.DIV:
            return l / r

        # If we get an unknown operation, raise an error
        raise ValueError("Unknown arithmetic operator")


# Represents a comparison between two expressions (like x > 5)
@dataclass(frozen=True)
class Relation:
    left: Expr   # Left expression
    op: RelOp    # Relational operator (<, <=, >, >=, ==, !=)
    right: Expr  # Right expression

    def evaluate(self, env: Dict[str, float]) -> bool:
        # Evaluate both sides
        l, r = self.left.evaluate(env), self.right.evaluate(env)

        # Return the result of the comparison
        return {
            RelOp.LT: l < r,   # less than
            RelOp.LE: l <= r,  # less than or equal
            RelOp.GT: l > r,   # greater than
            RelOp.GE: l >= r,  # greater than or equal
            RelOp.EQ: l == r,  # equal
            RelOp.NE: l != r,  # not equal
        }[self.op]


# Represents an AND of multiple relations
# For example: (x > 1 AND y < 5)
@dataclass(frozen=True)
class Conjunction:
    relations: List[Relation]  # List of Relation objects

    def evaluate(self, env: Dict[str, float]) -> bool:
        # Return True only if ALL relations are True
        return all(r.evaluate(env) for r in self.relations)


# Represents an OR of multiple conjunctions
# For example: (x > 1 AND y < 5) OR (x == 0)
@dataclass(frozen=True)
class Disjunction:
    clauses: List[Conjunction]  # List of Conjunction objects

    def evaluate(self, env: Dict[str, float]) -> bool:
        # Return True if ANY conjunction is True
        return any(c.evaluate(env) for c in self.clauses)


# A Rule is just a Disjunction (so it can have ORs of ANDs of relations)
Rule = Disjunction