"""
Unit tests for ChangeExtractor.

Tests relation extraction, matching, and change classification.
"""

import pytest
from core.config import DEFAULT_ADS_CONFIG
from parsers.lark_parser import OperationalRuleParser
from minimality.change_extractor import ChangeExtractor


@pytest.fixture
def parser():
    """Fixture providing parser instance."""
    return OperationalRuleParser(DEFAULT_ADS_CONFIG)


@pytest.fixture
def extractor():
    """Fixture providing ChangeExtractor instance."""
    return ChangeExtractor()


class TestRelationExtraction:
    """Test relation extraction from rules."""
    
    def test_extract_single_relation(self, parser, extractor):
        """Test extracting from single-relation rule."""
        rule, _ = parser.parse_safe("(dist_front < 5)")
        relations = extractor._extract_relations(rule)
        
        assert len(relations) == 1
        assert relations[0].left.name == "dist_front"
        assert relations[0].op.value == "<"
        assert relations[0].right.value == 5.0
    
    def test_extract_conjunction(self, parser, extractor):
        """Test extracting from conjunction."""
        rule, _ = parser.parse_safe("(dist_front < 5) AND (ego_speed > 10)")
        relations = extractor._extract_relations(rule)
        
        assert len(relations) == 2
        variables = {r.left.name for r in relations}
        assert variables == {"dist_front", "ego_speed"}
    
    def test_extract_disjunction(self, parser, extractor):
        """Test extracting from disjunction."""
        rule, _ = parser.parse_safe("(dist_front < 5) OR (ego_speed > 10)")
        relations = extractor._extract_relations(rule)
        
        assert len(relations) == 2
    
    def test_extract_nested(self, parser, extractor):
        """Test extracting from nested structure."""
        rule, _ = parser.parse_safe(
            "((dist_front < 5) AND (ego_speed > 10)) OR (lane_offset < 1)"
        )
        relations = extractor._extract_relations(rule)
        
        assert len(relations) == 3


class TestRelationParsing:
    """Test parsing individual relations."""
    
    def test_parse_variable_lt_constant(self, parser, extractor):
        """Test Variable < Constant pattern."""
        rule, _ = parser.parse_safe("(dist_front < 5)")
        relations = extractor._extract_relations(rule)
        
        var, op, const = extractor._parse_relation(relations[0])
        
        assert var == "dist_front"
        assert op.value == "<"
        assert const == 5.0
    
    def test_parse_variable_gt_constant(self, parser, extractor):
        """Test Variable > Constant pattern."""
        rule, _ = parser.parse_safe("(ego_speed > 10)")
        relations = extractor._extract_relations(rule)
        
        var, op, const = extractor._parse_relation(relations[0])
        
        assert var == "ego_speed"
        assert op.value == ">"
        assert const == 10.0
    
    def test_parse_all_operators(self, parser, extractor):
        """Test all relational operators."""
        operators = ["<", "<=", ">", ">=", "=", "!="]
        
        for op_str in operators:
            rule, _ = parser.parse_safe(f"(dist_front {op_str} 5)")
            relations = extractor._extract_relations(rule)
            
            var, op, const = extractor._parse_relation(relations[0])
            assert op.value == op_str


class TestChangeClassification:
    """Test change type classification."""
    
    def test_tightening_upper_bound(self, extractor):
        """Test tightening of upper bound (< operator)."""
        from core.types import RelOp
        
        # Original: dist_front < 10
        # Refined: dist_front < 5
        # Delta: -5 (negative)
        # Classification: tightening
        
        change_type = extractor._classify_change(RelOp.LT, -5.0)
        assert change_type == "tightening"
    
    def test_loosening_upper_bound(self, extractor):
        """Test loosening of upper bound (< operator)."""
        from core.types import RelOp
        
        # Original: dist_front < 5
        # Refined: dist_front < 10
        # Delta: +5 (positive)
        # Classification: loosening
        
        change_type = extractor._classify_change(RelOp.LT, 5.0)
        assert change_type == "loosening"
    
    def test_tightening_lower_bound(self, extractor):
        """Test tightening of lower bound (> operator)."""
        from core.types import RelOp
        
        # Original: ego_speed > 5
        # Refined: ego_speed > 10
        # Delta: +5 (positive)
        # Classification: tightening (higher minimum)
        
        change_type = extractor._classify_change(RelOp.GT, 5.0)
        assert change_type == "tightening"
    
    def test_loosening_lower_bound(self, extractor):
        """Test loosening of lower bound (> operator)."""
        from core.types import RelOp
        
        # Original: ego_speed > 10
        # Refined: ego_speed > 5
        # Delta: -5 (negative)
        # Classification: loosening (lower minimum)
        
        change_type = extractor._classify_change(RelOp.GT, -5.0)
        assert change_type == "loosening"
    
    def test_unchanged(self, extractor):
        """Test unchanged (exact 0.0 delta)."""
        from core.types import RelOp
        
        change_type = extractor._classify_change(RelOp.LT, 0.0)
        assert change_type == "unchanged"


class TestChangeExtraction:
    """Test full change extraction pipeline."""
    
    def test_extract_single_change(self, parser, extractor):
        """Test extracting single change."""
        original, _ = parser.parse_safe("(dist_front < 10)")
        refined, _ = parser.parse_safe("(dist_front < 5)")
        
        changes = extractor.extract_changes(original, refined)
        
        assert len(changes) == 1
        change = changes[0]
        
        assert change.variable == "dist_front"
        assert change.operator == "<"
        assert change.original_constant == 10.0
        assert change.refined_constant == 5.0
        assert change.delta == -5.0
        assert change.change_type == "tightening"
        assert change.magnitude == 0.5  # 5/10 = 0.5
    
    def test_extract_multiple_changes(self, parser, extractor):
        """Test extracting multiple changes."""
        original, _ = parser.parse_safe("(dist_front < 10) AND (ego_speed > 5)")
        refined, _ = parser.parse_safe("(dist_front < 8) AND (ego_speed > 10)")
        
        changes = extractor.extract_changes(original, refined)
        
        assert len(changes) == 2
        
        # Check both changes detected
        variables = {c.variable for c in changes}
        assert variables == {"dist_front", "ego_speed"}
    
    def test_no_changes(self, parser, extractor):
        """Test when rules are identical."""
        original, _ = parser.parse_safe("(dist_front < 5)")
        refined, _ = parser.parse_safe("(dist_front < 5)")
        
        changes = extractor.extract_changes(original, refined)
        
        # Either empty list or single "unchanged" change
        if changes:
            assert all(c.change_type == "unchanged" for c in changes)
    
    def test_unmatched_relations(self, parser, extractor):
        """Test when refined rule has different variables."""
        original, _ = parser.parse_safe("(dist_front < 10)")
        refined, _ = parser.parse_safe("(ego_speed > 5)")
        
        changes = extractor.extract_changes(original, refined)
        
        # No matching relations (different variables)
        assert len(changes) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
