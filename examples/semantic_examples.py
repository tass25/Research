"""
Examples demonstrating semantic validation (Part 2).
"""

from core.config import DEFAULT_ADS_CONFIG
from parsers.lark_parser import OperationalRuleParser
from data.simulation_trace import SimulationTrace, SimulationDataset
from data.semantic_result import ConsistencyIssue  # Correct import
from semantic.semantic_validator import SemanticValidator

def create_sample_dataset():
    """Create sample simulation dataset for testing."""
    traces = [
        SimulationTrace(
            input_vector={"ego_speed": 25.0, "dist_front": 10.0, "lane_offset": 0.0, "rel_speed": 0.0},
            observed_outcome="Pass"
        ),
        SimulationTrace(
            input_vector={"ego_speed": 45.0, "dist_front": 3.0, "lane_offset": 0.5, "rel_speed": -5.0},
            observed_outcome="Fail"
        ),
        # ... more traces
    ]
    return SimulationDataset(traces)


def main():
    """Demonstrate semantic validation."""
    
    # Parse a rule
    parser = OperationalRuleParser(DEFAULT_ADS_CONFIG)
    # Using AND keyword for robustness against unicode issues in some environments
    rule_str = "(dist_front < 5) AND (ego_speed > 0)"
    print(f"Parsing rule: {rule_str}")
    
    rule, errors = parser.parse_safe(rule_str)
    
    if not rule:
        print(f"Failed to parse rule. Errors: {errors}")
        return

    print(f"Validating Rule: {rule}")

    # Create dataset
    dataset = create_sample_dataset()
    
    # Create validator
    validator = SemanticValidator(
        rule_set_type="Pass",
        historical_rules=[],
        variable_bounds=DEFAULT_ADS_CONFIG.variable_bounds
    )
    
    # Validate
    result = validator.validate(
        rule=rule,
        training_data=dataset
    )
    
    # Print results
    print("-" * 50)
    print(result.summary())
    print("-" * 50)


if __name__ == "__main__":
    main()
