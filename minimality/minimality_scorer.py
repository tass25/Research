"""
Minimality scorer.

Computes overall minimality score from relation changes.
"""

from typing import List
from data.minimality_result import RelationChange


class MinimalityScorer:
    """Computes overall minimality score from analyzed changes."""
    
    def compute_score(self, changes: List[RelationChange]) -> float:
        """Compute minimality score.
        
        Score interpretation:
        - 1.0: All changes minimal and justified (perfect)
        - 0.7-0.9: Mostly justified changes (good)
        - 0.4-0.7: Mixed justification (questionable)
        - 0.0-0.4: Mostly unjustified changes (bad)
        
        Formula:
            score = (justified_weight + magnitude_penalty) / 2
            
            justified_weight = justified_changes / total_changes
            magnitude_penalty = 1 - avg(magnitude of unjustified tightenings)
        
        Args:
            changes: List of RelationChange objects
            
        Returns:
            Minimality score (0.0 to 1.0)
        """
        if not changes:
            return 1.0  # No changes = perfectly minimal
        
        # Component 1: Justification ratio
        justified_count = sum(1 for c in changes if c.is_justified)
        total_count = len(changes)
        justified_weight = justified_count / total_count
        
        # Component 2: Penalty for unjustified tightenings
        unjustified_tightenings = [
            c for c in changes
            if c.change_type == "tightening" and not c.is_justified
        ]
        
        if unjustified_tightenings:
            # Average magnitude of unjustified tightenings
            avg_magnitude = sum(c.magnitude for c in unjustified_tightenings) / len(unjustified_tightenings)
            # Penalty: higher magnitude = lower score
            magnitude_penalty = 1.0 - min(avg_magnitude, 1.0)
        else:
            # No unjustified tightenings = no penalty
            magnitude_penalty = 1.0
        
        # Combine components (equal weight)
        score = (justified_weight + magnitude_penalty) / 2
        
        # Clamp to [0, 1]
        return max(0.0, min(score, 1.0))
    
    def compute_weighted_score(
        self,
        changes: List[RelationChange],
        justification_weight: float = 0.7,
        magnitude_weight: float = 0.3
    ) -> float:
        """Compute score with custom weights.
        
        Args:
            changes: List of RelationChange objects
            justification_weight: Weight for justification ratio (0.0 to 1.0)
            magnitude_weight: Weight for magnitude penalty (0.0 to 1.0)
            
        Returns:
            Weighted minimality score
        """
        if not changes:
            return 1.0
        
        # Normalize weights
        total_weight = justification_weight + magnitude_weight
        if total_weight == 0:
            return 0.0
        
        just_w = justification_weight / total_weight
        mag_w = magnitude_weight / total_weight
        
        # Justification component
        justified_count = sum(1 for c in changes if c.is_justified)
        justified_ratio = justified_count / len(changes)
        
        # Magnitude component
        unjustified_changes = [
            c for c in changes
            if c.change_type != "unchanged" and not c.is_justified
        ]
        
        if unjustified_changes:
            avg_magnitude = sum(c.magnitude for c in unjustified_changes) / len(unjustified_changes)
            avg_magnitude = min(avg_magnitude, 1.0)
            magnitude_penalty = max(0.0, 1.0 - avg_magnitude)
        else:
            magnitude_penalty = 1.0
        
        # Weighted combination
        score = (just_w * justified_ratio) + (mag_w * magnitude_penalty)
        
        return max(0.0, min(score, 1.0))
