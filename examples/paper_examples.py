from core.config import DEFAULT_ADS_CONFIG
from parsers.lark_parser import OperationalRuleParser

# Create a parser instance with the default ADS configuration
parser = OperationalRuleParser(DEFAULT_ADS_CONFIG)

# Example rules to test
examples = [
    "(dist_front < 5.0) ∧ (ego_speed > 0)",         # valid rule
    "```(dist_front < 4.1) ∧ (ego_speed > 0)```", # valid rule inside code block
    "(unknown_var > 3)",                           # invalid rule (variable not allowed)
]

# Loop over each example rule
for rule in examples:
    # Parse safely (returns result and errors)
    parsed, errors = parser.parse_safe(rule)

    print("Rule:", rule)

    if errors:
        # If parsing failed, print the errors
        print("❌ Errors:", errors)
    else:
        # If parsing succeeded, evaluate the rule with a sample environment
        env = {
            "dist_front": 4.0,   # distance to front car
            "ego_speed": 10.0,   # car speed
            "lane_offset": 0.0,  # lane position
            "rel_speed": 0.0,    # relative speed
        }
        print("✅ Evaluates to:", parsed.evaluate(env))  # True or False

    print("-" * 40)  # Separator for readability