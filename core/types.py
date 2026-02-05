from enum import Enum


class RelOp(Enum):
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    EQ = "="
    NE = "!="


class ArithOp(Enum):
    ADD = "+"
    SUB = "-"
    MUL = "*"
    DIV = "/"


class LogicOp(Enum):
    AND = "∧"
    OR = "∨"