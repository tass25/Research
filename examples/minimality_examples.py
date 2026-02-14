"""
Examples demonstrating minimality analysis (Priority 3).

Shows how to detect overly conservative refinements.
"""

from core.config import DEFAULT_ADS_CONFIG
from parsers.lark_parser import OperationalRuleParser
from data.counterfactual_evidence import CounterfactualPair, CounterfactualEvidence
from minimality.minimality_validator import MinimalityValidator


def example_justified_tightening():
    """Example: Tightening justified by counterfactual evidence."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Justified Tightening")
    print("=" * 70)
    
    parser = OperationalRuleParser(DEFAULT_ADS_CONFIG)
    
    # Original rule
    original_str = "(dist_front < 5) AND (ego_speed > 0)"
    original_rule, _ = parser.parse_safe(original_str)
    
    # Refined rule (tightened dist_front)
    refined_str = "(dist_front < 4.1) AND (ego_speed > 0)"
    refined_rule, _ = parser.parse_safe(refined_str)
    
    # Counterfactual evidence showing boundary near 4.0
    evidence = CounterfactualEvidence(
        inconsistent_rule=original_str,
        pairs=[
            CounterfactualPair(
                original_input={"ego_speed": 25.0, "dist_front": 4.8, "lane_offset": 0.0, "rel_speed": 0.0},
                original_outcome="Fail",
                counterfactual_input={"ego_speed": 25.0, "dist_front": 4.0, "lane_offset": 0.0, "rel_speed": 0.0},
                counterfactual_outcome="Pass",
                perturbation={"ego_speed": 0.0, "dist_front": -0.8, "lane_offset": 0.0, "rel_speed": 0.0}
            ),
            CounterfactualPair(
                original_input={"ego_speed": 30.0, "dist_front": 4.5, "lane_offset": 0.1, "rel_speed": -2.0},
                original_outcome="Fail",
                counterfactual_input={"ego_speed": 30.0, "dist_front": 3.9, "lane_offset": 0.1, "rel_speed": -2.0},
                counterfactual_outcome="Pass",
                perturbation={"ego_speed": 0.0, "dist_front": -0.6, "lane_offset": 0.0, "rel_speed": 0.0}
            ),
        ]
    )
    
    # Validate minimality
    validator = MinimalityValidator(DEFAULT_ADS_CONFIG.variable_bounds)
    result = validator.validate(original_rule, refined_rule, evidence)
    
    print(result.summary())


def example_unjustified_tightening():
    """Example: Excessive tightening not supported by evidence."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Unjustified Tightening")
    print("=" * 70)
    
    parser = OperationalRuleParser(DEFAULT_ADS_CONFIG)
    
    # Original rule
    original_str = "(ego_speed < 30) AND (dist_front > 2)"
    original_rule, _ = parser.parse_safe(original_str)
    
    # Refined rule (excessively tightened ego_speed)
    refined_str = "(ego_speed < 1) AND (dist_front > 2)"
    refined_rule, _ = parser.parse_safe(refined_str)
    
    # Evidence shows boundary near 25, not 1
    evidence = CounterfactualEvidence(
        inconsistent_rule=original_str,
        pairs=[
            CounterfactualPair(
                original_input={"ego_speed": 28.0, "dist_front": 3.0, "lane_offset": 0.0, "rel_speed": 0.0},
                original_outcome="Fail",
                counterfactual_input={"ego_speed": 24.0, "dist_front": 3.0, "lane_offset": 0.0, "rel_speed": 0.0},
                counterfactual_outcome="Pass",
                perturbation={"ego_speed": -4.0, "dist_front": 0.0, "lane_offset": 0.0, "rel_speed": 0.0}
            ),
        ]
    )
    
    # Validate minimality
    validator = MinimalityValidator(DEFAULT_ADS_CONFIG.variable_bounds)
    result = validator.validate(original_rule, refined_rule, evidence)
    
    print(result.summary())


def example_no_evidence():
    """Example: Analysis without counterfactual evidence."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: No Counterfactual Evidence")
    print("=" * 70)
    
    parser = OperationalRuleParser(DEFAULT_ADS_CONFIG)
    
    # Original and refined rules
    original_str = "(dist_front < 10) AND (lane_offset < 2)"
    refined_str = "(dist_front < 8) AND (lane_offset < 1.5)"
    
    original_rule, _ = parser.parse_safe(original_str)
    refined_rule, _ = parser.parse_safe(refined_str)
    
    # No evidence provided
    validator = MinimalityValidator(DEFAULT_ADS_CONFIG.variable_bounds)
    result = validator.validate(original_rule, refined_rule, counterfactual_evidence=None)
    
    print(result.summary())


def main():
    """Run all minimality examples."""
    print("\n")
    print("=" * 70)
    print("MINIMALITY ANALYSIS EXAMPLES (Priority 3)")
    print("=" * 70)
    
    example_justified_tightening()
    example_unjustified_tightening()
    example_no_evidence()
    
    print("\n" + "=" * 70)
    print("All examples complete!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
