"""
CBF Kit Data Integration (Group A Deliverables).

Provides data loading utilities and metadata for CBFKIT simulation datasets.
Supports unicycle systems with static and dynamic obstacles, using both
legacy (nominal) and evolved (CBF-based safe) controllers.
"""

from cbf_data.adapter import cbf_to_semantic, semantic_to_cbf

__all__ = [
    "cbf_to_semantic",
    "semantic_to_cbf",
]
