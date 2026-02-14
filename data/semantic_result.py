from dataclasses import dataclass
from typing import List, Set, Dict
from data.simulation_trace import SimulationTrace

@dataclass
class ConsistencyIssue:
    """Single consistency mismatch."""
    trace: SimulationTrace
    rule_verdict: str        # What rule predicted
    observed_outcome: str    # What actually happened
    
@dataclass
class ContradictionIssue:
    """Contradiction with historical rule."""
    current_rule: str
    historical_rule: str
    conflicting_input: Dict[str, float]  # Input where they disagree
    explanation: str

@dataclass
class OverfittingIndicator:
    """Evidence of overfitting."""
    indicator_type: str      # "boundary_sensitive", "overly_specific", etc.
    severity: float          # 0.0 to 1.0
    evidence: str            # Human-readable explanation
    affected_variables: Set[str]

@dataclass
class SemanticValidationResult:
    """Complete semantic validation result."""
    rule: str
    is_consistent: bool
    consistency_score: float              # % of traces matched
    consistency_issues: List[ConsistencyIssue]
    
    has_contradictions: bool
    contradictions: List[ContradictionIssue]
    
    overfitting_risk: float               # 0.0 to 1.0
    overfitting_indicators: List[OverfittingIndicator]
    
    passed_validation: bool               # Overall pass/fail
    
    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"Semantic Validation Result for: {self.rule}",
            f"Passed: {self.passed_validation}",
            f"Consistency Score: {self.consistency_score:.2%} ({len(self.consistency_issues)} issues)",
            f"Contradictions: {len(self.contradictions)}",
            f"Overfitting Risk: {self.overfitting_risk:.2%}"
        ]
        return "\n".join(lines)
