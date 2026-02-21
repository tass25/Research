# CBF Data — Group A

Data integration layer for CBFKIT simulation datasets.

## Purpose

Loads, structures, and exposes the CBFKIT Controller-Barrier-Function datasets
so that Group B (rule inference) and Group C (rule validation) can consume them
through a clean Python API.

## Files

| File | Description |
|------|-------------|
| `loader.py` | `SimulationDataset`, `SimulationRun`, `PairedComparison` dataclasses; `load_dataset()`, `load_paired_comparison()`, `load_all_datasets()` |
| `metadata.py` | `FeatureMetadata`, `SystemMetadata` with physical units, bounds, and controller parameters for each system |
| `__init__.py` | Package init |
| `datasets/` | Raw CSV files organised by `{system}/{controller}/` |

## Dataset Layout

```
datasets/
├── unicycle_static_obstacle/
│   ├── robust_evolved/       # CBF-QP controller
│   │   ├── D_legacy.csv
│   │   ├── D_evolved.csv
│   │   └── D_paired_comparison.csv
│   └── robust_vanilla/       # Nominal (no CBF)
│       └── ...
└── unicycle_dynamic_obstacle/
    ├── robust_evolved/
    └── robust_vanilla/
```

Each CSV contains simulation runs with input features and a `label` column (`Pass` / `Fail`).

### Key datasets

| Name | Role |
|------|------|
| **D_legacy** | Runs from the legacy (vanilla) controller — mixture of Pass and Fail |
| **D_evolved** | Runs from the evolved (CBF) controller — expected 100 % Pass |
| **D_paired_comparison** | Same initial conditions run with both controllers |

## Features

**Static obstacle systems** (4 features):

- `initial_distance_to_obstacle` — metres
- `initial_speed` — m/s
- `obstacle_radius` — metres
- `initial_heading_error` — radians

**Dynamic obstacle systems** (6 features): above + `obstacle_speed`, `obstacle_heading`.

## Quick Start

```python
from cbf_data.loader import load_dataset, AVAILABLE_SYSTEMS

d_legacy = load_dataset("unicycle_static_obstacle", "robust_evolved", "legacy")
X, y = d_legacy.get_feature_matrix()   # numpy arrays
```

## Extensibility

To add a new system (e.g., HSR):

1. Place CSV files under `datasets/hsr_system/controller_name/`.
2. Add a `("hsr_system", "controller_name")` tuple to `AVAILABLE_SYSTEMS` in `loader.py`.
3. Register a new `SystemMetadata` entry in `metadata.py`.
