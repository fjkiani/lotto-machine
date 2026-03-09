"""
Kill Chain — Data Models

Dataclasses for mismatch alerts and intelligence reports.
Extracted from kill_chain_engine.py for modularity.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List


@dataclass
class MismatchAlert:
    """A detected mismatch between public and institutional positioning."""
    severity: str = "GREEN"  # GREEN / YELLOW / RED
    title: str = ""
    description: str = ""
    signals: List[str] = field(default_factory=list)
    timestamp: str = ""


@dataclass
class KillChainReport:
    """Complete kill chain intelligence report."""
    # Layer data
    fedwatch: Optional[Dict] = None
    dark_pool: Optional[Dict] = None
    cot: Optional[Dict] = None
    gex: Optional[Dict] = None
    sec_13f: Optional[Dict] = None
    # Analysis
    alert_level: str = "GREEN"
    mismatches: List[MismatchAlert] = field(default_factory=list)
    narrative: str = ""
    # Metadata
    timestamp: str = ""
    layers_active: int = 0
    layers_failed: List[str] = field(default_factory=list)
