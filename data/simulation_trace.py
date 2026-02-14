from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Any, Optional

@dataclass(frozen=True)
class SimulationTrace:
    """Single simulation run with input and observed outcome."""
    input_vector: Dict[str, float]      # {"ego_speed": 25.0, "dist_front": 10.0, ...}
    observed_outcome: str               # "Pass" or "Fail"
    timestamp: Optional[float] = None   # When was this run executed
    metadata: Dict[str, Any] = field(default_factory=dict)  # Extra info

@dataclass(frozen=True)
class SimulationDataset:
    """Collection of simulation traces."""
    traces: List[SimulationTrace]
    
    def filter_by_outcome(self, outcome: str) -> List[SimulationTrace]:
        """Filter traces by outcome (Pass/Fail)."""
        return [t for t in self.traces if t.observed_outcome == outcome]
        
    def get_all_variables(self) -> Set[str]:
        """Extract all variable names used."""
        vars_set = set()
        for trace in self.traces:
            vars_set.update(trace.input_vector.keys())
        return vars_set
        
    def split_train_test(self, test_ratio: float = 0.2) -> Tuple['SimulationDataset', 'SimulationDataset']:
        """Split into training and test sets."""
        # Simple split for now, could be randomized
        split_idx = int(len(self.traces) * (1 - test_ratio))
        return (
            SimulationDataset(self.traces[:split_idx]),
            SimulationDataset(self.traces[split_idx:])
        )
