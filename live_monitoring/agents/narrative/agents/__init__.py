"""
🤖 SPECIALIZED NARRATIVE AGENTS
===============================
Each agent focuses on a specific domain for deep research.
"""

from .base_agent import BaseNarrativeAgent, AgentResult
from .fed_agent import FedNarrativeAgent
from .trump_agent import TrumpNarrativeAgent
from .institutional_agent import InstitutionalNarrativeAgent
from .macro_agent import MacroNarrativeAgent
from .technical_agent import TechnicalNarrativeAgent

__all__ = [
    'BaseNarrativeAgent',
    'AgentResult',
    'FedNarrativeAgent',
    'TrumpNarrativeAgent',
    'InstitutionalNarrativeAgent',
    'MacroNarrativeAgent',
    'TechnicalNarrativeAgent',
]

