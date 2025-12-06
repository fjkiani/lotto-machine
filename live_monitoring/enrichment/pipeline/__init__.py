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
from .tavily_enhancer import enhance_with_tavily

__all__ = [
    "build_perplexity_queries",
    "run_perplexity_queries",
    "NarrativeSource",
    "enhance_with_tavily",
]

