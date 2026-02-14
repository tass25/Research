"""
Examples from SEAMS 2026 paper.

Demonstrates parsing and evaluation of operational rules.
"""

from core.config import DEFAULT_ADS_CONFIG
from parsers.lark_parser import OperationalRuleParser


def main():
    """Run all paper examples."""
    parser = OperationalRuleParser(DEFAULT_ADS_CONFIG)

    # Test cases: (rule_string, should_parse, description)
    test_cases = [
        # Valid rules
        ("(dist_front < 5) ∧ (ego_speed > 0)", True, "Paper example r1"),
        ("(dist_front < 4.1) ∧ (ego_speed > 0)", True, "Paper example r1★ (refined)"),
        ("(ego_speed > 10) ∨ (dist_front > 20)", True, "Simple disjunction"),
        
        # Unicode normalization (should work after preparse)
        ("(ego_speed ≤ 30)", True, "Unicode ≤ operator"),
        
        # Should fail: unknown variable
        ("(unknown_var > 3)", False, "Unknown variable"),
        
        # Should fail: out of bounds constant
        ("(ego_speed < 200)", False, "Out of ODD bounds"),
    ]

    # Environment for evaluation
    env = {
        "ego_speed": 10.0,
        "dist_front": 4.0,
        "lane_offset": 0.0,
        "rel_speed": 0.0,
    }

    print("=" * 70)
    print("SEAMS 2026 Paper Examples")
    print("=" * 70)
    print()

    for rule_str, should_parse, description in test_cases:
        print(f"Test: {description}")
        print(f"Rule: {rule_str}")
        
        rule, errors = parser.parse_safe(rule_str)
        
        if errors:
            print(f"❌ Parse failed: {errors}")
            if not should_parse:
                print("✓ Expected failure")
        else:
            print(f"✅ Parse successful: {rule}")
            if should_parse:
                try:
                    result = rule.evaluate(env)
                    print(f"Evaluation on {env}: {result}")
                except Exception as e:
                    print(f"⚠️  Evaluation error: {e}")
            else:
                print("⚠️  Should have failed but parsed successfully")
        
        print("-" * 70)
        print()


if __name__ == "__main__":
    main()