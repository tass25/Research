# Importing necessary modules
from lark import Lark, Transformer, exceptions
from core.schema import (
    Variable, Constant, BinaryExpr,
    Relation, Conjunction, Disjunction
)
from core.types import RelOp, ArithOp
from core.config import GrammarConfig


# This class transforms the parsed tree from Lark into our Python objects
class RuleTransformer(Transformer):
    def __init__(self, config: GrammarConfig):
        self.config = config  # We use config to know which variables are allowed

    # Convert VARIABLE token into a Variable object
    def VARIABLE(self, token):
        name = str(token)
        if name not in self.config.allowed_variables:
            # If variable is not allowed, raise an error
            raise ValueError(f"Unknown variable: {name}")
        return Variable(name)

    # Convert NUMBER token into a Constant object
    def NUMBER(self, token):
        return Constant(float(token))

    # Convert arithmetic operator token into ArithOp enum
    def AOP(self, token):
        return ArithOp(token.value)

    # Convert relational operator token into RelOp enum
    def ROP(self, token):
        return RelOp(token.value)

    # Transform expression nodes
    # If it's just a single item, return it
    # Otherwise, it's a binary expression (like x + 5)
    def expression(self, items):
        if len(items) == 1:
            return items[0]
        return BinaryExpr(items[0], items[1], items[2])

    # Transform a relation node (like x > 5)
    def relation(self, items):
        return Relation(items[0], items[1], items[2])

    # Transform a conjunction node (AND)
    def conjunction(self, items):
        if len(items) == 1:
            return Conjunction([items[0]])  # Wrap single relation in a list
        return Conjunction(items)

    # Transform a disjunction node (OR)
    def disjunction(self, items):
        if len(items) == 1:
            return Disjunction([items[0]])  # Wrap single conjunction in a list
        return Disjunction(items)


# This class is the main parser interface for operational rules
class OperationalRuleParser:
    def __init__(self, config: GrammarConfig):
        self.config = config
        # Load the grammar from the .lark file
        self.parser = Lark.open(
            "grammar/rules.lark",  # Path to the grammar file
            parser="lalr",          # Use LALR parser (fast and efficient)
            start="start",          # Start symbol in the grammar
            transformer=RuleTransformer(config),  # Transform parse tree to Python objects
        )

    # Preprocess rule string before parsing
    def _preprocess(self, rule_str: str) -> str:
        rule_str = rule_str.strip()  # Remove extra spaces
        # Remove code block markers if they exist (``` ... ```)
        if rule_str.startswith("```") and rule_str.endswith("```"):
            return "\n".join(rule_str.splitlines()[1:-1])
        return rule_str

    # Parse the rule string into Python objects
    def parse(self, rule_str: str):
        try:
            return self.parser.parse(self._preprocess(rule_str))
        except (exceptions.LarkError, ValueError) as e:
            # Raise error if parsing fails
            raise ValueError(str(e))

    # Safe parse: returns (result, errors)
    # If parsing fails, result is None and errors contain the messages
    def parse_safe(self, rule_str: str):
        try:
            return self.parse(rule_str), []
        except ValueError as e:
            return None, [str(e)]