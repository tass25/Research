"""
Change extractor for minimality analysis.

Extracts and matches relations between original and refined rules to detect changes.
"""

from typing import List, Tuple, Optional
from core.schema import Rule, Relation, Conjunction, Disjunction, Variable, Constant, BinaryExpr
from core.types import RelOp
from data.minimality_result import RelationChange


class ChangeExtractor:
    """Extracts relation-level changes between original and refined rules.
    
    Matches relations by (variable, operator) and computes deltas in constants.
    """
    
    def extract_changes(
        self,
        original_rule: Rule,
        refined_rule: Rule
    ) -> List[RelationChange]:
        """Extract all relation changes between rules.
        
        Algorithm:
        1. Extract all relations from both rules
        2. Match relations by (variable, operator)
        3. Compute delta for matched pairs
        4. Classify as tightening/loosening/unchanged
        
        Args:
            original_rule: Original rule before refinement
            refined_rule: Refined rule after LLM modification
            
        Returns:
            List of RelationChange objects
        """
        original_relations = self._extract_relations(original_rule)
        refined_relations = self._extract_relations(refined_rule)
        
        changes = []
        matched_refined = set()
        
        # Match relations from original to refined
        for orig_rel in original_relations:
            orig_parsed = self._parse_relation(orig_rel)
            if orig_parsed is None:
                continue
            
            orig_var, orig_op, orig_const = orig_parsed
            
            # Find matching refined relation
            for i, ref_rel in enumerate(refined_relations):
                if i in matched_refined:
                    continue
                
                ref_parsed = self._parse_relation(ref_rel)
                if ref_parsed is None:
                    continue
                
                ref_var, ref_op, ref_const = ref_parsed
                
                # Match by variable and operator
                if orig_var == ref_var and orig_op == ref_op:
                    # Compute change
                    delta = ref_const - orig_const
                    change_type = self._classify_change(orig_op, delta)
                    if change_type == "unchanged":
                        matched_refined.add(i)
                        break
                    magnitude = abs(delta) / abs(orig_const) if orig_const != 0 else 0.0
                    
                    changes.append(RelationChange(
                        variable=orig_var,
                        operator=str(orig_op.value),
                        original_constant=orig_const,
                        refined_constant=ref_const,
                        delta=delta,
                        change_type=change_type,
                        magnitude=magnitude,
                        is_justified=False,  # Determined by JustificationChecker
                        justification=""
                    ))
                    
                    matched_refined.add(i)
                    break
        
        return changes
    
    def _extract_relations(self, rule: Rule) -> List[Relation]:
        """Recursively extract all Relation objects from rule.
        
        Args:
            rule: Rule to extract from
            
        Returns:
            List of Relation objects
        """
        relations = []
        
        if isinstance(rule, Relation):
            relations.append(rule)
        elif isinstance(rule, (Conjunction, Disjunction)):
            for item in rule.items:
                relations.extend(self._extract_relations(item))
        
        return relations
    
    def _parse_relation(self, rel: Relation) -> Optional[Tuple[str, RelOp, float]]:
        """Extract (variable, operator, constant) from Relation.
        
        Handles both:
        - Variable < Constant  (e.g., dist_front < 5)
        - Constant > Variable  (e.g., 5 > dist_front)
        
        Args:
            rel: Relation object to parse
            
        Returns:
            (variable_name, operator, constant_value) or None if not parseable
        """
        left = rel.left
        op = rel.op
        right = rel.right
        
        # Case 1: Variable op Constant
        if isinstance(left, Variable) and isinstance(right, Constant):
            return (left.name, op, right.value)
        
        # Case 2: Constant op Variable (need to flip operator)
        if isinstance(left, Constant) and isinstance(right, Variable):
            flipped_op = self._flip_operator(op)
            if flipped_op:
                return (right.name, flipped_op, left.value)
        
        # Case 3: Complex expressions - not supported yet
        # For now, only handle simple Variable op Constant relations
        return None
    
    def _flip_operator(self, op: RelOp) -> Optional[RelOp]:
        """Flip operator for Constant op Variable → Variable op Constant.
        
        Example: 5 > x becomes x < 5
        """
        flip_map = {
            RelOp.LT: RelOp.GT,
            RelOp.LE: RelOp.GE,
            RelOp.GT: RelOp.LT,
            RelOp.GE: RelOp.LE,
            RelOp.EQ: RelOp.EQ,
            RelOp.NE: RelOp.NE,
        }
        return flip_map.get(op)
    
    def _classify_change(self, operator: RelOp, delta: float) -> str:
        """Classify change as tightening, loosening, or unchanged.
        
        Logic:
        - For < or <=: negative delta = tightening (smaller upper bound)
        - For > or >=: positive delta = tightening (larger lower bound)
        - For = or !=: any change = modification
        
        Args:
            operator: Relational operator
            delta: Change in constant (refined - original)
            
        Returns:
            "tightening" | "loosening" | "unchanged"
        """
        if abs(delta) < 1e-9:  # Floating point tolerance
            return "unchanged"
        
        if operator in [RelOp.LT, RelOp.LE]:
            # For upper bounds, smaller = tightening
            return "tightening" if delta < 0 else "loosening"
        
        elif operator in [RelOp.GT, RelOp.GE]:
            # For lower bounds, larger = tightening
            return "tightening" if delta > 0 else "loosening"
        
        else:  # EQ or NE
            return "tightening"  # Any change to equality is considered tightening
