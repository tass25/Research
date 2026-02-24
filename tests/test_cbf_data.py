"""Tests for cbf_data package: loader, metadata, adapter."""

import pytest
from pathlib import Path
from cbf_data.loader import (
    SimulationRun, SimulationDataset, PairedComparison,
    load_dataset, load_paired_comparison, load_all_datasets,
    summarize_dataset, _get_feature_names,
    STATIC_FEATURES, DYNAMIC_FEATURES, AVAILABLE_SYSTEMS,
)
from cbf_data.metadata import (
    FeatureMetadata, SystemMetadata, SYSTEM_REGISTRY,
    get_system_metadata, get_feature_bounds, print_metadata,
    UNICYCLE_STATIC_OBSTACLE, UNICYCLE_DYNAMIC_OBSTACLE,
)
from cbf_data.adapter import cbf_to_semantic, semantic_to_cbf
from data.simulation_trace import (
    SimulationDataset as SemanticDataset,
    SimulationTrace,
)


# ── SimulationRun / SimulationDataset unit tests ─────────────────────────

class TestSimulationRun:
    def test_basic_construction(self):
        run = SimulationRun(
            case_id=1,
            input_features={"x": 1.0, "y": 2.0},
            label="Pass",
            min_h=0.5,
            controller_error=False,
            case_runtime_s=0.12,
        )
        assert run.case_id == 1
        assert run.label == "Pass"


class TestSimulationDataset:
    def _dataset(self, labels):
        runs = [
            SimulationRun(i, {"x": float(i)}, lbl, 0.0, False, 0.0)
            for i, lbl in enumerate(labels)
        ]
        return SimulationDataset("sys", "ctrl", "legacy", runs, ["x"])

    def test_counts(self):
        ds = self._dataset(["Pass", "Pass", "Fail"])
        assert ds.n_runs == 3
        assert ds.n_pass == 2
        assert ds.n_fail == 1

    def test_pass_rate(self):
        ds = self._dataset(["Pass", "Fail"])
        assert ds.pass_rate == pytest.approx(0.5)

    def test_pass_rate_empty(self):
        ds = self._dataset([])
        assert ds.pass_rate == 0.0

    def test_get_feature_matrix(self):
        ds = self._dataset(["Pass", "Fail"])
        X, y = ds.get_feature_matrix()
        assert len(X) == 2
        assert y == [1, 0]


class TestPairedComparison:
    def test_inconsistent(self):
        pc = PairedComparison(1, {"x": 1}, "Fail", -0.1, "Pass", 0.2)
        assert pc.is_inconsistent is True

    def test_consistent(self):
        pc = PairedComparison(1, {"x": 1}, "Pass", 0.1, "Pass", 0.2)
        assert pc.is_inconsistent is False


# ── loader: load_dataset with actual CSVs ──────────────────────────────

class TestLoadDataset:
    def test_load_static_evolved(self):
        ds = load_dataset("unicycle_static_obstacle", "robust_evolved", "evolved")
        assert ds.n_runs > 0
        assert ds.system == "unicycle_static_obstacle"
        assert ds.controller == "robust_evolved"
        assert set(ds.feature_names) == set(STATIC_FEATURES)

    def test_load_dynamic_legacy(self):
        ds = load_dataset("unicycle_dynamic_obstacle", "robust_vanilla", "legacy")
        assert ds.n_runs > 0
        assert set(ds.feature_names) == set(DYNAMIC_FEATURES)

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_dataset("unicycle_static_obstacle", "robust_evolved", "nonexistent")

    def test_unknown_system(self):
        with pytest.raises(ValueError, match="Unknown system"):
            _get_feature_names("martian_obstacle")


class TestLoadPairedComparison:
    def test_load_pairs(self):
        pairs = load_paired_comparison("unicycle_static_obstacle", "robust_evolved")
        assert len(pairs) > 0
        assert isinstance(pairs[0], PairedComparison)

    def test_missing_file(self):
        with pytest.raises(FileNotFoundError):
            load_paired_comparison("unicycle_static_obstacle", "nonexistent_ctrl")


