"""
Configuration for grammar enforcement.

Defines allowed variables and their physical/operational bounds
based on the Operational Design Domain (ODD).
"""

from dataclasses import dataclass
from typing import Dict, Tuple, Set


@dataclass(frozen=True)
class GrammarConfig:
    """Configuration for operational rule validation.
    
    Attributes:
        allowed_variables: Set of variable names allowed in rules
        variable_bounds: Physical/logical limits per variable from ODD
    """
    allowed_variables: Set[str]
    variable_bounds: Dict[str, Tuple[float, float]]


# Default configuration for Autonomous Driving System (ADS)
DEFAULT_ADS_CONFIG = GrammarConfig(
    allowed_variables={
        "ego_speed",      # Ego vehicle speed (m/s)
        "dist_front",     # Distance to front vehicle (m)
        "lane_offset",    # Lateral offset within lane (m)
        "rel_speed",      # Relative speed to front vehicle (m/s)
    },
    variable_bounds={
        "ego_speed": (0.0, 50.0),       # 0-180 km/h
        "dist_front": (0.0, 200.0),     # 0-200 meters
        "lane_offset": (-5.0, 5.0),     # ±5 meters from lane center
        "rel_speed": (-50.0, 50.0),     # ±50 m/s relative speed
    },
)