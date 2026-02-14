from dataclasses import dataclass
from typing import Dict, List, Set

@dataclass(frozen=True)
class CounterfactualPair:
    """Pair of original and counterfactual inputs.
    
    From paper: x (inconsistent) and x' (consistent) that differ minimally.
    """
    original_input: Dict[str, float]        # x
    original_outcome: str                    # y (observed)
    counterfactual_input: Dict[str, float]  # x'
    counterfactual_outcome: str              # y' (observed)
    perturbation: Dict[str, float]          # Δ = x' - x
    
    def perturbation_magnitude(self) -> float:
        """L1 distance between inputs."""
        return sum(abs(v) for v in self.perturbation.values())
    
    def get_changed_variables(self) -> Set[str]:
        """Which variables changed in counterfactual."""
        return {k for k, v in self.perturbation.items() if v != 0}

@dataclass(frozen=True)
class CounterfactualEvidence:
    """Collection of counterfactual pairs for a rule."""
    inconsistent_rule: str                   # The rule being refined
    pairs: List[CounterfactualPair]
    
    def get_decision_boundary_features(self) -> Set[str]:
        """Which features are on the decision boundary (commonly perturbed)."""
        features = set()
        for pair in self.pairs:
            features.update(pair.get_changed_variables())
        return features