class TestLoadAll:
    def test_load_all_datasets(self):
        all_ds = load_all_datasets()
        assert isinstance(all_ds, dict)
        assert len(all_ds) > 0
        for key, ds in all_ds.items():
            assert ds.n_runs > 0


class TestSummarize:
    def test_summarize_dataset(self):
        ds = load_dataset("unicycle_static_obstacle", "robust_evolved", "evolved")
        summary = summarize_dataset(ds)
        assert "unicycle_static_obstacle" in summary
        assert "Pass:" in summary


# ── metadata module ──────────────────────────────────────────────────────

class TestMetadata:
    def test_static_in_registry(self):
        assert "unicycle_static_obstacle" in SYSTEM_REGISTRY

    def test_dynamic_in_registry(self):
        assert "unicycle_dynamic_obstacle" in SYSTEM_REGISTRY

    def test_get_system_metadata_static(self):
        meta = get_system_metadata("unicycle_static_obstacle")
        assert isinstance(meta, SystemMetadata)
        assert len(meta.features) == 4

    def test_get_system_metadata_dynamic(self):
        meta = get_system_metadata("unicycle_dynamic_obstacle")
        assert len(meta.features) == 6

    def test_get_system_metadata_unknown(self):
        with pytest.raises(ValueError, match="Unknown system"):
            get_system_metadata("mars_rover")

    def test_get_feature_bounds(self):
        bounds = get_feature_bounds("unicycle_static_obstacle")
        assert "initial_speed" in bounds
        lo, hi = bounds["initial_speed"]
        assert lo < hi

    def test_print_metadata(self):
        report = print_metadata("unicycle_static_obstacle")
        assert "System:" in report
        assert "initial_speed" in report

    def test_feature_metadata_frozen(self):
        fm = UNICYCLE_STATIC_OBSTACLE.features[0]
        with pytest.raises(AttributeError):
            fm.name = "changed"


# ── adapter: cbf_to_semantic / semantic_to_cbf ──────────────────────────

class TestAdapter:
    def _make_cbf_dataset(self):
        runs = [
            SimulationRun(0, {"x": 1.0, "y": 2.0}, "Pass", 0.5, False, 0.1),
            SimulationRun(1, {"x": 3.0, "y": 4.0}, "Fail", -0.1, True, 0.2),
        ]
        return SimulationDataset("sys", "ctrl", "legacy", runs, ["x", "y"])

    def test_cbf_to_semantic(self):
        cbf_ds = self._make_cbf_dataset()
        sem_ds = cbf_to_semantic(cbf_ds)
        assert isinstance(sem_ds, SemanticDataset)
        assert len(sem_ds.traces) == 2
        assert sem_ds.traces[0].observed_outcome == "Pass"
        assert sem_ds.traces[0].input_vector == {"x": 1.0, "y": 2.0}

    def test_cbf_to_semantic_preserves_metadata(self):
        cbf_ds = self._make_cbf_dataset()
        sem_ds = cbf_to_semantic(cbf_ds)
        meta = sem_ds.traces[0].metadata
        assert meta["case_id"] == 0
        assert meta["min_h"] == 0.5

    def test_semantic_to_cbf(self):
        traces = [
            SimulationTrace({"a": 10.0}, "Pass"),
            SimulationTrace({"a": 20.0}, "Fail"),
        ]
        sem_ds = SemanticDataset(traces=traces)
        cbf_ds = semantic_to_cbf(sem_ds, system="s", controller="c", dataset_type="d")
        assert isinstance(cbf_ds, SimulationDataset)
        assert cbf_ds.n_runs == 2
        assert cbf_ds.runs[0].label == "Pass"

    def test_round_trip(self):
        original = self._make_cbf_dataset()
        sem = cbf_to_semantic(original)
        back = semantic_to_cbf(sem, "sys", "ctrl", "legacy", ["x", "y"])
        assert back.n_runs == original.n_runs
        assert back.runs[0].label == original.runs[0].label
        for orig_run, back_run in zip(original.runs, back.runs):
            assert orig_run.input_features == back_run.input_features

    def test_semantic_to_cbf_empty(self):
        sem_ds = SemanticDataset(traces=[])
        cbf_ds = semantic_to_cbf(sem_ds)
        assert cbf_ds.n_runs == 0
        assert cbf_ds.feature_names == []
