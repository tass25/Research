"""
Adapter between cbf_data.loader.SimulationDataset and data.simulation_trace.SimulationDataset.

Bridges the Group A data layer (cbf_data) with the semantic validation layer (data/)
so that both can operate on the same simulation results without incompatible types.
"""

import logging
from typing import List, Optional

from cbf_data.loader import SimulationDataset as CbfDataset, SimulationRun
from data.simulation_trace import (
    SimulationDataset as SemanticDataset,
    SimulationTrace,
)

logger = logging.getLogger(__name__)


def cbf_to_semantic(cbf_dataset: CbfDataset) -> SemanticDataset:
    """Convert a cbf_data.loader.SimulationDataset → data.simulation_trace.SimulationDataset.

    This allows the semantic validation layer (consistency checker, contradiction
    checker, overfitting detector) to operate on pipeline data loaded by Group A.

    Args:
        cbf_dataset: A SimulationDataset loaded via cbf_data.loader.

    Returns:
        A semantic SimulationDataset with SimulationTrace entries.
    """
    traces: List[SimulationTrace] = []

    for run in cbf_dataset.runs:
        trace = SimulationTrace(
            input_vector=dict(run.input_features),
            observed_outcome=run.label,
            timestamp=None,
            metadata={
                "case_id": run.case_id,
                "min_h": run.min_h,
                "controller_error": run.controller_error,
                "case_runtime_s": run.case_runtime_s,
                "system": cbf_dataset.system,
                "controller": cbf_dataset.controller,
                "dataset_type": cbf_dataset.dataset_type,
            },
        )
        traces.append(trace)

    logger.debug(
        "Converted CbfDataset (%s/%s/%s, %d runs) → SemanticDataset (%d traces)",
        cbf_dataset.system,
        cbf_dataset.controller,
        cbf_dataset.dataset_type,
        cbf_dataset.n_runs,
        len(traces),
    )
    return SemanticDataset(traces=traces)


def semantic_to_cbf(
    semantic_dataset: SemanticDataset,
    system: str = "unknown",
    controller: str = "unknown",
    dataset_type: str = "unknown",
    feature_names: Optional[List[str]] = None,
) -> CbfDataset:
    """Convert a data.simulation_trace.SimulationDataset → cbf_data.loader.SimulationDataset.

    This allows semantic-layer datasets to be used with Group B/C inference
    and evaluation tools.

    Args:
        semantic_dataset: A SemanticDataset with SimulationTrace entries.
        system: System name for the output dataset.
        controller: Controller name for the output dataset.
        dataset_type: Dataset type ("legacy" / "evolved").
        feature_names: Ordered feature names. If None, inferred from first trace.

    Returns:
        A cbf_data SimulationDataset with SimulationRun entries.
    """
    if feature_names is None and semantic_dataset.traces:
        feature_names = sorted(semantic_dataset.traces[0].input_vector.keys())
    elif feature_names is None:
        feature_names = []

    runs: List[SimulationRun] = []
    for i, trace in enumerate(semantic_dataset.traces):
        meta = trace.metadata if trace.metadata else {}
        run = SimulationRun(
            case_id=meta.get("case_id", i),
            input_features=dict(trace.input_vector),
            label=trace.observed_outcome,
            min_h=meta.get("min_h", 0.0),
            controller_error=meta.get("controller_error", False),
            case_runtime_s=meta.get("case_runtime_s", 0.0),
        )
        runs.append(run)

    cbf = CbfDataset(
        system=system,
        controller=controller,
        dataset_type=dataset_type,
        runs=runs,
        feature_names=list(feature_names),
    )
    logger.debug(
        "Converted SemanticDataset (%d traces) → CbfDataset (%s/%s/%s, %d runs)",
        len(semantic_dataset.traces),
        system,
        controller,
        dataset_type,
        cbf.n_runs,
    )
    return cbf
