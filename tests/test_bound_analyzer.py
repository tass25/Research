"""
Unit tests for BoundAnalyzer.

Tests severity computation and percentage calculations.
"""

import pytest
from data.minimality_result import RelationChange
from minimality.bound_analyzer import BoundAnalyzer


@pytest.fixture
def analyzer():
    """Fixture providing BoundAnalyzer instance."""
    return BoundAnalyzer()


@pytest.fixture
def variable_bounds():
    """Fixture providing sample ODD bounds."""
    return {
        "ego_speed": (0.0, 50.0),
        "dist_front": (0.0, 200.0),
        "lane_offset": (-5.0, 5.0),
    }


class TestTighteningSeverity:
    """Test tightening severity computation."""
    
    def test_moderate_tightening_upper_bound(self, analyzer, variable_bounds):
        """Test moderate tightening of upper bound."""
        # Original: dist_front < 100
        # Refined: dist_front < 50
        # ODD: [0, 200]
        # Original range: 100 - 0 = 100
        # Refined range: 50 - 0 = 50
        # Severity: (100 - 50) / 100 = 0.5
        
        change = RelationChange(
            variable="dist_front",
            operator="<",
            original_constant=100.0,
            refined_constant=50.0,
            delta=-50.0,
            change_type="tightening",
            magnitude=0.5,
            is_justified=False,
            justification=""
        )
        
        severity = analyzer.analyze_tightening_severity(change, variable_bounds)
        assert abs(severity - 0.5) < 1e-6
    
    def test_extreme_tightening_upper_bound(self, analyzer, variable_bounds):
        """Test extreme tightening of upper bound."""
        # Original: dist_front < 100
        # Refined: dist_front < 1
        # Severity: (100 - 1) / 100 = 0.99
        
        change = RelationChange(
            variable="dist_front",
            operator="<",
            original_constant=100.0,
            refined_constant=1.0,
            delta=-99.0,
            change_type="tightening",
            magnitude=0.99,
            is_justified=False,
            justification=""
        )
        
        severity = analyzer.analyze_tightening_severity(change, variable_bounds)
        assert severity > 0.9
    
    def test_tightening_lower_bound(self, analyzer, variable_bounds):
        """Test tightening of lower bound."""
        # Original: ego_speed > 10
        # Refined: ego_speed > 25
        # ODD: [0, 50]
        # Original range: 50 - 10 = 40
        # Refined range: 50 - 25 = 25
        # Severity: (40 - 25) / 40 = 0.375
        
        change = RelationChange(
            variable="ego_speed",
            operator=">",
            original_constant=10.0,
            refined_constant=25.0,
            delta=15.0,
            change_type="tightening",
            magnitude=1.5,
            is_justified=False,
            justification=""
        )
        
        severity = analyzer.analyze_tightening_severity(change, variable_bounds)
        assert abs(severity - 0.375) < 1e-6
    
    def test_loosening_returns_zero(self, analyzer, variable_bounds):
        """Test that loosening returns severity 0."""
        change = RelationChange(
            variable="dist_front",
            operator="<",
            original_constant=50.0,
            refined_constant=100.0,
            delta=50.0,
            change_type="loosening",
            magnitude=1.0,
            is_justified=False,
            justification=""
        )
        
        severity = analyzer.analyze_tightening_severity(change, variable_bounds)
        assert severity == 0.0
    
    def test_unknown_variable_fallback(self, analyzer):
        """Test fallback when variable not in bounds."""
        change = RelationChange(
            variable="unknown_var",
            operator="<",
            original_constant=100.0,
            refined_constant=50.0,
            delta=-50.0,
            change_type="tightening",
            magnitude=0.5,
            is_justified=False,
            justification=""
        )
        
        # Should fallback to simple magnitude
        severity = analyzer.analyze_tightening_severity(change, {})
        assert severity == 0.5


class TestPercentageCalculation:
    """Test percentage change calculation."""
    
    def test_percentage_change(self, analyzer):
        """Test basic percentage calculation."""
        change = RelationChange(
            variable="dist_front",
            operator="<",
            original_constant=100.0,
            refined_constant=80.0,
            delta=-20.0,
            change_type="tightening",
            magnitude=0.2,
            is_justified=False,
            justification=""
        )
        
        pct = analyzer.get_tightening_percentage(change)
        assert pct == 20.0
    
    def test_zero_original_constant(self, analyzer):
        """Test handling of zero original constant."""
        change = RelationChange(
            variable="dist_front",
            operator=">",
            original_constant=0.0,
            refined_constant=5.0,
            delta=5.0,
            change_type="tightening",
            magnitude=0.0,
            is_justified=False,
            justification=""
        )
        
        pct = analyzer.get_tightening_percentage(change)
        assert pct == 0.0


class TestSeverityCategorization:
    """Test severity categorization."""
    
    def test_categorize_minor(self, analyzer):
        """Test minor severity."""
        assert analyzer.categorize_severity(0.05) == "minor"
    
    def test_categorize_moderate(self, analyzer):
        """Test moderate severity."""
        assert analyzer.categorize_severity(0.2) == "moderate"
    
    def test_categorize_severe(self, analyzer):
        """Test severe severity."""
        assert analyzer.categorize_severity(0.5) == "severe"
    
    def test_categorize_extreme(self, analyzer):
        """Test extreme severity."""
        assert analyzer.categorize_severity(0.9) == "extreme"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
