"""
Unit tests for MinimalityScorer.

Tests score computation with various change patterns.
"""

import pytest
from data.minimality_result import RelationChange
from minimality.minimality_scorer import MinimalityScorer


@pytest.fixture
def scorer():
    """Fixture providing MinimalityScorer instance."""
    return MinimalityScorer()


class TestScoreComputation:
    """Test minimality score computation."""
    
    def test_no_changes_perfect_score(self, scorer):
        """Test that no changes gives perfect score."""
        changes = []
        score = scorer.compute_score(changes)
        
        assert score == 1.0
    
    def test_all_justified_perfect_score(self, scorer):
        """Test that all justified changes gives perfect score."""
        changes = [
            RelationChange(
                variable="dist_front",
                operator="<",
                original_constant=10.0,
                refined_constant=8.0,
                delta=-2.0,
                change_type="tightening",
                magnitude=0.2,
                is_justified=True,
                justification="Justified"
            ),
            RelationChange(
                variable="ego_speed",
                operator=">",
                original_constant=5.0,
                refined_constant=10.0,
                delta=5.0,
                change_type="tightening",
                magnitude=1.0,
                is_justified=True,
                justification="Justified"
            ),
        ]
        
        score = scorer.compute_score(changes)
        assert score == 1.0
    
    def test_all_unjustified_low_score(self, scorer):
        """Test that all unjustified tightenings gives low score."""
        changes = [
            RelationChange(
                variable="dist_front",
                operator="<",
                original_constant=30.0,
                refined_constant=1.0,
                delta=-29.0,
                change_type="tightening",
                magnitude=0.97,
                is_justified=False,
                justification="Not justified"
            ),
        ]
        
        score = scorer.compute_score(changes)
        
        # Should be very low due to high magnitude unjustified tightening
        assert score < 0.5
    
    def test_mixed_changes_moderate_score(self, scorer):
        """Test that mixed justified/unjustified gives moderate score."""
        changes = [
            RelationChange(
                variable="dist_front",
                operator="<",
                original_constant=10.0,
                refined_constant=8.0,
                delta=-2.0,
                change_type="tightening",
                magnitude=0.2,
                is_justified=True,
                justification="Justified"
            ),
            RelationChange(
                variable="ego_speed",
                operator=">",
                original_constant=10.0,
                refined_constant=15.0,
                delta=5.0,
                change_type="tightening",
                magnitude=0.5,
                is_justified=False,
                justification="Not justified"
            ),
        ]
        
        score = scorer.compute_score(changes)
        
        # 50% justified, moderate magnitude penalty
        assert 0.3 < score < 0.8
    
    def test_loosening_not_penalized(self, scorer):
        """Test that unjustified loosening is not heavily penalized."""
        changes = [
            RelationChange(
                variable="dist_front",
                operator="<",
                original_constant=5.0,
                refined_constant=10.0,
                delta=5.0,
                change_type="loosening",
                magnitude=1.0,
                is_justified=False,
                justification="Not justified"
            ),
        ]
        
        score = scorer.compute_score(changes)
        
        # Loosening gets no magnitude penalty
        # justified_weight = 0/1 = 0
        # magnitude_penalty = 1.0 (no unjustified tightenings)
        # score = (0 + 1.0) / 2 = 0.5
        assert abs(score - 0.5) < 1e-6


class TestWeightedScoring:
    """Test weighted score computation."""
    
    def test_custom_weights(self, scorer):
        """Test custom weighting."""
        changes = [
            RelationChange(
                variable="dist_front",
                operator="<",
                original_constant=10.0,
                refined_constant=8.0,
                delta=-2.0,
                change_type="tightening",
                magnitude=0.2,
                is_justified=True,
                justification="Justified"
            ),
            RelationChange(
                variable="ego_speed",
                operator=">",
                original_constant=10.0,
                refined_constant=15.0,
                delta=5.0,
                change_type="tightening",
                magnitude=0.8,
                is_justified=False,
                justification="Not justified"
            ),
        ]
        
        # Emphasize justification
        score_high_just = scorer.compute_weighted_score(
            changes,
            justification_weight=0.9,
            magnitude_weight=0.1
        )
        
        # Emphasize magnitude
        score_high_mag = scorer.compute_weighted_score(
            changes,
            justification_weight=0.1,
            magnitude_weight=0.9
        )
        
        # High justification weight should give higher score
        # (50% justified is better weighted)
        assert score_high_just > score_high_mag


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
