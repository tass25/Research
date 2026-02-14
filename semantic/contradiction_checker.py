"""
Contradiction checker for semantic validation.

Detects contradictions between current and historical rules.
"""

from typing import List, Tuple, Dict, Set
from core.schema import Rule
from data.semantic_result import ContradictionIssue
import random

class ContradictionChecker:
    """Detects contradictions between current and historical rules.
    
    From paper: "No contradictions - there is no (x, y) such that a pass rule
    and a fail rule both hold on x."
    """
    
    def check_contradictions(
        self,
        current_rule: Rule,
        current_rule_type: str,      # "Pass" or "Fail"
        historical_rules: List[Tuple[Rule, str]],  # List of (rule, type)
        test_points: List[Dict[str, float]]  # Inputs to test
    ) -> List[ContradictionIssue]:
        """Find contradictions.
        
        Algorithm:
        1. For each test point:
            - Evaluate current_rule
            - Evaluate all historical rules
            - Check if any opposite-type rule also holds
        2. Return contradictions
        """
        contradictions = []
        
        for test_point in test_points:
            try:
                current_holds = current_rule.evaluate(test_point)
            except KeyError:
                continue

            if not current_holds:
                continue  # Current rule doesn't apply
            
            # Check historical rules of opposite type
            for hist_rule, hist_type in historical_rules:
                if hist_type == current_rule_type:
                    continue  # Same type, not a contradiction
                
                try:
                    hist_holds = hist_rule.evaluate(test_point)
                except KeyError:
                    continue
                
                if hist_holds:
                    # CONTRADICTION FOUND!
                    contradictions.append(ContradictionIssue(
                        current_rule=str(current_rule),
                        historical_rule=str(hist_rule),
                        conflicting_input=test_point,
                        explanation=f"{current_rule_type} rule and {hist_type} rule both hold"
                    ))
        
        return contradictions
    
    def generate_test_points(
        self,
        variables: Set[str],
        bounds: Dict[str, Tuple[float, float]],
        num_points: int = 1000
    ) -> List[Dict[str, float]]:
        """Generate random test points for contradiction checking.
        
        Uses random sampling within variable bounds.
        """
        points = []
        for _ in range(num_points):
            point = {}
            for var in variables:
                if var in bounds:
                    min_val, max_val = bounds[var]
                    point[var] = random.uniform(min_val, max_val)
                else:
                    point[var] = 0.0 # Default fallback
            points.append(point)
        return points
