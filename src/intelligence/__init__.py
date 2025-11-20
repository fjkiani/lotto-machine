"""
Multi-Source Intelligence Gathering System
Cross-references and pattern-matches across dozens of public sources
"""

from .aggregator import IntelligenceAggregator
from .sources import (
    NewsSourceScraper,
    BlockTradeScraper,
    DarkPoolScraper,
    OptionActivityScraper,
    SocialSentimentScraper,
    TechnicalDataScraper
)
from .correlator import IntelligenceCorrelator
from .synthesizer import IntelligenceSynthesizer

__all__ = [
    'IntelligenceAggregator',
    'NewsSourceScraper',
    'BlockTradeScraper',
    'DarkPoolScraper',
    'OptionActivityScraper',
    'SocialSentimentScraper',
    'TechnicalDataScraper',
    'IntelligenceCorrelator',
    'IntelligenceSynthesizer'
]
