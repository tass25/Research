"""
Integration tests for MinimalityValidator.

Tests complete minimality validation pipeline.
"""

import pytest
from core.config import DEFAULT_ADS_CONFIG
from parsers.lark_parser import OperationalRuleParser
from data.counterfactual_evidence import CounterfactualPair, CounterfactualEvidence
from minimality.minimality_validator import MinimalityValidator


@pytest.fixture
def parser():
    """Fixture providing parser instance."""
    return OperationalRuleParser(DEFAULT_ADS_CONFIG)


@pytest.fixture
def validator():
    """Fixture providing MinimalityValidator instance."""
    return MinimalityValidator(DEFAULT_ADS_CONFIG.variable_bounds)


class TestEndToEndValidation:
    """Test complete validation pipeline."""
    
    def test_justified_refinement_passes(self, parser, validator):
        """Test that justified refinement passes validation."""
        # Original rule
        original, _ = parser.parse_safe("(dist_front < 10)")
        
        # Refined rule (moderate tightening)
        refined, _ = parser.parse_safe("(dist_front < 8)")
        
        # Evidence supporting the change
        evidence = CounterfactualEvidence(
            inconsistent_rule="(dist_front < 10)",
            pairs=[
                CounterfactualPair(
                    original_input={"dist_front": 9.0, "ego_speed": 20.0, "lane_offset": 0.0, "rel_speed": 0.0},
                    original_outcome="Fail",
                    counterfactual_input={"dist_front": 7.8, "ego_speed": 20.0, "lane_offset": 0.0, "rel_speed": 0.0},
                    counterfactual_outcome="Pass",
                    perturbation={"dist_front": -1.2, "ego_speed": 0.0, "lane_offset": 0.0, "rel_speed": 0.0}
                ),
            ]
        )
        
        result = validator.validate(original, refined, evidence)
        
        assert result.total_changes == 1
        assert result.justified_changes == 1
        assert result.overall_score > 0.7
        assert result.passed_minimality
    
    def test_unjustified_refinement_fails(self, parser, validator):
        """Test that unjustified excessive tightening fails."""
        # Original rule
        original, _ = parser.parse_safe("(ego_speed < 30)")
        
        # Refined rule (excessive tightening)
        refined, _ = parser.parse_safe("(ego_speed < 1)")
        
        # Evidence shows boundary near 25, not 1
        evidence = CounterfactualEvidence(
            inconsistent_rule="(ego_speed < 30)",
            pairs=[
                CounterfactualPair(
                    original_input={"dist_front": 10.0, "ego_speed": 28.0, "lane_offset": 0.0, "rel_speed": 0.0},
                    original_outcome="Fail",
                    counterfactual_input={"dist_front": 10.0, "ego_speed": 24.0, "lane_offset": 0.0, "rel_speed": 0.0},
                    counterfactual_outcome="Pass",
                    perturbation={"dist_front": 0.0, "ego_speed": -4.0, "lane_offset": 0.0, "rel_speed": 0.0}
                ),
            ]
        )
        
        result = validator.validate(original, refined, evidence)
        
        assert result.total_changes == 1
        assert result.justified_changes == 0
        assert len(result.unjustified_tightenings) == 1
        assert result.overall_score < 0.7
        assert not result.passed_minimality
    
    def test_no_changes_passes(self, parser, validator):
        """Test that identical rules pass with perfect score."""
        original, _ = parser.parse_safe("(dist_front < 10)")
        refined, _ = parser.parse_safe("(dist_front < 10)")
        
        result = validator.validate(original, refined)
        
        assert result.total_changes == 0
        assert result.overall_score == 1.0
        assert result.passed_minimality
    
    def test_multiple_changes_mixed_justification(self, parser, validator):
        """Test multiple changes with mixed justification."""
        original, _ = parser.parse_safe("(dist_front < 10) AND (ego_speed > 5)")
        refined, _ = parser.parse_safe("(dist_front < 8) AND (ego_speed > 20)")
        
        # Evidence justifies dist_front but not ego_speed
        evidence = CounterfactualEvidence(
            inconsistent_rule="(dist_front < 10) AND (ego_speed > 5)",
            pairs=[
                CounterfactualPair(
                    original_input={"dist_front": 9.0, "ego_speed": 10.0, "lane_offset": 0.0, "rel_speed": 0.0},
                    original_outcome="Fail",
                    counterfactual_input={"dist_front": 7.8, "ego_speed": 10.0, "lane_offset": 0.0, "rel_speed": 0.0},
                    counterfactual_outcome="Pass",
                    perturbation={"dist_front": -1.2, "ego_speed": 0.0, "lane_offset": 0.0, "rel_speed": 0.0}
                ),
            ]
        )
        
        result = validator.validate(original, refined, evidence)
        
        assert result.total_changes == 2
        assert result.justified_changes == 1
        assert len(result.unjustified_tightenings) == 1


class TestValidationWithoutEvidence:
    """Test validation when no evidence provided."""
    
    def test_no_evidence_all_unjustified(self, parser, validator):
        """Test that without evidence, all changes are unjustified."""
        original, _ = parser.parse_safe("(dist_front < 10)")
        refined, _ = parser.parse_safe("(dist_front < 8)")
        
        result = validator.validate(original, refined, counterfactual_evidence=None)
        
        assert result.total_changes == 1
        assert result.justified_changes == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
