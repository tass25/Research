# CBF Data — Group A

Data integration layer for CBFKIT simulation datasets.

## Why This Folder Exists

The SEAMS 2026 pipeline analyses operational rules by comparing two controllers — a **vanilla** (legacy, no safety filter) controller and an **evolved** (CBF-QP) controller. This package loads the raw simulation CSV files, structures them into typed Python dataclasses, and provides a clean API so that Group B (rule inference) and Group C (rule validation) can consume datasets without knowing anything about file paths or CSV column conventions. It also includes a bidirectional adapter that converts between the `cbf_data` representation and the `data` (semantic layer) representation.

## Folder Structure

```
cbf_data/
├── __init__.py         # Re-exports cbf_to_semantic, semantic_to_cbf
├── loader.py           # SimulationDataset, SimulationRun, PairedComparison; load functions
├── metadata.py         # FeatureMetadata, SystemMetadata — physical bounds and units
├── adapter.py          # Bidirectional cbf_data ↔ data.simulation_trace converter
└── datasets/           # Raw CSV files organised by {system}/{controller}/
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

## Files

### `loader.py` — Dataset Loading

| Class / Function | Purpose |
|-----------------|---------|
| `SimulationRun` | Single simulation: `case_id`, `input_features` dict, `label` ("Pass"/"Fail"), `min_h`, `controller_error`, `case_runtime_s` |
| `SimulationDataset` | Collection of `SimulationRun` objects with `get_feature_matrix()` → `(List[List[float]], List[int])` |
| `PairedComparison` | Same initial conditions run on both controllers |
| `load_dataset(system, controller, dataset_type)` | Load a specific CSV into `SimulationDataset` |
| `load_paired_comparison(system, controller)` | Load matched vanilla/CBF pairs |
| `load_all_datasets()` | Load every available system/controller combination |
| `summarize_dataset(dataset)` | Generate human-readable summary of a dataset |
| `AVAILABLE_SYSTEMS` | Tuple list of valid `(system, controller)` combinations |

### `metadata.py` — Physical Bounds and Units

| Class / Function | Purpose |
|-----------------|---------|
| `FeatureMetadata` | Per-feature: `name`, `description`, `unit`, `sampling_range` (tuple), `physical_bounds` (tuple) |
| `SystemMetadata` | Per-system: `system_name`, `description`, `features` list, `legacy_controller`, `evolved_controller`, `cbf_type`, `simulation_dt`, `simulation_duration`, `n_samples`, `safety_condition`, `random_seed_info` |
| `get_system_metadata(system)` | Look up metadata for a given system |
| `get_feature_bounds(system)` | Return `{feature_name: (min, max)}` dict for validators |
| `print_metadata(system)` | Generate human-readable metadata report |

### `adapter.py` — Bidirectional Data Converter

| Function | Direction | Purpose |
|----------|-----------|---------|
| `cbf_to_semantic(cbf_dataset)` | `cbf_data` → `data` | Convert `cbf_data.loader.SimulationDataset` into `data.simulation_trace.SimulationDataset` (semantic layer) |
| `semantic_to_cbf(semantic_dataset, system, controller, dataset_type, feature_names)` | `data` → `cbf_data` | Convert back for re-evaluation or export (extra params are optional, default to `"unknown"`) |

The `__init__.py` re-exports both functions so callers can write:
```python
from cbf_data import cbf_to_semantic, semantic_to_cbf
```

## Key Datasets

| Name | Role |
|------|------|
| **D_legacy** | Runs from the legacy (vanilla) controller — mixture of Pass and Fail |
| **D_evolved** | Runs from the evolved (CBF) controller — expected 100% Pass |
| **D_paired_comparison** | Same initial conditions run with both controllers |

Each CSV contains simulation runs with input features and a `label` column (`Pass` / `Fail`).

## Features

**Static obstacle systems** (4 features):

| Feature | Unit | Description |
|---------|------|-------------|
| `initial_distance_to_obstacle` | metres | Starting distance to obstacle |
| `initial_speed` | m/s | Initial ego speed |
| `obstacle_radius` | metres | Obstacle radius |
| `initial_heading_error` | radians | Initial heading error |

**Dynamic obstacle systems** (6 features): above + `obstacle_speed` (m/s), `obstacle_heading` (radians).

## Usage

```python
from cbf_data.loader import load_dataset, AVAILABLE_SYSTEMS

# Load a single dataset
d_legacy = load_dataset("unicycle_static_obstacle", "robust_evolved", "legacy")
X, y = d_legacy.get_feature_matrix()   # (List[List[float]], List[int])

# Convert to semantic layer representation
from cbf_data import cbf_to_semantic
semantic_ds = cbf_to_semantic(d_legacy)
```

## Where It's Used

| Consumer | How It's Used |
|----------|--------------|
| `run_pipeline.py` | Group A stage: loads all datasets for inference and validation |
| `rule_inference/` | Group B: trains decision trees on `D_legacy` features |
| `rule_validation/` | Group C: evaluates rules against `D_evolved` |
| `semantic/` | Consistency/contradiction analysis against simulation traces |
| `examples/` | Demo scripts create sample datasets |
| `tests/test_cbf_data.py` | 28 unit tests covering loader, metadata, and adapter |

## Extensibility

To add a new system (e.g., HSR):

1. Place CSV files under `datasets/hsr_system/controller_name/`.
2. Add a `("hsr_system", "controller_name")` tuple to `AVAILABLE_SYSTEMS` in `loader.py`.
3. Register a new `SystemMetadata` entry in `metadata.py`.

## Dependencies

- **`numpy`** — Feature matrix conversion
- **`pandas`** — CSV loading
- **Internal:** `data.simulation_trace` (for adapter conversions)
