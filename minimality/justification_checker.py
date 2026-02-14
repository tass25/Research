"""
Justification checker for minimality analysis.

Checks if bound changes are justified by counterfactual evidence.
"""

from typing import Tuple, List
from data.minimality_result import RelationChange
from data.counterfactual_evidence import CounterfactualEvidence


class JustificationChecker:
    """Checks if bound changes are justified by counterfactual evidence.
    
    From paper: Changes should be grounded in counterfactual evidence,
    not arbitrary tightening.
    """
    
    def check_justification(
        self,
        change: RelationChange,
        counterfactual_evidence: CounterfactualEvidence
    ) -> Tuple[bool, str]:
        """Check if a relation change is justified by evidence.
        
        Justification criteria:
        1. Counterfactual evidence involves the changed variable
        2. Counterfactual values cluster near the new bound
        3. Change direction aligns with counterfactual pattern
        
        Args:
            change: RelationChange to check
            counterfactual_evidence: Counterfactual pairs for analysis
            
        Returns:
            (is_justified, explanation)
        """
        if not counterfactual_evidence.pairs:
            return False, "No counterfactual evidence provided"
        
        # Extract counterfactuals involving this variable
        relevant_pairs = [
            pair for pair in counterfactual_evidence.pairs
            if change.variable in pair.get_changed_variables()
        ]
        
        if not relevant_pairs:
            return False, f"No counterfactuals involve variable '{change.variable}'"
        
        # Extract counterfactual values for this variable
        cf_values = []
        for pair in relevant_pairs:
            if change.variable in pair.counterfactual_input:
                cf_values.append(pair.counterfactual_input[change.variable])
        
        if not cf_values:
            return False, "No counterfactual values found for this variable"
        
        # Check 1: Clustering near refined value
        is_clustered, cluster_explanation = self._check_clustering(
            change, cf_values
        )
        
        if is_clustered:
            return True, cluster_explanation
        
        # Check 2: Boundary alignment
        is_aligned, alignment_explanation = self._check_boundary_alignment(
            change, cf_values, relevant_pairs
        )
        
        if is_aligned:
            return True, alignment_explanation
        
        # Not justified
        avg_distance = sum(abs(val - change.refined_constant) for val in cf_values) / len(cf_values)
        return False, f"Counterfactuals not aligned with change (avg distance: {avg_distance:.2f})"
    
    def _check_clustering(
        self,
        change: RelationChange,
        cf_values: List[float]
    ) -> Tuple[bool, str]:
        """Check if counterfactual values cluster near refined constant.
        
        Args:
            change: RelationChange being checked
            cf_values: List of counterfactual values for the variable
            
        Returns:
            (is_clustered, explanation)
        """
        # Compute distances from counterfactuals to refined value
        distances = [abs(val - change.refined_constant) for val in cf_values]
        avg_distance = sum(distances) / len(distances)
        
        # Threshold: counterfactuals should be within 50% of change magnitude
        threshold = abs(change.delta) * 0.5
        
        if avg_distance <= threshold:
            return True, (
                f"Counterfactuals cluster near refined value "
                f"(avg distance: {avg_distance:.2f}, threshold: {threshold:.2f})"
            )
        
        return False, ""
    
    def _check_boundary_alignment(
        self,
        change: RelationChange,
        cf_values: List[float],
        relevant_pairs
    ) -> Tuple[bool, str]:
        """Check if change direction aligns with counterfactual pattern.
        
        For tightening: counterfactuals should show violations near new bound
        For loosening: counterfactuals should show safe region expansion
        
        Args:
            change: RelationChange being checked
            cf_values: List of counterfactual values
            relevant_pairs: Relevant counterfactual pairs
            
        Returns:
            (is_aligned, explanation)
        """
        if change.change_type != "tightening":
            # For now, only validate tightening
            return False, ""
        
        # Count how many counterfactuals are near the new bound
        threshold = abs(change.delta) * 0.5
        near_bound_count = sum(
            1 for val in cf_values
            if abs(val - change.refined_constant) <= threshold
        )
        
        # If majority of counterfactuals are near new bound, it's justified
        if near_bound_count >= len(cf_values) * 0.5:
            return True, (
                f"{near_bound_count}/{len(cf_values)} counterfactuals near new bound "
                f"(within {threshold:.2f})"
            )
        
        return False, ""
