"""Data structures for semantic validation."""

from .simulation_trace import SimulationTrace, SimulationDataset
from .counterfactual_evidence import CounterfactualPair, CounterfactualEvidence
from .semantic_result import (
    SemanticValidationResult, 
    ConsistencyIssue, 
    ContradictionIssue, 
    OverfittingIndicator
)
from .minimality_result import RelationChange, MinimalityResult

__all__ = [
    "SimulationTrace",
    "SimulationDataset",
    "CounterfactualPair",
    "CounterfactualEvidence",
    "SemanticValidationResult",
    "ConsistencyIssue",
    "ContradictionIssue",
    "OverfittingIndicator",
    "RelationChange",
    "MinimalityResult",
]
