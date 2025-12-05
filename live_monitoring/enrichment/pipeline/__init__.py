"""
Market Narrative Pipeline Components

Modular, swappable components for building market narratives.
Each component has a single responsibility and can be tuned independently.
"""

from .perplexity_adapter import (
    build_perplexity_queries,
    run_perplexity_queries,
    NarrativeSource,
)

__all__ = [
    "build_perplexity_queries",
    "run_perplexity_queries",
    "NarrativeSource",
]

