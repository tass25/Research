"""
Counterfactual generator for semantic validation.

Generates counterfactual inputs for boundary analysis.
"""

from typing import Dict, List, Tuple, Optional
from core.schema import Rule
from data.counterfactual_evidence import CounterfactualPair
import numpy as np

class CounterfactualGenerator:
    """Generates counterfactual inputs for overfitting detection.
    
    From paper: "Counterfactual Analysis step generates a counterfactual 
    input x' together with its observed outcome label y' obtained by 
    re-executing the system."
    """
    
    def __init__(self, simulator_callback=None):
        """
        Args:
            simulator_callback: Function that takes input dict and returns outcome.
                                If None, must provide outcomes manually.
        """
        self.simulator_callback = simulator_callback
    
    def generate_counterfactual(
        self,
        original_input: Dict[str, float],
        original_outcome: str,
        rule: Rule,
        bounds: Dict[str, Tuple[float, float]],
        search_method: str = "L1_minimal"
    ) -> Optional[CounterfactualPair]:
        """Generate counterfactual for an inconsistent case.
        
        From paper: "L1 minimal-change search over the input space, which 
        identifies the smallest modification that restores agreement between 
        the rule verdict and the observed system behavior."
        
        Algorithm:
        1. Start from original_input
        2. Incrementally expand L1 radius
        3. Test modified inputs until verdict flips
        4. Return first flip found (minimal change)
        
        Returns:
            CounterfactualPair if found, None otherwise
        """
        # L1 minimal search
        
        for radius in np.arange(0.1, 10.0, 0.1):
            # Generate candidates within L1 ball of radius
            candidates = self._generate_L1_candidates(
                original_input, radius, bounds
            )
            
            for candidate in candidates:
                # Evaluate rule on candidate
                try:
                    rule_holds = rule.evaluate(candidate)
                except KeyError:
                    continue
                
                # Get simulated outcome (requires re-execution)
                if self.simulator_callback:
                    candidate_outcome = self.simulator_callback(candidate)
                else:
                    # If no simulator, must be provided externally
                    continue
                
                # Check if verdict flipped
                # Original verdict based on original input evaluation
                try:
                   original_rule_res = rule.evaluate(original_input)
                except KeyError:
                   continue

                original_verdict = "Pass" if original_rule_res else "Fail"
                candidate_verdict = "Pass" if rule_holds else "Fail"
                
                if original_verdict != candidate_verdict:
                    # Found counterfactual!
                    perturbation = {
                        k: candidate[k] - original_input[k]
                        for k in original_input.keys()
                    }
                    
                    return CounterfactualPair(
                        original_input=original_input,
                        original_outcome=original_outcome,
                        counterfactual_input=candidate,
                        counterfactual_outcome=candidate_outcome,
                        perturbation=perturbation
                    )
        
        return None  # No counterfactual found
    
    def _generate_L1_candidates(
        self,
        center: Dict[str, float],
        radius: float,
        bounds: Dict[str, Tuple[float, float]],
        num_samples: int = 100
    ) -> List[Dict[str, float]]:
        """Generate candidates within L1 ball."""
        candidates = []
        vars_list = list(center.keys())
        
        for _ in range(num_samples):
            # Distributed radius among variables
            perturbations = np.random.dirichlet(np.ones(len(vars_list))) * radius
            signs = np.random.choice([-1, 1], size=len(vars_list))
            
            candidate = center.copy()
            for i, var in enumerate(vars_list):
                delta = perturbations[i] * signs[i]
                val = center[var] + delta
                
                # Clip to bounds
                if var in bounds:
                    min_val, max_val = bounds[var]
                    val = max(min_val, min(val, max_val))
                
                candidate[var] = float(val)
            candidates.append(candidate)
            
        return candidates
