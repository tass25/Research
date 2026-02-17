"""
Minimality analysis result structures.

Defines data classes for representing changes between original and refined rules.
"""

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class RelationChange:
    """Change in a single relation between original and refined rule.
    
    Example:
        Original: dist_front < 5
        Refined:  dist_front < 4.1
        Change:   -0.9 (tightening)
    
    Attributes:
        variable: Variable name (example, "dist_front")
        operator: Relational operator (example, "<")
        original_constant: Constant in original rule (example, 5.0)
        refined_constant: Constant in refined rule (example, 4.1)
        delta: Change amount (refined - original, example, -0.9)
        change_type: "tightening" | "loosening" | "unchanged"
        magnitude: Relative change magnitude (0.0 to 1.0+)
        is_justified: Whether change is supported by evidence
        justification: Explanation of justification status
    """
    variable: str
    operator: str
    original_constant: float
    refined_constant: float
    delta: float
    change_type: str
    magnitude: float
    is_justified: bool
    justification: str
    
    def __str__(self) -> str:
        """Human-readable representation."""
        direction = "↓" if self.change_type == "tightening" else "↑" if self.change_type == "loosening" else "="
        justified_mark = "✓" if self.is_justified else "✗"
        return (
            f"{self.variable} {self.operator} {self.original_constant} → {self.refined_constant} "
            f"({direction} {abs(self.delta):.2f}, {self.magnitude*100:.1f}%) [{justified_mark}]"
        )


@dataclass(frozen=True)
class MinimalityResult:
    """Complete result of minimality analysis.
    
    Attributes:
        original_rule: String representation of original rule
        refined_rule: String representation of refined rule
        overall_score: Minimality score (0.0 = bad, 1.0 = good/minimal)
        relation_changes: List of all detected changes
        unjustified_tightenings: Changes that tighten without justification
        unjustified_loosenings: Changes that loosen without justification
        total_changes: Total number of changes detected
        justified_changes: Number of changes with justification
        passed_minimality: Whether overall score passes threshold
    """
    original_rule: str
    refined_rule: str
    overall_score: float
    relation_changes: List[RelationChange]
    unjustified_tightenings: List[RelationChange]
    unjustified_loosenings: List[RelationChange]
    total_changes: int
    justified_changes: int
    passed_minimality: bool
    
    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "=" * 70,
            "MINIMALITY ANALYSIS RESULT",
            "=" * 70,
            f"Original: {self.original_rule}",
            f"Refined:  {self.refined_rule}",
            "",
            f"Overall Score: {self.overall_score:.2%}",
            f"Status: {'PASS ✓' if self.passed_minimality else 'FAIL ✗'}",
            "",
            f"Changes Detected: {self.total_changes}",
            f"  - Justified: {self.justified_changes}",
            f"  - Unjustified Tightenings: {len(self.unjustified_tightenings)}",
            f"  - Unjustified Loosenings: {len(self.unjustified_loosenings)}",
            "",
        ]
        
        if self.relation_changes:
            lines.append("Detailed Changes:")
            for i, change in enumerate(self.relation_changes, 1):
                lines.append(f"  {i}. {change}")
                if change.justification:
                    lines.append(f"     → {change.justification}")
        
        if self.unjustified_tightenings:
            lines.append("")
            lines.append("⚠️  UNJUSTIFIED TIGHTENINGS:")
            for change in self.unjustified_tightenings:
                lines.append(f"  - {change.variable} {change.operator}: {change.original_constant} → {change.refined_constant}")
                lines.append(f"    Reason: {change.justification}")
        
        lines.append("=" * 70)
        return "\n".join(lines)
