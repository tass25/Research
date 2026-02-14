"""
Main semantic validator orchestrator.

Combines consistency, contradiction, and overfitting checks.
"""

from typing import List, Tuple, Dict, Optional
from core.schema import Rule
from data.simulation_trace import SimulationDataset
from data.counterfactual_evidence import CounterfactualEvidence
from data.semantic_result import SemanticValidationResult
from semantic.consistency_checker import ConsistencyChecker
from semantic.contradiction_checker import ContradictionChecker
from semantic.overfitting_detector import OverfittingDetector

class SemanticValidator:
    """Main orchestrator for semantic validation.
    
    Combines consistency, contradiction, and overfitting checks.
    """
    
    def __init__(
        self,
        rule_set_type: str,
        historical_rules: List[Tuple[Rule, str]] = None,
        variable_bounds: Dict[str, Tuple[float, float]] = None
    ):
        """
        Args:
            rule_set_type: "Pass" or "Fail"
            historical_rules: Existing rules to check contradictions against
            variable_bounds: For contradiction test point generation
        """
        self.rule_set_type = rule_set_type
        self.consistency_checker = ConsistencyChecker(rule_set_type)
        self.contradiction_checker = ContradictionChecker()
        self.overfitting_detector = OverfittingDetector()
        self.historical_rules = historical_rules or []
        self.variable_bounds = variable_bounds or {}
    
    def validate(
        self,
        rule: Rule,
        training_data: SimulationDataset,
        counterfactual_evidence: Optional[CounterfactualEvidence] = None,
        test_data: Optional[SimulationDataset] = None
    ) -> SemanticValidationResult:
        """Perform complete semantic validation.
        
        Returns:
            SemanticValidationResult with all checks
        """
        # Step 1: Consistency check
        consistency_score, consistency_issues = self.consistency_checker.check_consistency(
            rule, training_data
        )
        is_consistent = consistency_score >= 0.95  # 95% threshold
        
        # Step 2: Contradiction check
        test_points = self.contradiction_checker.generate_test_points(
            variables=set(self.variable_bounds.keys()),
            bounds=self.variable_bounds,
            num_points=1000
        )
        contradictions = self.contradiction_checker.check_contradictions(
            current_rule=rule,
            current_rule_type=self.rule_set_type,
            historical_rules=self.historical_rules,
            test_points=test_points
        )
        has_contradictions = len(contradictions) > 0
        
        # Step 3: Overfitting detection
        overfitting_risk = 0.0
        overfitting_indicators = []
        if counterfactual_evidence:
            overfitting_risk, overfitting_indicators = self.overfitting_detector.detect_overfitting(
                rule=rule,
                counterfactual_evidence=counterfactual_evidence,
                training_data=training_data,
                test_data=test_data
            )
        
        # Overall decision
        passed_validation = (
            is_consistent and 
            not has_contradictions and 
            overfitting_risk < 0.7  # Risk threshold
        )
        
        return SemanticValidationResult(
            rule=str(rule),
            is_consistent=is_consistent,
            consistency_score=consistency_score,
            consistency_issues=consistency_issues,
            has_contradictions=has_contradictions,
            contradictions=contradictions,
            overfitting_risk=overfitting_risk,
            overfitting_indicators=overfitting_indicators,
            passed_validation=passed_validation
        )
