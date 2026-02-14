"""
Bound analyzer for minimality analysis.

Analyzes the severity and magnitude of bound changes.
"""

from typing import Dict, Tuple
from data.minimality_result import RelationChange


class BoundAnalyzer:
    """Analyzes quantitative properties of bound changes."""
    
    def analyze_tightening_severity(
        self,
        change: RelationChange,
        variable_bounds: Dict[str, Tuple[float, float]]
    ) -> float:
        """Compute tightening severity relative to ODD bounds.
        
        Returns severity score in [0, 1]:
        - 0.0: No tightening or loosening
        - 0.5: Moderate tightening
        - 1.0: Extreme tightening (close to ODD limit)
        
        Example:
            Original: ego_speed < 30
            Refined:  ego_speed < 1
            ODD:      ego_speed ∈ [0, 50]
            
            Available range in original: 30 - 0 = 30
            Available range in refined: 1 - 0 = 1
            Severity = (30 - 1) / 30 = 0.97 (97% of range eliminated!)
        
        Args:
            change: RelationChange to analyze
            variable_bounds: ODD bounds for variables
            
        Returns:
            Severity score (0.0 to 1.0)
        """
        if change.change_type != "tightening":
            return 0.0
        
        var = change.variable
        if var not in variable_bounds:
            # Fallback: use simple percentage if ODD bounds unknown
            return min(change.magnitude, 1.0)
        
        lo, hi = variable_bounds[var]
        
        if change.operator in ["<", "<="]:
            # Tightening upper bound
            # Original allows range [lo, original_const]
            # Refined allows range [lo, refined_const]
            original_range = change.original_constant - lo
            refined_range = change.refined_constant - lo
            
            if original_range <= 0:
                return 0.0  # Invalid range
            
            # Fraction of range eliminated
            range_eliminated = original_range - refined_range
            severity = range_eliminated / original_range
            
            return max(0.0, min(severity, 1.0))
        
        elif change.operator in [">", ">="]:
            # Tightening lower bound
            # Original allows range [original_const, hi]
            # Refined allows range [refined_const, hi]
            original_range = hi - change.original_constant
            refined_range = hi - change.refined_constant
            
            if original_range <= 0:
                return 0.0  # Invalid range
            
            # Fraction of range eliminated
            range_eliminated = original_range - refined_range
            severity = range_eliminated / original_range
            
            return max(0.0, min(severity, 1.0))
        
        return 0.0
    
    def get_tightening_percentage(self, change: RelationChange) -> float:
        """Compute simple percentage change.
        
        Args:
            change: RelationChange to analyze
            
        Returns:
            Percentage change (e.g., 18.0 for 18% change)
        """
        if change.original_constant == 0:
            return 0.0
        
        return abs(change.delta) / abs(change.original_constant) * 100
    
    def categorize_severity(self, severity: float) -> str:
        """Categorize severity into human-readable levels.
        
        Args:
            severity: Severity score (0.0 to 1.0)
            
        Returns:
            "minor" | "moderate" | "severe" | "extreme"
        """
        if severity < 0.1:
            return "minor"
        elif severity < 0.3:
            return "moderate"
        elif severity < 0.7:
            return "severe"
        else:
            return "extreme"
