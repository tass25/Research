"""
Overfitting detector for semantic validation.

Detects boundary sensitivity, overly specific constants, and train/test gaps.
"""

from typing import List, Tuple, Optional, Set, Dict
from core.schema import Rule, Constant, BinaryExpr, Relation, Conjunction, Disjunction
from data.simulation_trace import SimulationDataset
from data.counterfactual_evidence import CounterfactualEvidence
from data.semantic_result import OverfittingIndicator
from semantic.consistency_checker import ConsistencyChecker
import numpy as np

def extract_constants(node) -> List[float]:
    """Helper to extract constants from a rule."""
    if isinstance(node, Constant):
        return [node.value]
    if isinstance(node, BinaryExpr):
        return extract_constants(node.left) + extract_constants(node.right)
    if isinstance(node, Relation):
        return extract_constants(node.left) + extract_constants(node.right)
    if isinstance(node, (Conjunction, Disjunction)):
        consts = []
        for item in node.items:
            consts.extend(extract_constants(item))
        return consts
    return []

class OverfittingDetector:
    """Detects overfitting in refined rules.
    
    From paper Lesson 2: "LLMs tend to increase apparent safety by tightening 
    bounds... this can over constrain the rule in a conservative way that is 
    not correctly grounded in the provided ODD, yielding many unnecessary 
    nominal restrictions."
    """

    def __init__(self, rule_set_type: str = "Pass"):
        """Initialize detector with the rule set type.
        
        Args:
            rule_set_type: "Pass" or "Fail" — needed so train/test gap
                           evaluation uses the correct semantics.
        """
        self.rule_set_type = rule_set_type
    
    def detect_overfitting(
        self,
        rule: Rule,
        counterfactual_evidence: CounterfactualEvidence,
        training_data: SimulationDataset,
        test_data: Optional[SimulationDataset] = None
    ) -> Tuple[float, List[OverfittingIndicator]]:
        """Detect overfitting indicators.
        
        Returns:
            (risk_score, list_of_indicators)
        """
        indicators = []
        
        # Indicator 1: Boundary sensitivity
        boundary_indicator = self._check_boundary_sensitivity(
            rule, counterfactual_evidence
        )
        if boundary_indicator:
            indicators.append(boundary_indicator)
        
        # Indicator 2: Overly specific constants
        specificity_indicator = self._check_constant_specificity(
            rule, counterfactual_evidence
        )
        if specificity_indicator:
            indicators.append(specificity_indicator)
        
        # Indicator 3: Train/test performance gap (if test data available)
        if test_data:
            gap_indicator = self._check_train_test_gap(
                rule, training_data, test_data
            )
            if gap_indicator:
                indicators.append(gap_indicator)
        
        # Indicator 4: Unnecessary restrictions
        restriction_indicator = self._check_unnecessary_restrictions(
            rule, counterfactual_evidence, training_data
        )
        if restriction_indicator:
            indicators.append(restriction_indicator)
        
        # Compute overall risk score
        risk_score = self._compute_risk_score(indicators)
        
        return risk_score, indicators
    
    def _check_boundary_sensitivity(
        self,
        rule: Rule,
        evidence: CounterfactualEvidence
    ) -> Optional[OverfittingIndicator]:
        """Check if rule is too sensitive to small perturbations.
        
        High sensitivity = overfitting indicator.
        """
        if not evidence.pairs:
            return None
        
        # Analyze perturbation magnitudes
        perturbation_sizes = [
            pair.perturbation_magnitude() 
            for pair in evidence.pairs
        ]
        
        avg_perturbation = np.mean(perturbation_sizes)
        
        # If average perturbation is very small, rule is boundary-sensitive
        if avg_perturbation < 0.5:  # Threshold depends on domain
            return OverfittingIndicator(
                indicator_type="boundary_sensitive",
                severity=1.0 - (avg_perturbation / 0.5),
                evidence=f"Rule changes verdict with average perturbation of {avg_perturbation:.3f}",
                affected_variables=set().union(
                    *[pair.get_changed_variables() for pair in evidence.pairs]
                )
            )
        
        return None
    
    def _check_constant_specificity(
        self,
        rule: Rule,
        evidence: CounterfactualEvidence
    ) -> Optional[OverfittingIndicator]:
        """Check if constants in rule are overly specific.
        
        Example: dist_front < 4.1 might be overfitting to a specific case,
        whereas dist_front < 5.0 would be more general.
        """
        # Extract constants from rule
        constants = extract_constants(rule)  # Helper from Part 1
        
        # Check if constants have suspicious precision
        overly_specific = []
        for const in constants:
            # If constant has > 1 decimal place, might be overfitting (heuristic)
            if abs(const - round(const, 1)) > 1e-6:
                overly_specific.append(const)
        
        if overly_specific:
            return OverfittingIndicator(
                indicator_type="overly_specific",
                severity=len(overly_specific) / len(constants) if constants else 0,
                evidence=f"Rule contains overly specific constants: {overly_specific}",
                affected_variables=set()  # Would need to track which vars
            )
        
        return None
    
    def _check_train_test_gap(
        self,
        rule: Rule,
        training_data: SimulationDataset,
        test_data: SimulationDataset,
        threshold: float = 0.15
    ) -> Optional[OverfittingIndicator]:
        """Check for train/test performance gap.
        
        Uses self.rule_set_type so Fail-set rules are evaluated correctly.
        """
        # Evaluate on training data — use actual rule_set_type, not hardcoded "Pass"
        train_score, _ = ConsistencyChecker(self.rule_set_type).check_consistency(
            rule, training_data
        )
        
        # Evaluate on test data
        test_score, _ = ConsistencyChecker(self.rule_set_type).check_consistency(
            rule, test_data
        )
        
        gap = train_score - test_score
        
        if gap > threshold:  # Configurable performance drop
            return OverfittingIndicator(
                indicator_type="train_test_gap",
                severity=min(gap / 0.3, 1.0),  # Normalize to [0, 1]
                evidence=f"Training score {train_score:.2f} vs test score {test_score:.2f}",
                affected_variables=set()
            )
        
        return None
        
    def _check_unnecessary_restrictions(
        self,
        rule: Rule,
        evidence: CounterfactualEvidence,
        training_data: Optional[SimulationDataset] = None,
    ) -> Optional[OverfittingIndicator]:
        """Detect predicates that restrict the rule without improving safety.

        Strategy: for Conjunction rules, try removing each predicate and
        check if the consistency score stays the same or improves.  If
        removing a predicate does NOT hurt consistency, it is likely
        unnecessary.
        """
        if training_data is None:
            return None

        # Only works for conjunction rules (most common after inference)
        if not isinstance(rule, (Conjunction, Disjunction)):
            return None

        # Flatten to get the list of items to test
        if isinstance(rule, Disjunction) and len(rule.items) == 1:
            inner = rule.items[0]
            if isinstance(inner, Conjunction):
                items = inner.items
            else:
                return None  # Single relation, nothing to drop
        elif isinstance(rule, Conjunction):
            items = rule.items
        else:
            return None  # Multi-clause disjunction, too complex for this heuristic

        if len(items) <= 1:
            return None  # Nothing to drop

        # Baseline score with all predicates
        checker = ConsistencyChecker(self.rule_set_type)
        baseline_score, _ = checker.check_consistency(rule, training_data)

        unnecessary = []
        for i, item in enumerate(items):
            # Build rule without predicate i
            remaining = [it for j, it in enumerate(items) if j != i]
            if len(remaining) == 1:
                reduced_rule = Disjunction([remaining[0]])
            else:
                reduced_rule = Disjunction([Conjunction(remaining)])

            reduced_score, _ = checker.check_consistency(reduced_rule, training_data)
            if reduced_score >= baseline_score - 1e-9:
                unnecessary.append(str(item))

        if unnecessary:
            return OverfittingIndicator(
                indicator_type="unnecessary_restriction",
                severity=len(unnecessary) / len(items),
                evidence=f"Removing these predicates does not hurt consistency: {unnecessary}",
                affected_variables=set(),
            )

        return None
    
    def _compute_risk_score(
        self,
        indicators: List[OverfittingIndicator]
    ) -> float:
        """Aggregate indicator severities into overall risk score."""
        if not indicators:
            return 0.0
        
        # Weighted average of severities
        return min(sum(ind.severity for ind in indicators) / len(indicators), 1.0)
