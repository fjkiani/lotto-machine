"""
👥 Dynamic Official Tracker - Discovers Officials from Data
============================================================
NOT hardcoded! Learns officials from news mentions.
"""

import logging
import re
from datetime import datetime
from typing import List, Optional
from .models import FedOfficial, FedPosition
from .database import FedOfficialsDatabase

logger = logging.getLogger(__name__)


class OfficialTracker:
    """Dynamically discovers and tracks Fed officials."""
    
    # Common Fed titles (for discovery)
    FED_TITLES = [
        "fed chair", "chairman", "federal reserve chair",
        "vice chair", "governor", "fed president",
        "fomc member", "regional fed president"
    ]
    
    def __init__(self, database: FedOfficialsDatabase):
        self.db = database
    
    def discover_from_text(self, text: str) -> List[str]:
        """
        Discover Fed official names from text.
        Returns list of official names found.
        """
        # Load known officials from database
        known_officials = {o.name.lower(): o.name for o in self.db.get_officials()}
        
        found = []
        text_lower = text.lower()
        
        # Check for known officials
        for lower_name, real_name in known_officials.items():
            if lower_name in text_lower:
                found.append(real_name)
        
        # Try to discover new officials (look for "Name, Fed Title" pattern)
        # Exclude common place names
        place_names = {'new york', 'san francisco', 'chicago', 'atlanta', 'cleveland', 'st louis', 'minneapolis'}
        
        patterns = [
            r'([A-Z][a-z]+ [A-Z][a-z]+),?\s+(?:Federal Reserve|Fed|FOMC)',
            r'Fed (?:Chair|Governor|President) ([A-Z][a-z]+ [A-Z][a-z]+)',
            r'([A-Z][a-z]+ [A-Z][a-z]+)\s+(?:said|stated|commented|noted|indicated)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                # Skip if it's a place name
                if match.lower() in place_names:
                    continue
                
                # Skip if it's already found or known
                if match not in found and match not in [o.name for o in self.db.get_officials()]:
                    # Validate: should be a person's name (2 words, both capitalized)
                    words = match.split()
                    if len(words) == 2 and all(w[0].isupper() for w in words):
                        # New official discovered!
                        logger.info(f"🔍 Discovered new official: {match}")
                        self._create_official(match, text)
                        found.append(match)
        
        return found
    
    def _create_official(self, name: str, context: str):
        """Create a new official entry from discovery."""
        # Try to infer position from context
        position = None
        context_lower = context.lower()
        
        if "chair" in context_lower and "vice" not in context_lower:
            from .models import FedPosition
            position = FedPosition.CHAIR
        elif "vice chair" in context_lower:
            from .models import FedPosition
            position = FedPosition.VICE_CHAIR
        elif "governor" in context_lower:
            from .models import FedPosition
            position = FedPosition.GOVERNOR
        elif "president" in context_lower:
            from .models import FedPosition
            position = FedPosition.REGIONAL_PRESIDENT
        
        official = FedOfficial(
            name=name,
            position=position,
            voting_member=True,  # Assume yes until we learn otherwise
            first_seen=datetime.now(),
            last_seen=datetime.now(),
            comment_frequency=1,
        )
        
        self.db.update_official(official)
    
    def update_official_stats(self, official_name: str):
        """Update official's stats after finding a comment."""
        officials = self.db.get_officials()
        for official in officials:
            if official.name == official_name:
                official.comment_frequency += 1
                official.last_seen = datetime.now()
                self.db.update_official(official)
                break

