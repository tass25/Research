# Importing modules

from dataclasses import dataclass
from typing import Dict, Tuple, Set


# This class defines a configuration for a "grammar"(rules for variables in a system )
@dataclass(frozen=True)
class GrammarConfig:
    allowed_variables: Set[str]            
    variable_bounds: Dict[str, Tuple[float, float]]  
    # For each variable, define a min and max value it can take


# This is a default configuration for an Autonomous Driving System
DEFAULT_ADS_CONFIG = GrammarConfig(
    allowed_variables={
        "ego_speed",    # The speed of the car itself
        "dist_front",   # Distance to the car in front
        "lane_offset",  # How far the car is from the center of the lane
        "rel_speed",    # Relative speed compared to the car in front
    },
    variable_bounds={
        "ego_speed": (0.0, 50.0),     # Speed can be 0 to 50 m/s
        "dist_front": (0.0, 200.0),   # Distance in meters
        "lane_offset": (-5.0, 5.0),   # Offset left or right in meters
        "rel_speed": (-50.0, 50.0),   # Relative speed in m/s
    },
)