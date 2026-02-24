"""
Core type definitions for the grammar schema.

Defines type-safe enumerations for all operators used in operational rules.
"""

from enum import Enum


class RelOp(Enum):
    """Relational operators allowed in the grammar."""
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    EQ = "="
    NE = "!="
    
    @classmethod
    def from_string(cls, s: str) -> 'RelOp':
        """Parse relational operator from string token."""
        mapping = {
            "<": cls.LT,
            "<=": cls.LE,
            ">": cls.GT,
            ">=": cls.GE,
            "=": cls.EQ,
            "!=": cls.NE,
        }
        if s not in mapping:
            raise ValueError(f"Invalid relational operator: {s}")
        return mapping[s]


class ArithOp(Enum):
    """Arithmetic operators allowed in the grammar."""
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"
    
    @classmethod
    def from_string(cls, s: str) -> 'ArithOp':
        """Parse arithmetic operator from string token."""
        mapping = {
            "+": cls.ADD,
            "-": cls.SUB,
            "*": cls.MUL,
            "/": cls.DIV,
        }
        if s not in mapping:
            raise ValueError(f"Invalid arithmetic operator: {s}")
        return mapping[s]