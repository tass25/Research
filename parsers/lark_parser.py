"""
Lark-based parser for operational rules.

Transforms string rules into strongly-typed schema objects.
"""

from pathlib import Path
from lark import Lark, Transformer, exceptions
from core.schema import (
    Variable, Constant, BinaryExpr,
    Relation, Conjunction, Disjunction
)
from core.types import RelOp, ArithOp
from core.config import GrammarConfig


class RuleTransformer(Transformer):
    """Transforms Lark parse tree into typed schema objects."""
    
    def __init__(self, config: GrammarConfig):
        super().__init__()
        self.config = config

    # Add this method to handle all terminals explicitly
    def __default__(self, data, children, meta):
        """Fallback for any unhandled rules."""
        if len(children) == 1:
            return children[0]
        return children

    def VARIABLE(self, token):
        """Transform VARIABLE token to Variable object."""
        name = str(token)
        if name not in self.config.allowed_variables:
            raise ValueError(
                f"Unknown variable: '{name}'. "
                f"Allowed: {sorted(self.config.allowed_variables)}"
            )
        return Variable(name)

    def NUMBER(self, token):
        """Transform NUMBER token to Constant object."""
        return Constant(float(token))

    def AOP(self, token):
        """Transform arithmetic operator token to ArithOp enum."""
        return ArithOp.from_string(token.value)

    def ROP(self, token):
        """Transform relational operator token to RelOp enum."""
        return RelOp.from_string(token.value)
    
    # Handle term rule explicitly
    def term(self, items):
        """Transform term rule - ensures terminals become objects."""
        if len(items) == 1:
            return items[0]  # Should already be Variable or Constant
        return items[0]  # Parenthesized expression

    def expression(self, items):
        """Transform expression rule."""
        if len(items) == 1:
            return items[0]
        # Binary expression: left op right
        return BinaryExpr(items[0], items[1], items[2])

    def relation(self, items):
        """Transform relation rule into Relation object."""
        # items should be [Expr, RelOp, Expr]
        # But if it matches the grouped_rule format (which is handled separately but might interact), be careful.
        # The grammar separates them: ?relation: expression ROP expression | "(" disjunction ")" -> grouped_rule
        
        # NOTE: If accessing directly via method name, it's specific.
        if len(items) != 3:
             # This might happen if the grammar rule for relation has other shapes, but
             # currently it's expr ROP expr.
             # However, grouped_rule handles the parens case.
             raise ValueError(f"Expected 3 items in relation, got {len(items)}: {items}")
        
        left, op, right = items
        
        # Defensive check
        if not isinstance(left, (Variable, Constant, BinaryExpr)):
            # It might be that 'left' is still a Token if not transformed?
            # But term/expression should have handled it.
            raise TypeError(f"Left side of relation is {type(left)}, expected Expr. Value: {left}")
        if not isinstance(op, RelOp):
            raise TypeError(f"Operator is {type(op)}, expected RelOp. Value: {op}")
        if not isinstance(right, (Variable, Constant, BinaryExpr)):
            raise TypeError(f"Right side of relation is {type(right)}, expected Expr. Value: {right}")
        
        return Relation(left, op, right)

    def conjunction(self, items):
        """Transform conjunction rule."""
        flattened = []
        for item in items:
            if isinstance(item, Conjunction):
                flattened.extend(item.items)
            elif isinstance(item, (Relation, Disjunction)): # Explicitly check for valid Schema objects
                flattened.append(item)
            # Ignore tokens (AND, OR)
        return Conjunction(flattened)

    def disjunction(self, items):
        """Transform disjunction rule."""
        flattened = []
        for item in items:
            if isinstance(item, Disjunction):
                flattened.extend(item.items)
            elif isinstance(item, (Relation, Conjunction)): # Explicitly check for valid Schema objects
                flattened.append(item)
            # Ignore tokens (AND, OR)
        return Disjunction(flattened)
    
    # Handle grouped rules
    def grouped_rule(self, items):
        """Handle parenthesized disjunction."""
        return items[0]


class OperationalRuleParser:
    """High-level parser API for operational rules."""
    
    def __init__(self, config: GrammarConfig):
        """Initialize parser with grammar configuration."""
        # Resolve grammar file path
        grammar_path = Path(__file__).parent.parent / "grammar" / "rules.lark"
        
        if not grammar_path.exists():
            raise FileNotFoundError(f"Grammar file not found: {grammar_path}")
        
        # Read grammar with explicit UTF-8 encoding
        with open(grammar_path, 'r', encoding='utf-8') as f:
            grammar_content = f.read()
        
        # Create parser with grammar content
        self.parser = Lark(
            grammar_content,
            parser="lalr",
            transformer=RuleTransformer(config),
            start="start",
        )
        self.config = config

    def parse(self, rule_str: str):
        """Parse a rule string into a typed Rule object."""
        try:
            # Normalize Unicode operators (fallback for compatibility)
            normalized = rule_str.replace("AND", "∧").replace("OR", "∨")
            
            # Strip whitespace and parse
            result = self.parser.parse(normalized.strip())
            
            # Ensure result is a Disjunction
            if not isinstance(result, Disjunction):
                if isinstance(result, (Relation, Conjunction)):
                    result = Disjunction([result])
                else:
                    raise ValueError(f"Unexpected parse result type: {type(result)}")
            
            return result
            
        except (exceptions.LarkError, ValueError) as e:
            raise ValueError(f"Parse error: {e}")

    def parse_safe(self, rule_str: str):
        """Safe parsing that returns errors instead of raising."""
        try:
            rule = self.parse(rule_str)
            return rule, []
        except ValueError as e:
            return None, [str(e)]