"""
🎤 Fed Officials Intelligence - MODULAR & DYNAMIC
==================================================
Data-driven Fed monitoring that learns from patterns.

Architecture:
- models.py: Data contracts
- database.py: Persistent storage + pattern learning
- query_generator.py: Dynamic query generation (learns what works)
- sentiment_analyzer.py: LLM-based sentiment (not keyword matching)
- official_tracker.py: Dynamically track officials
- impact_learner.py: Learn market impact from actual price moves
- engine.py: Main orchestrator
"""

from .engine import FedOfficialsEngine

__all__ = ['FedOfficialsEngine']



