"""
🔍 Dynamic Query Generator - Learns What Works
==============================================
Generates queries based on learned performance, not hardcoded strings.
"""

import logging
from datetime import datetime
from typing import List
from .database import FedOfficialsDatabase

logger = logging.getLogger(__name__)


class QueryGenerator:
    """Generates queries dynamically based on learned performance."""
    
    # Base query templates (seed data, will be improved by learning)
    BASE_TEMPLATES = [
        "What did {official} say about interest rates {timeframe}?",
        "Recent comments from {official} on rate cuts or hikes {timeframe}",
        "{official} statements on monetary policy {timeframe}",
        "Fed {official} speeches about inflation and rates {timeframe}",
        "What are {official}'s views on the economy {timeframe}?",
    ]
    
    def __init__(self, database: FedOfficialsDatabase):
        self.db = database
    
    def generate_queries(self, officials: List[str], timeframe: str = "today") -> List[str]:
        """
        Generate queries for given officials.
        
        Uses learned performance to prioritize best templates.
        """
        # Get best-performing templates
        best_templates = self.db.get_best_queries(limit=10)
        
        # If we don't have learned templates yet, use base templates
        if not best_templates:
            templates = self.BASE_TEMPLATES
        else:
            # Mix learned + base (70% learned, 30% base for exploration)
            templates = best_templates[:3] + self.BASE_TEMPLATES[:2]
        
        queries = []
        for official in officials[:5]:  # Limit to top 5 officials
            for template in templates[:3]:  # Top 3 templates per official
                query = template.format(
                    official=official,
                    timeframe=timeframe
                )
                queries.append(query)
        
        logger.debug(f"Generated {len(queries)} queries for {len(officials)} officials")
        return queries
    
    def record_result(self, query_template: str, success: bool, comments_found: int):
        """Record query performance for learning."""
        self.db.track_query_performance(query_template, success, comments_found)


