"""
YAML / TOML configuration loader.

Loads pipeline configuration from YAML files, merging with defaults.
Replaces the hardcoded DEFAULT_ADS_CONFIG for production use.

Usage:
    from core.config_loader import load_config, load_pipeline_config

    # Load grammar config from YAML
    config = load_config("config.yaml")

    # Load full pipeline config (thresholds + grammar)
    pipeline = load_pipeline_config("pipeline.yaml")
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple

import yaml

from core.config import GrammarConfig

logger = logging.getLogger(__name__)


# ── Pipeline-level configuration ─────────────────────────────────────────

@dataclass
class ThresholdConfig:
    """Configurable thresholds (previously hardcoded across 6+ modules)."""

    # Semantic validation (semantic_validator.py)
    consistency_threshold: float = 0.95
    overfitting_risk_threshold: float = 0.7

    # Overfitting detection (overfitting_detector.py)
    boundary_sensitivity: float = 0.5
    constant_specificity_decimals: int = 1
    train_test_gap: float = 0.15

    # Minimality (minimality_validator.py)
    minimality_threshold: float = 0.7

    # Rule selection (rule_selector.py)
    min_false_positive_rate: float = 0.20
    max_false_negative_rate: float = 0.05

    # Structure (structure.py)
    max_depth: int = 10
    max_predicates: int = 20


@dataclass
class PipelineConfig:
    """Full pipeline configuration."""

    grammar: GrammarConfig
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)

    # Inference settings
    dt_depths: list = field(default_factory=lambda: [2, 3, 4, 5, None])
    dt_min_samples_leaf: int = 5
    rf_n_estimators: int = 100
    rf_max_depth: int = 4
    hc_n_estimators: int = 200
    hc_max_depth: int = 5
    hc_min_confidence: float = 0.75
    hc_min_support: int = 10

    # Selection
    top_k: int = 10

    # Reproducibility
    random_seed: int = 42


# ── Loaders ──────────────────────────────────────────────────────────────

def load_config(path: str) -> GrammarConfig:
    """Load a GrammarConfig from a YAML file.

    Expected YAML structure::

        allowed_variables:
          - ego_speed
          - dist_front
        variable_bounds:
          ego_speed: [0.0, 50.0]
          dist_front: [0.0, 200.0]

    Args:
        path: Path to YAML file.

    Returns:
        GrammarConfig built from file contents.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If YAML structure is invalid.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {p}")

    with open(p, "r", encoding="utf-8") as f:
        raw: Dict[str, Any] = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"Config file must be a YAML mapping, got {type(raw).__name__}")

    # Parse allowed_variables
    allowed = raw.get("allowed_variables")
    if not allowed or not isinstance(allowed, list):
        raise ValueError("'allowed_variables' must be a non-empty list of strings")
    allowed_set: Set[str] = set(allowed)

    # Parse variable_bounds
    bounds_raw = raw.get("variable_bounds", {})
    if not isinstance(bounds_raw, dict):
        raise ValueError("'variable_bounds' must be a mapping of variable → [min, max]")

    bounds: Dict[str, Tuple[float, float]] = {}
    for var, vals in bounds_raw.items():
        if not isinstance(vals, (list, tuple)) or len(vals) != 2:
            raise ValueError(
                f"Bounds for '{var}' must be [min, max], got {vals}"
            )
        bounds[var] = (float(vals[0]), float(vals[1]))

    config = GrammarConfig(allowed_variables=allowed_set, variable_bounds=bounds)
    logger.info("Loaded GrammarConfig from %s (%d variables)", p, len(allowed_set))
    return config


def load_pipeline_config(path: str) -> PipelineConfig:
    """Load a full PipelineConfig from YAML.

    Expected YAML structure::

        grammar:
          allowed_variables: [...]
          variable_bounds: {...}
        thresholds:
          consistency_threshold: 0.95
          min_false_positive_rate: 0.20
          ...
        inference:
          dt_depths: [2, 3, 4, 5, null]
          rf_n_estimators: 100
          ...
        random_seed: 42

    Args:
        path: Path to YAML file.

    Returns:
        PipelineConfig with grammar + thresholds + inference settings.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Pipeline config not found: {p}")

    with open(p, "r", encoding="utf-8") as f:
        raw: Dict[str, Any] = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"Config file must be a YAML mapping, got {type(raw).__name__}")

    # Grammar section (required)
    grammar_section = raw.get("grammar")
    if not grammar_section:
        raise ValueError("'grammar' section is required in pipeline config")

    grammar = load_config_from_dict(grammar_section)

    # Thresholds section (optional, uses defaults)
    thresholds = ThresholdConfig()
    thresh_raw = raw.get("thresholds", {})
    if isinstance(thresh_raw, dict):
        for key, val in thresh_raw.items():
            if hasattr(thresholds, key):
                setattr(thresholds, key, type(getattr(thresholds, key))(val))
            else:
                logger.warning("Unknown threshold key: %s", key)

    # Inference section (optional)
    inf_raw = raw.get("inference", {})

    _default_depths = [2, 3, 4, 5, None]

    pipeline = PipelineConfig(
        grammar=grammar,
        thresholds=thresholds,
        dt_depths=inf_raw.get("dt_depths", _default_depths),
        dt_min_samples_leaf=inf_raw.get("dt_min_samples_leaf", 5),
        rf_n_estimators=inf_raw.get("rf_n_estimators", 100),
        rf_max_depth=inf_raw.get("rf_max_depth", 4),
        hc_n_estimators=inf_raw.get("hc_n_estimators", 200),
        hc_max_depth=inf_raw.get("hc_max_depth", 5),
        hc_min_confidence=inf_raw.get("hc_min_confidence", 0.75),
        hc_min_support=inf_raw.get("hc_min_support", 10),
        top_k=raw.get("top_k", 10),
        random_seed=raw.get("random_seed", 42),
    )

    logger.info("Loaded PipelineConfig from %s", p)
    return pipeline


def load_config_from_dict(d: Dict[str, Any]) -> GrammarConfig:
    """Build GrammarConfig from a dict (e.g. parsed from YAML section)."""
    allowed = d.get("allowed_variables", [])
    bounds_raw = d.get("variable_bounds", {})
    bounds = {k: (float(v[0]), float(v[1])) for k, v in bounds_raw.items()}
    return GrammarConfig(allowed_variables=set(allowed), variable_bounds=bounds)


def save_config(config: GrammarConfig, path: str) -> None:
    """Save a GrammarConfig to YAML for reproducibility.

    Args:
        config: The GrammarConfig to serialize.
        path: Output file path.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "allowed_variables": sorted(config.allowed_variables),
        "variable_bounds": {
            k: list(v) for k, v in sorted(config.variable_bounds.items())
        },
    }
    with open(p, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    logger.info("Saved GrammarConfig to %s", p)
