"""
Contradiction checker for semantic validation.

Detects contradictions between current and historical rules.
"""

import logging
import random
from typing import List, Tuple, Dict, Set
from core.schema import Rule
from data.semantic_result import ContradictionIssue

logger = logging.getLogger(__name__)


class ContradictionChecker:
    """Detects contradictions between current and historical rules.
    
    From paper: "No contradictions - there is no (x, y) such that a pass rule
    and a fail rule both hold on x."
    """

    def __init__(self, seed: int = 42):
        """Initialize with a reproducible random seed.
        
        Args:
            seed: Random seed for test point generation (default 42).
        """
        self._rng = random.Random(seed)
    
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
        2. Return contradictions (deduplicated by rule pair)
        
        Args:
            current_rule: The rule being validated.
            current_rule_type: "Pass" or "Fail".
            historical_rules: Existing rules to check against.
            test_points: Input vectors to evaluate.
            
        Raises:
            ValueError: If current_rule_type is not "Pass" or "Fail".
        """
        if current_rule_type not in ("Pass", "Fail"):
            raise ValueError(
                f"current_rule_type must be 'Pass' or 'Fail', got '{current_rule_type}'"
            )

        contradictions = []
        # Track which (current, historical) pairs already have a reported
        # contradiction to avoid N duplicate reports for the same pair.
        seen_pairs: set = set()
        
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
                
                # Deduplicate: only report first witness per rule pair
                pair_key = (str(current_rule), str(hist_rule))
                if pair_key in seen_pairs:
                    continue

                try:
                    hist_holds = hist_rule.evaluate(test_point)
                except KeyError:
                    continue
                
                if hist_holds:
                    # CONTRADICTION FOUND!
                    seen_pairs.add(pair_key)
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
        
        Uses seeded random sampling within variable bounds.
        Variables without bounds generate a warning and use range [-10, 10].
        """
        points = []
        # Warn about unbound variables once
        unbound = variables - set(bounds.keys())
        if unbound:
            logger.warning(
                "Variables %s have no bounds defined — using default range [-10, 10]",
                sorted(unbound),
            )

        for _ in range(num_points):
            point = {}
            for var in variables:
                if var in bounds:
                    min_val, max_val = bounds[var]
                    point[var] = self._rng.uniform(min_val, max_val)
                else:
                    point[var] = self._rng.uniform(-10.0, 10.0)
            points.append(point)
        return points
