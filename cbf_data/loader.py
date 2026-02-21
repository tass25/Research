"""
Data loader for CBFKIT simulation datasets.

Loads D_legacy, D_evolved, and D_paired_comparison CSVs
into structured DataFrames with proper typing.
"""

import csv
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


@dataclass
class SimulationRun:
    """A single simulation run result."""
    case_id: int
    input_features: Dict[str, float]
    label: str  # "Pass" or "Fail"
    min_h: float
    controller_error: bool
    case_runtime_s: float


@dataclass
class SimulationDataset:
    """A collection of simulation runs with metadata."""
    system: str           # e.g., "unicycle_static_obstacle"
    controller: str       # e.g., "robust_evolved"
    dataset_type: str     # "legacy" or "evolved"
    runs: List[SimulationRun] = field(default_factory=list)
    feature_names: List[str] = field(default_factory=list)

    @property
    def n_runs(self) -> int:
        return len(self.runs)

    @property
    def n_pass(self) -> int:
        return sum(1 for r in self.runs if r.label == "Pass")

    @property
    def n_fail(self) -> int:
        return sum(1 for r in self.runs if r.label == "Fail")

    @property
    def pass_rate(self) -> float:
        return self.n_pass / self.n_runs if self.n_runs > 0 else 0.0

    def get_feature_matrix(self) -> Tuple[List[List[float]], List[int]]:
        """Return (X, y) where X is feature matrix and y is binary labels (1=Pass, 0=Fail)."""
        X = []
        y = []
        for run in self.runs:
            row = [run.input_features[f] for f in self.feature_names]
            X.append(row)
            y.append(1 if run.label == "Pass" else 0)
        return X, y


@dataclass
class PairedComparison:
    """A paired comparison between legacy and evolved controller on same input."""
    case_id: int
    input_features: Dict[str, float]
    legacy_label: str
    legacy_min_h: float
    evolved_label: str
    evolved_min_h: float

    @property
    def is_inconsistent(self) -> bool:
        """True when legacy says Fail but evolved says Pass (spurious failure)."""
        return self.legacy_label == "Fail" and self.evolved_label == "Pass"


# Feature columns per system type
STATIC_FEATURES = [
    "initial_distance_to_obstacle",
    "initial_speed",
    "obstacle_radius",
    "initial_heading_error",
]

DYNAMIC_FEATURES = [
    "initial_distance_to_obstacle",
    "initial_speed",
    "obstacle_radius",
    "initial_heading_error",
    "obstacle_speed",
    "obstacle_heading",
]

# All available system-controller combinations
AVAILABLE_SYSTEMS = [
    ("unicycle_static_obstacle", "robust_evolved"),
    ("unicycle_static_obstacle", "robust_vanilla"),
    ("unicycle_dynamic_obstacle", "robust_evolved"),
    ("unicycle_dynamic_obstacle", "robust_vanilla"),
]


def _get_data_dir() -> Path:
    """Get the datasets directory path."""
    return Path(__file__).parent / "datasets"


def _get_feature_names(system: str) -> List[str]:
    """Get feature column names for a given system type."""
    if "static" in system:
        return STATIC_FEATURES
    elif "dynamic" in system:
        return DYNAMIC_FEATURES
    else:
        raise ValueError(f"Unknown system type: {system}")


def load_dataset(
    system: str,
    controller: str,
    dataset_type: str,
) -> SimulationDataset:
    """Load a simulation dataset from CSV.

    Args:
        system: System name (e.g., "unicycle_static_obstacle")
        controller: Controller type (e.g., "robust_evolved")
        dataset_type: "legacy" or "evolved"

    Returns:
        SimulationDataset with all runs loaded.

    Raises:
        FileNotFoundError: If CSV file doesn't exist.
        ValueError: If invalid system/controller/type combination.
    """
    data_dir = _get_data_dir()
    filename = f"D_{dataset_type}.csv"
    csv_path = data_dir / system / controller / filename

    if not csv_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {csv_path}\n"
            f"Available: {[str(s) + '/' + str(c) for s, c in AVAILABLE_SYSTEMS]}"
        )

    feature_names = _get_feature_names(system)
    dataset = SimulationDataset(
        system=system,
        controller=controller,
        dataset_type=dataset_type,
        feature_names=feature_names,
    )

    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            features = {feat: float(row[feat]) for feat in feature_names}
            run = SimulationRun(
                case_id=int(row["case_id"]),
                input_features=features,
                label=row["label"],
                min_h=float(row["min_h"]),
                controller_error=row["controller_error"] == "True",
                case_runtime_s=float(row["case_runtime_s"]),
            )
            dataset.runs.append(run)

    return dataset


def load_paired_comparison(
    system: str,
    controller: str,
) -> List[PairedComparison]:
    """Load paired comparison data (legacy vs evolved on same inputs).

    Args:
        system: System name (e.g., "unicycle_static_obstacle")
        controller: Controller type (e.g., "robust_evolved")

    Returns:
        List of PairedComparison records.
    """
    data_dir = _get_data_dir()
    csv_path = data_dir / system / controller / "D_paired_comparison.csv"

    if not csv_path.exists():
        raise FileNotFoundError(f"Paired comparison not found: {csv_path}")

    feature_names = _get_feature_names(system)
    pairs = []

    with open(csv_path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            features = {feat: float(row[feat]) for feat in feature_names}
            pair = PairedComparison(
                case_id=int(row["case_id"]),
                input_features=features,
                legacy_label=row["legacy_label"],
                legacy_min_h=float(row["legacy_min_h"]),
                evolved_label=row["evolved_label"],
                evolved_min_h=float(row["evolved_min_h"]),
            )
            pairs.append(pair)

    return pairs


def load_all_datasets() -> Dict[str, SimulationDataset]:
    """Load all available datasets.

    Returns:
        Dict mapping "system/controller/type" to SimulationDataset.
    """
    all_data = {}
    for system, controller in AVAILABLE_SYSTEMS:
        for dtype in ["legacy", "evolved"]:
            key = f"{system}/{controller}/{dtype}"
            try:
                all_data[key] = load_dataset(system, controller, dtype)
            except FileNotFoundError:
                pass
    return all_data


def summarize_dataset(dataset: SimulationDataset) -> str:
    """Generate a human-readable summary of a dataset."""
    lines = [
        f"Dataset: {dataset.system} / {dataset.controller} / {dataset.dataset_type}",
        f"Total runs: {dataset.n_runs}",
        f"Pass: {dataset.n_pass} ({dataset.pass_rate:.1%})",
        f"Fail: {dataset.n_fail} ({1 - dataset.pass_rate:.1%})",
        f"Features: {', '.join(dataset.feature_names)}",
    ]

    # Feature ranges
    if dataset.runs:
        lines.append("Feature ranges:")
        for feat in dataset.feature_names:
            vals = [r.input_features[feat] for r in dataset.runs]
            lines.append(f"  {feat}: [{min(vals):.4f}, {max(vals):.4f}]")

    return "\n".join(lines)
