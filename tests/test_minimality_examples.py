"""
Regression tests for minimality examples.

Ensures examples continue to work as expected.
"""

import pytest
from core.config import DEFAULT_ADS_CONFIG
from parsers.lark_parser import OperationalRuleParser
from data.counterfactual_evidence import CounterfactualPair, CounterfactualEvidence
from minimality.minimality_validator import MinimalityValidator


@pytest.fixture
def parser():
    """Fixture providing parser."""
    return OperationalRuleParser(DEFAULT_ADS_CONFIG)


@pytest.fixture
def validator():
    """Fixture providing validator."""
    return MinimalityValidator(DEFAULT_ADS_CONFIG.variable_bounds)


class TestExamples:
    """Test all examples from minimality_examples.py."""
    
    def test_example_justified_tightening(self, parser, validator):
        """Test Example 1: Justified tightening."""
        # Original rule
        original_str = "(dist_front < 5) AND (ego_speed > 0)"
        original_rule, errors = parser.parse_safe(original_str)
        assert not errors
        
        # Refined rule
        refined_str = "(dist_front < 4.1) AND (ego_speed > 0)"
        refined_rule, errors = parser.parse_safe(refined_str)
        assert not errors
        
        # Evidence
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
            ]
        )
        
        # Validate
        result = validator.validate(original_rule, refined_rule, evidence)
        
        # Should pass
        assert result.passed_minimality
        assert result.justified_changes > 0
    
    def test_example_unjustified_tightening(self, parser, validator):
        """Test Example 2: Unjustified tightening."""
        # Original rule
        original_str = "(ego_speed < 30) AND (dist_front > 2)"
        original_rule, errors = parser.parse_safe(original_str)
        assert not errors
        
        # Refined rule (excessive)
        refined_str = "(ego_speed < 1) AND (dist_front > 2)"
        refined_rule, errors = parser.parse_safe(refined_str)
        assert not errors
        
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
        
        # Validate
        result = validator.validate(original_rule, refined_rule, evidence)
        
        # Should fail
        assert not result.passed_minimality
        assert len(result.unjustified_tightenings) > 0
    
    def test_example_no_evidence(self, parser, validator):
        """Test Example 3: No evidence provided."""
        # Rules
        original_str = "(dist_front < 10) AND (lane_offset < 2)"
        refined_str = "(dist_front < 8) AND (lane_offset < 1.5)"
        
        original_rule, _ = parser.parse_safe(original_str)
        refined_rule, _ = parser.parse_safe(refined_str)
        
        # No evidence
        result = validator.validate(original_rule, refined_rule, counterfactual_evidence=None)
        
        # Should detect changes
        assert result.total_changes > 0
        # Without evidence, changes are unjustified
        assert result.justified_changes == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
