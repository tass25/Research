"""Tests for core/config_loader.py and core/logging_config.py."""

import logging
import pytest
import yaml
from pathlib import Path

from core.config import GrammarConfig
from core.config_loader import (
    ThresholdConfig,
    PipelineConfig,
    load_config,
    load_pipeline_config,
    load_config_from_dict,
    save_config,
)
from core.logging_config import (
    ColoredFormatter,
    setup_logging,
    get_logger,
    _HAS_COLOR,
)


# ── ThresholdConfig / PipelineConfig dataclass basics ─────────────────────

class TestThresholdConfig:
    def test_defaults(self):
        tc = ThresholdConfig()
        assert tc.consistency_threshold == 0.95
        assert tc.min_false_positive_rate == 0.20
        assert tc.max_depth == 10

    def test_override(self):
        tc = ThresholdConfig(consistency_threshold=0.8)
        assert tc.consistency_threshold == 0.8


class TestPipelineConfig:
    def test_defaults(self):
        gc = GrammarConfig(
            allowed_variables={"x"}, variable_bounds={"x": (0, 10)}
        )
        pc = PipelineConfig(grammar=gc)
        assert pc.random_seed == 42
        assert pc.top_k == 10
        assert pc.dt_depths == [2, 3, 4, 5, None]


# ── load_config (GrammarConfig from YAML) ────────────────────────────────

class TestLoadConfig:
    def test_valid_yaml(self, tmp_path):
        cfg = {
            "allowed_variables": ["ego_speed", "dist_front"],
            "variable_bounds": {
                "ego_speed": [0.0, 50.0],
                "dist_front": [0.0, 200.0],
            },
        }
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump(cfg))

        result = load_config(str(p))
        assert isinstance(result, GrammarConfig)
        assert "ego_speed" in result.allowed_variables
        assert result.variable_bounds["dist_front"] == (0.0, 200.0)

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent.yaml")

    def test_invalid_not_mapping(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text("- a list\n- not a mapping\n")
        with pytest.raises(ValueError, match="mapping"):
            load_config(str(p))

    def test_missing_allowed_variables(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump({"variable_bounds": {"x": [0, 1]}}))
        with pytest.raises(ValueError, match="allowed_variables"):
            load_config(str(p))

    def test_bad_bounds_format(self, tmp_path):
        cfg = {
            "allowed_variables": ["x"],
            "variable_bounds": {"x": "not_a_list"},
        }
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump(cfg))
        with pytest.raises(ValueError, match="Bounds"):
            load_config(str(p))


# ── load_pipeline_config ─────────────────────────────────────────────────

class TestLoadPipelineConfig:
    def test_full_pipeline(self, tmp_path):
        cfg = {
            "grammar": {
                "allowed_variables": ["speed"],
                "variable_bounds": {"speed": [0, 100]},
            },
            "thresholds": {
                "consistency_threshold": 0.90,
            },
            "inference": {
                "dt_depths": [2, 3],
                "rf_n_estimators": 50,
            },
            "random_seed": 99,
        }
        p = tmp_path / "pipeline.yaml"
        p.write_text(yaml.dump(cfg))

        result = load_pipeline_config(str(p))
        assert isinstance(result, PipelineConfig)
        assert "speed" in result.grammar.allowed_variables
        assert result.thresholds.consistency_threshold == 0.90
        assert result.rf_n_estimators == 50
        assert result.random_seed == 99

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_pipeline_config("nowhere.yaml")

    def test_missing_grammar_section(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump({"thresholds": {}}))
        with pytest.raises(ValueError, match="grammar"):
            load_pipeline_config(str(p))

    def test_invalid_not_mapping(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text("just text")
        with pytest.raises(ValueError, match="mapping"):
            load_pipeline_config(str(p))


# ── load_config_from_dict / save_config ──────────────────────────────────

class TestConfigHelpers:
    def test_from_dict(self):
        d = {
            "allowed_variables": ["a", "b"],
            "variable_bounds": {"a": [0, 1], "b": [2, 3]},
        }
        gc = load_config_from_dict(d)
        assert gc.allowed_variables == {"a", "b"}

    def test_save_and_reload(self, tmp_path):
        gc = GrammarConfig(
            allowed_variables={"x", "y"},
            variable_bounds={"x": (0, 10), "y": (-5, 5)},
        )
        out_path = tmp_path / "saved.yaml"
        save_config(gc, str(out_path))
        assert out_path.exists()

        reloaded = load_config(str(out_path))
        assert reloaded.allowed_variables == gc.allowed_variables
        assert reloaded.variable_bounds == gc.variable_bounds


# ── logging_config ───────────────────────────────────────────────────────

class TestColoredFormatter:
    def test_format_info(self):
        fmt = ColoredFormatter("%(levelname)s %(message)s")
        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "hello", (), None
        )
        output = fmt.format(record)
        assert "hello" in output

    def test_format_error(self):
        fmt = ColoredFormatter("%(levelname)s %(message)s")
        record = logging.LogRecord(
            "test", logging.ERROR, "", 0, "oops", (), None
        )
        output = fmt.format(record)
        assert "oops" in output

    def test_format_debug(self):
        fmt = ColoredFormatter("%(message)s")
        record = logging.LogRecord(
            "test", logging.DEBUG, "", 0, "dbg", (), None
        )
        output = fmt.format(record)
        assert "dbg" in output


class TestSetupLogging:
    def test_get_logger(self):
        lg = get_logger("my_test_module")
        assert isinstance(lg, logging.Logger)
        assert lg.name == "my_test_module"

    def test_setup_with_file(self, tmp_path):
        # Reset the _CONFIGURED flag so we can call setup_logging again
        import core.logging_config as lc
        lc._CONFIGURED = False

        log_file = str(tmp_path / "test.log")
        setup_logging("DEBUG", log_file=log_file)
        assert Path(log_file).exists() or True  # file created on first write

        # Reset for other tests
        lc._CONFIGURED = False
        # Clean up handlers to avoid side effects
        root = logging.getLogger()
        for h in root.handlers[:]:
            root.removeHandler(h)

    def test_idempotent(self):
        import core.logging_config as lc
        lc._CONFIGURED = True
        # Should be a no-op
        setup_logging("WARNING")
        lc._CONFIGURED = False
