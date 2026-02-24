import json
from dataclasses import dataclass, asdict
from typing import List, Set, Dict, Any
from data.simulation_trace import SimulationTrace


@dataclass
class ConsistencyIssue:
    """Single consistency mismatch."""
    trace: SimulationTrace
    rule_verdict: str        # What rule predicted
    observed_outcome: str    # What actually happened

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_vector": dict(self.trace.input_vector),
            "observed_outcome": self.trace.observed_outcome,
            "rule_verdict": self.rule_verdict,
            "expected_outcome": self.observed_outcome,
        }

    
@dataclass
class ContradictionIssue:
    """Contradiction with historical rule."""
    current_rule: str
    historical_rule: str
    conflicting_input: Dict[str, float]  # Input where they disagree
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_rule": self.current_rule,
            "historical_rule": self.historical_rule,
            "conflicting_input": dict(self.conflicting_input),
            "explanation": self.explanation,
        }


@dataclass
class OverfittingIndicator:
    """Evidence of overfitting."""
    indicator_type: str      # "boundary_sensitive", "overly_specific", etc.
    severity: float          # 0.0 to 1.0
    evidence: str            # Human-readable explanation
    affected_variables: Set[str]

    def __str__(self):
        return f"[{self.indicator_type}] severity={self.severity:.2f}: {self.evidence}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "indicator_type": self.indicator_type,
            "severity": self.severity,
            "evidence": self.evidence,
            "affected_variables": sorted(self.affected_variables),
        }


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

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict for persistence."""
        return {
            "rule": self.rule,
            "passed_validation": self.passed_validation,
            "is_consistent": self.is_consistent,
            "consistency_score": self.consistency_score,
            "consistency_issues": [i.to_dict() for i in self.consistency_issues],
            "has_contradictions": self.has_contradictions,
            "contradictions": [c.to_dict() for c in self.contradictions],
            "overfitting_risk": self.overfitting_risk,
            "overfitting_indicators": [o.to_dict() for o in self.overfitting_indicators],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
