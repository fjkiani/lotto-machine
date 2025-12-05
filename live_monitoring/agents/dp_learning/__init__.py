"""
🧠 DARK POOL LEARNING ENGINE
============================
Learns from historical dark pool interactions to predict bounce vs break.

Components:
- models.py: Data contracts
- database.py: SQLite persistence  
- tracker.py: Outcome tracking
- learner.py: Pattern learning
- engine.py: Main orchestrator
"""

from .engine import DPLearningEngine
from .models import DPInteraction, DPOutcome, DPPattern

__all__ = ['DPLearningEngine', 'DPInteraction', 'DPOutcome', 'DPPattern']

