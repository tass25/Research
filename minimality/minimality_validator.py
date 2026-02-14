"""
Main minimality validator orchestrator.

Combines all minimality analysis components.
"""

from typing import Dict, Tuple, Optional, List
from core.schema import Rule
from data.counterfactual_evidence import CounterfactualEvidence
from data.minimality_result import MinimalityResult, RelationChange
from minimality.change_extractor import ChangeExtractor
from minimality.bound_analyzer import BoundAnalyzer
from minimality.justification_checker import JustificationChecker
from minimality.minimality_scorer import MinimalityScorer


class MinimalityValidator:
    """Main orchestrator for change minimality analysis.
    
    Coordinates extraction, analysis, justification checking, and scoring
    of bound changes between original and refined rules.
    """
    
    def __init__(
        self,
        variable_bounds: Dict[str, Tuple[float, float]],
        minimality_threshold: float = 0.7
    ):
        """Initialize minimality validator.
        
        Args:
            variable_bounds: ODD bounds for severity computation
            minimality_threshold: Score threshold for passing (default 0.7)
        """
        self.change_extractor = ChangeExtractor()
        self.bound_analyzer = BoundAnalyzer()
        self.justification_checker = JustificationChecker()
        self.minimality_scorer = MinimalityScorer()
        self.variable_bounds = variable_bounds
        self.minimality_threshold = minimality_threshold
    
    def validate(
        self,
        original_rule: Rule,
        refined_rule: Rule,
        counterfactual_evidence: Optional[CounterfactualEvidence] = None
    ) -> MinimalityResult:
        """Perform complete minimality analysis.
        
        Pipeline:
        1. Extract relation changes
        2. Check justification (if evidence provided)
        3. Compute overall score
        4. Categorize changes
        5. Make pass/fail decision
        
        Args:
            original_rule: Original rule before refinement
            refined_rule: Refined rule from LLM
            counterfactual_evidence: Optional evidence for justification
            
        Returns:
            MinimalityResult with complete analysis
        """
        # Step 1: Extract changes
        changes = self.change_extractor.extract_changes(
            original_rule, refined_rule
        )
        
        if not changes:
            # No changes detected = perfectly minimal
            return MinimalityResult(
                original_rule=str(original_rule),
                refined_rule=str(refined_rule),
                overall_score=1.0,
                relation_changes=[],
                unjustified_tightenings=[],
                unjustified_loosenings=[],
                total_changes=0,
                justified_changes=0,
                passed_minimality=True
            )
        
        # Step 2: Check justification for each change (if evidence provided)
        if counterfactual_evidence:
            changes = self._check_justifications(changes, counterfactual_evidence)
        
        # Step 3: Compute overall score
        overall_score = self.minimality_scorer.compute_score(changes)
        
        # Step 4: Categorize changes
        unjustified_tightenings = [
            c for c in changes
            if c.change_type == "tightening" and not c.is_justified
        ]
        
        unjustified_loosenings = [
            c for c in changes
            if c.change_type == "loosening" and not c.is_justified
        ]
        
        justified_count = sum(1 for c in changes if c.is_justified)
        
        # Step 5: Make pass/fail decision
        passed = overall_score >= self.minimality_threshold
        
        return MinimalityResult(
            original_rule=str(original_rule),
            refined_rule=str(refined_rule),
            overall_score=overall_score,
            relation_changes=changes,
            unjustified_tightenings=unjustified_tightenings,
            unjustified_loosenings=unjustified_loosenings,
            total_changes=len(changes),
            justified_changes=justified_count,
            passed_minimality=passed
        )
    
    def _check_justifications(
        self,
        changes: List[RelationChange],
        evidence: CounterfactualEvidence
    ) -> List[RelationChange]:
        """Check justification for all changes and update them.
        
        Args:
            changes: List of changes to check
            evidence: Counterfactual evidence for justification
            
        Returns:
            Updated list of changes with justification info
        """
        updated_changes = []
        
        for change in changes:
            is_justified, explanation = self.justification_checker.check_justification(
                change, evidence
            )
            
            # Create updated RelationChange with justification info
            updated_change = RelationChange(
                variable=change.variable,
                operator=change.operator,
                original_constant=change.original_constant,
                refined_constant=change.refined_constant,
                delta=change.delta,
                change_type=change.change_type,
                magnitude=change.magnitude,
                is_justified=is_justified,
                justification=explanation
            )
            
            updated_changes.append(updated_change)
        
        return updated_changes
