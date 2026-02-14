# test_parser_part2.py
from parsers.lark_parser import OperationalRuleParser
from core.config import DEFAULT_ADS_CONFIG
import sys

def main():
    print("Initializing parser...")
    try:
        parser = OperationalRuleParser(DEFAULT_ADS_CONFIG)
    except Exception as e:
        print(f"❌ Failed to initialize parser: {e}")
        return

    test_rules = [
        "(ego_speed > 10) AND (dist_front < 5)",  # Using AND keyword
        "(ego_speed > 10) ∧ (dist_front < 5)",     # Using Unicode
        "((ego_speed > 10) AND (dist_front < 5)) OR (lane_offset < 1)",  # Grouped
    ]

    all_passed = True

    for rule_str in test_rules:
        # Normalize for print logic (utf-8 print issues often happen on windows terminals)
        safe_rule_str = rule_str.encode('ascii', 'replace').decode('ascii')
        print(f"\nTesting rule: {safe_rule_str}")
        
        rule, errors = parser.parse_safe(rule_str)
        if errors:
            print(f"❌ Failed: {errors}")
            all_passed = False
        else:
            print(f"✅ Parsed: {type(rule)}")
            
            # TEST EVALUATION
            test_input = {
                "ego_speed": 15.0,
                "dist_front": 3.0,
                "lane_offset": 0.5,
                "rel_speed": 0.0
            }
            try:
                result = rule.evaluate(test_input)
                print(f"   Evaluates to: {result}")
            except Exception as e:
                print(f"   ❌ Evaluation failed: {e}")
                all_passed = False

    if all_passed:
        print("\n✅ All parser tests passed!")
    else:
        print("\n❌ Some tests failed.")

if __name__ == "__main__":
    main()
