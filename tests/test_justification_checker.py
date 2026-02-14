"""
Unit tests for JustificationChecker.

Tests evidence-based justification checking.
"""

import pytest
from data.minimality_result import RelationChange
from data.counterfactual_evidence import CounterfactualPair, CounterfactualEvidence
from minimality.justification_checker import JustificationChecker


@pytest.fixture
def checker():
    """Fixture providing JustificationChecker instance."""
    return JustificationChecker()


class TestJustificationChecking:
    """Test justification checking with evidence."""
    
    def test_justified_by_clustering(self, checker):
        """Test justification when counterfactuals cluster near new bound."""
        change = RelationChange(
            variable="dist_front",
            operator="<",
            original_constant=10.0,
            refined_constant=5.0,
            delta=-5.0,
            change_type="tightening",
            magnitude=0.5,
            is_justified=False,
            justification=""
        )
        
        # Counterfactuals cluster near 5.0
        evidence = CounterfactualEvidence(
            inconsistent_rule="(dist_front < 10)",
            pairs=[
                CounterfactualPair(
                    original_input={"dist_front": 8.0, "ego_speed": 20.0, "lane_offset": 0.0, "rel_speed": 0.0},
                    original_outcome="Fail",
                    counterfactual_input={"dist_front": 4.8, "ego_speed": 20.0, "lane_offset": 0.0, "rel_speed": 0.0},
                    counterfactual_outcome="Pass",
                    perturbation={"dist_front": -3.2, "ego_speed": 0.0, "lane_offset": 0.0, "rel_speed": 0.0}
                ),
                CounterfactualPair(
                    original_input={"dist_front": 7.0, "ego_speed": 25.0, "lane_offset": 0.1, "rel_speed": -2.0},
                    original_outcome="Fail",
                    counterfactual_input={"dist_front": 5.1, "ego_speed": 25.0, "lane_offset": 0.1, "rel_speed": -2.0},
                    counterfactual_outcome="Pass",
                    perturbation={"dist_front": -1.9, "ego_speed": 0.0, "lane_offset": 0.0, "rel_speed": 0.0}
                ),
            ]
        )
        
        is_justified, explanation = checker.check_justification(change, evidence)
        
        assert is_justified
        assert "cluster" in explanation.lower()
    
    def test_unjustified_no_evidence(self, checker):
        """Test unjustified when no evidence provided."""
        change = RelationChange(
            variable="dist_front",
            operator="<",
            original_constant=10.0,
            refined_constant=5.0,
            delta=-5.0,
            change_type="tightening",
            magnitude=0.5,
            is_justified=False,
            justification=""
        )
        
        evidence = CounterfactualEvidence(
            inconsistent_rule="(dist_front < 10)",
            pairs=[]
        )
        
        is_justified, explanation = checker.check_justification(change, evidence)
        
        assert not is_justified
        assert "no counterfactual evidence" in explanation.lower()
    
    def test_unjustified_wrong_variable(self, checker):
        """Test unjustified when evidence doesn't involve the variable."""
        change = RelationChange(
            variable="dist_front",
            operator="<",
            original_constant=10.0,
            refined_constant=5.0,
            delta=-5.0,
            change_type="tightening",
            magnitude=0.5,
            is_justified=False,
            justification=""
        )
        
        # Evidence involves ego_speed, not dist_front
        evidence = CounterfactualEvidence(
            inconsistent_rule="(ego_speed > 10)",
            pairs=[
                CounterfactualPair(
                    original_input={"dist_front": 8.0, "ego_speed": 20.0, "lane_offset": 0.0, "rel_speed": 0.0},
                    original_outcome="Fail",
                    counterfactual_input={"dist_front": 8.0, "ego_speed": 15.0, "lane_offset": 0.0, "rel_speed": 0.0},
                    counterfactual_outcome="Pass",
                    perturbation={"dist_front": 0.0, "ego_speed": -5.0, "lane_offset": 0.0, "rel_speed": 0.0}
                ),
            ]
        )
        
        is_justified, explanation = checker.check_justification(change, evidence)
        
        assert not is_justified
        assert "no counterfactuals involve" in explanation.lower()
    
    def test_unjustified_far_from_bound(self, checker):
        """Test unjustified when counterfactuals are far from new bound."""
        change = RelationChange(
            variable="dist_front",
            operator="<",
            original_constant=30.0,
            refined_constant=1.0,
            delta=-29.0,
            change_type="tightening",
            magnitude=0.97,
            is_justified=False,
            justification=""
        )
        
        # Counterfactuals near 25, not near 1
        evidence = CounterfactualEvidence(
            inconsistent_rule="(dist_front < 30)",
            pairs=[
                CounterfactualPair(
                    original_input={"dist_front": 28.0, "ego_speed": 20.0, "lane_offset": 0.0, "rel_speed": 0.0},
                    original_outcome="Fail",
                    counterfactual_input={"dist_front": 24.0, "ego_speed": 20.0, "lane_offset": 0.0, "rel_speed": 0.0},
                    counterfactual_outcome="Pass",
                    perturbation={"dist_front": -4.0, "ego_speed": 0.0, "lane_offset": 0.0, "rel_speed": 0.0}
                ),
            ]
        )
        
        is_justified, explanation = checker.check_justification(change, evidence)
        
        assert not is_justified
        assert "not aligned" in explanation.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
