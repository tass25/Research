"""
Dataset metadata for CBFKIT simulation datasets.

Documents the schema, feature meanings, units, bounds,
controller parameters, and simulation settings for reproducibility.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class FeatureMetadata:
    """Metadata for a single input feature."""
    name: str
    description: str
    unit: str
    sampling_range: Tuple[float, float]
    physical_bounds: Tuple[float, float]


@dataclass(frozen=True)
class SystemMetadata:
    """Metadata for a CBFKIT system configuration."""
    system_name: str
    description: str
    features: List[FeatureMetadata]
    legacy_controller: str
    evolved_controller: str
    cbf_type: str
    simulation_dt: float          # Time step (seconds)
    simulation_duration: float     # Total duration (seconds)
    n_samples: int                 # Number of input samples
    safety_condition: str          # h(x) >= 0 description
    random_seed_info: str


# ── Static obstacle system metadata ──────────────────────────────────────────

STATIC_FEATURES_META = [
    FeatureMetadata(
        name="initial_distance_to_obstacle",
        description="Euclidean distance from unicycle to static obstacle at t=0",
        unit="m",
        sampling_range=(0.5, 5.0),
        physical_bounds=(0.0, 100.0),
    ),
    FeatureMetadata(
        name="initial_speed",
        description="Initial linear speed of the unicycle",
        unit="m/s",
        sampling_range=(0.1, 3.0),
        physical_bounds=(0.0, 10.0),
    ),
    FeatureMetadata(
        name="obstacle_radius",
        description="Radius of the circular static obstacle",
        unit="m",
        sampling_range=(0.2, 1.5),
        physical_bounds=(0.01, 5.0),
    ),
    FeatureMetadata(
        name="initial_heading_error",
        description="Difference between unicycle heading and goal direction at t=0",
        unit="rad",
        sampling_range=(-3.14, 3.14),
        physical_bounds=(-3.14159, 3.14159),
    ),
]

UNICYCLE_STATIC_OBSTACLE = SystemMetadata(
    system_name="unicycle_static_obstacle",
    description=(
        "Unicycle robot navigating around a circular static obstacle. "
        "The CBF ensures the robot maintains a safe distance h(x) >= 0 "
        "from the obstacle throughout the trajectory."
    ),
    features=STATIC_FEATURES_META,
    legacy_controller="LQR / pure pursuit (nominal, no CBF)",
    evolved_controller="CBF-QP with barrier constraint (robust safety filter)",
    cbf_type="Distance-based barrier: h(x) = ||p - p_obs||^2 - r^2",
    simulation_dt=0.07,
    simulation_duration=20.0,
    n_samples=200,
    safety_condition="h(x(t)) = ||position - obstacle_center||^2 - obstacle_radius^2 >= 0",
    random_seed_info="Uniform random sampling over input ranges, shared seeds between legacy and evolved",
)

# ── Dynamic obstacle system metadata ─────────────────────────────────────────

DYNAMIC_FEATURES_META = STATIC_FEATURES_META + [
    FeatureMetadata(
        name="obstacle_speed",
        description="Linear speed of the moving obstacle",
        unit="m/s",
        sampling_range=(0.1, 1.5),
        physical_bounds=(0.0, 5.0),
    ),
    FeatureMetadata(
        name="obstacle_heading",
        description="Heading direction of the moving obstacle",
        unit="rad",
        sampling_range=(-3.14, 3.14),
        physical_bounds=(-3.14159, 3.14159),
    ),
]

UNICYCLE_DYNAMIC_OBSTACLE = SystemMetadata(
    system_name="unicycle_dynamic_obstacle",
    description=(
        "Unicycle robot navigating around a moving circular obstacle. "
        "The CBF accounts for obstacle velocity to maintain safety. "
        "This is a harder scenario where the legacy controller fails more often."
    ),
    features=DYNAMIC_FEATURES_META,
    legacy_controller="LQR / pure pursuit (nominal, no CBF)",
    evolved_controller="CBF-QP with barrier constraint (robust safety filter)",
    cbf_type="Distance-based barrier with obstacle velocity compensation",
    simulation_dt=0.07,
    simulation_duration=20.0,
    n_samples=200,
    safety_condition="h(x(t)) = ||position - obstacle_position(t)||^2 - obstacle_radius^2 >= 0",
    random_seed_info="Uniform random sampling over input ranges, shared seeds between legacy and evolved",
)


# Registry of all available system metadata
SYSTEM_REGISTRY: Dict[str, SystemMetadata] = {
    "unicycle_static_obstacle": UNICYCLE_STATIC_OBSTACLE,
    "unicycle_dynamic_obstacle": UNICYCLE_DYNAMIC_OBSTACLE,
}


def get_system_metadata(system_name: str) -> SystemMetadata:
    """Get metadata for a CBFKIT system.

    Args:
        system_name: One of "unicycle_static_obstacle", "unicycle_dynamic_obstacle"

    Returns:
        SystemMetadata with full documentation.
    """
    if system_name not in SYSTEM_REGISTRY:
        raise ValueError(
            f"Unknown system: {system_name}. "
            f"Available: {list(SYSTEM_REGISTRY.keys())}"
        )
    return SYSTEM_REGISTRY[system_name]


def get_feature_bounds(system_name: str) -> Dict[str, Tuple[float, float]]:
    """Get physical bounds for all features of a system.

    Useful for grammar config integration.

    Returns:
        Dict mapping feature name to (min, max) physical bounds.
    """
    meta = get_system_metadata(system_name)
    return {f.name: f.physical_bounds for f in meta.features}


def print_metadata(system_name: str) -> str:
    """Generate a human-readable metadata report."""
    meta = get_system_metadata(system_name)
    lines = [
        f"System: {meta.system_name}",
        f"Description: {meta.description}",
        f"",
        f"Controllers:",
        f"  Legacy: {meta.legacy_controller}",
        f"  Evolved: {meta.evolved_controller}",
        f"  CBF type: {meta.cbf_type}",
        f"",
        f"Simulation:",
        f"  Time step: {meta.simulation_dt} s",
        f"  Duration: {meta.simulation_duration} s",
        f"  Samples: {meta.n_samples}",
        f"  Safety condition: {meta.safety_condition}",
        f"  Seeds: {meta.random_seed_info}",
        f"",
        f"Input Features ({len(meta.features)}):",
    ]
    for f in meta.features:
        lines.append(
            f"  {f.name}: {f.description} [{f.unit}] "
            f"sampled [{f.sampling_range[0]}, {f.sampling_range[1]}], "
            f"physical [{f.physical_bounds[0]}, {f.physical_bounds[1]}]"
        )
    return "\n".join(lines)
