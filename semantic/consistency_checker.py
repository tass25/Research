"""
Consistency checker for semantic validation.

Checks if rule verdicts match observed simulation outcomes.
"""

from typing import List, Tuple
from core.schema import Rule
from data.simulation_trace import SimulationDataset
from data.semantic_result import ConsistencyIssue


class ConsistencyChecker:
    """Checks if rule verdicts match observed outcomes.
    
    From paper Table 1:
    - Rule in R_Pass, verdict=Pass, outcome=Pass → Consistent
    - Rule in R_Pass, verdict=Pass, outcome=Fail → Inconsistent
    - Rule in R_Fail, verdict=Fail, outcome=Fail → Consistent
    - Rule in R_Fail, verdict=Fail, outcome=Pass → Inconsistent
    """
    
    def __init__(self, rule_set_type: str):
        """
        Args:
            rule_set_type: "Pass" or "Fail" (which R set this rule belongs to)
        """
        if rule_set_type not in ["Pass", "Fail"]:
            raise ValueError(f"rule_set_type must be 'Pass' or 'Fail', got '{rule_set_type}'")
        self.rule_set_type = rule_set_type
    
    def check_consistency(
        self, 
        rule: Rule,
        dataset: SimulationDataset
    ) -> Tuple[float, List[ConsistencyIssue]]:
        """Check rule against simulation data.
        
        Returns:
            (consistency_score, list_of_issues)
        """
        matches = 0
        total_applicable = 0
        issues = []
        
        for trace in dataset.traces:
            try:
                # Evaluate rule on input
                rule_holds = rule.evaluate(trace.input_vector)
            except KeyError as e:
                # Variable not in input vector - skip this trace
                continue
            except Exception as e:
                # Other evaluation error
                print(f"Warning: Failed to evaluate rule on {trace.input_vector}: {e}")
                continue
            
            # Determine rule verdict based on rule set type
            if self.rule_set_type == "Pass":
                rule_verdict = "Pass" if rule_holds else "Inconclusive"
            else:  # Fail
                rule_verdict = "Fail" if rule_holds else "Inconclusive"
            
            # Skip if rule doesn't apply
            if rule_verdict == "Inconclusive":
                continue
            
            total_applicable += 1
            
            # Check consistency
            if rule_verdict == trace.observed_outcome:
                matches += 1
            else:
                issues.append(ConsistencyIssue(
                    trace=trace,
                    rule_verdict=rule_verdict,
                    observed_outcome=trace.observed_outcome
                ))
        
        # Compute score
        if total_applicable == 0:
            return 0.0, issues  # Rule doesn't apply to any traces
        
        score = matches / total_applicable
        return score, issues
