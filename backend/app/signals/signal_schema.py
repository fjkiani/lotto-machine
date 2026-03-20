from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime

@dataclass
class SignalResult:
    """
    Standardized payload for all Kill Shots signal modules.
    Ensures frontend (Phase 3 Pillars) receives clean, explicit data mappings.
    """
    name: str # e.g. "GEX", "COT", "BRAIN", "FED_DP"
    slug: str # e.g. "gex-extreme-negative-2026-03-19"
    boost: int # The numerical contribution to the divergence (0-3)
    active: bool # Whether the signal is actively armed
    
    # Traceability
    timestamp: str 
    source_date: str 
    
    # Specific Layer Data (Must map explicitly, no assumed UI fields)
    raw: Dict[str, Any] = field(default_factory=dict)
    
    # LLM or deterministic explanation
    explanation: str = ""
    reasons: List[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "name": self.name,
            "slug": self.slug,
            "boost": self.boost,
            "active": self.active,
            "timestamp": self.timestamp,
            "source_date": self.source_date,
            "raw": self.raw,
            "explanation": self.explanation,
            "reasons": self.reasons
        }
