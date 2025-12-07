"""
📊 Economic Data Fetcher
========================
Integrates Alpha Vantage economic data with our calendar events.

Maps calendar events → Alpha Vantage indicators → actual/previous values → sentiment.

Usage:
    fetcher = EconomicDataFetcher()
    release = fetcher.get_release_for_event("Nonfarm Payrolls")
    sentiment = fetcher.get_economic_sentiment()
"""

import os
import logging
from dataclasses import dataclass
from datetime import datetime, date
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Import Alpha Vantage client
try:
    from live_monitoring.enrichment.apis.alpha_vantage_econ import AlphaVantageEcon, EconomicRelease
except ImportError:
    from alpha_vantage_econ import AlphaVantageEcon, EconomicRelease


@dataclass
class EventSentiment:
    """Economic event sentiment analysis."""
    event_name: str
    sentiment: str  # HAWKISH / DOVISH / NEUTRAL
    reasoning: str
    latest_value: float
    previous_value: Optional[float]
    change_pct: Optional[float]
    release_date: str


class EconomicDataFetcher:
    """
    Fetches economic data and calculates sentiment.
    
    Maps calendar event names to Alpha Vantage indicators.
    """
    
    # Map calendar event names → Alpha Vantage indicator keys
    EVENT_TO_INDICATOR = {
        # Employment
        "Nonfarm Payrolls": "NFP",
        "NFP": "NFP",
        "Nonfarm Payroll": "NFP",
        "Non-Farm Payrolls": "NFP",
        "Unemployment Rate": "UNEMPLOYMENT",
        "Unemployment": "UNEMPLOYMENT",
        "Jobless Claims": "UNEMPLOYMENT",  # Proxy
        
        # Inflation
        "CPI": "CPI",
        "Consumer Price Index": "CPI",
        "Core CPI": "CPI",
        "PCE": "INFLATION",  # Use inflation as proxy
        "Inflation": "INFLATION",
        
        # Interest Rates
        "Federal Funds Rate": "FED_FUNDS_RATE",
        "Fed Rate": "FED_FUNDS_RATE",
        "FOMC": "FED_FUNDS_RATE",
        
        # Growth
        "GDP": "REAL_GDP",
        "Real GDP": "REAL_GDP",
        "GDP Growth": "REAL_GDP",
        
        # Other
        "Retail Sales": "RETAIL_SALES",
        "Durable Goods": "DURABLES",
        "Durable Goods Orders": "DURABLES",
        "Treasury Yield": "TREASURY_10Y",
    }
    
    # Sentiment rules: indicator → (higher_is_hawkish, threshold)
    SENTIMENT_RULES = {
        # Jobs: Better jobs = HAWKISH (less cuts needed)
        "NFP": (True, 0.5),  # Higher NFP = HAWKISH
        "UNEMPLOYMENT": (False, 0.5),  # Higher unemployment = DOVISH
        
        # Inflation: Higher inflation = HAWKISH (need to fight it)
        "CPI": (True, 0.3),
        "INFLATION": (True, 0.3),
        
        # Rates: Higher rates = HAWKISH
        "FED_FUNDS_RATE": (True, 0.1),
        
        # Growth: Higher GDP = HAWKISH (economy strong)
        "REAL_GDP": (True, 0.5),
        
        # Consumer: Higher sales = HAWKISH
        "RETAIL_SALES": (True, 1.0),
        "DURABLES": (True, 1.0),
        
        # Yields: Higher yields = HAWKISH
        "TREASURY_10Y": (True, 0.1),
    }
    
    def __init__(self, api_key: Optional[str] = None):
        self.client = AlphaVantageEcon(api_key=api_key)
        self._last_sentiment: Optional[EventSentiment] = None
    
    def get_indicator_for_event(self, event_name: str) -> Optional[str]:
        """Map a calendar event name to Alpha Vantage indicator key."""
        # Direct match
        if event_name in self.EVENT_TO_INDICATOR:
            return self.EVENT_TO_INDICATOR[event_name]
        
        # Fuzzy match
        event_lower = event_name.lower()
        for key, indicator in self.EVENT_TO_INDICATOR.items():
            if key.lower() in event_lower or event_lower in key.lower():
                return indicator
        
        return None
    
    def get_release_for_event(self, event_name: str) -> Optional[EconomicRelease]:
        """Get the latest release data for a calendar event."""
        indicator_key = self.get_indicator_for_event(event_name)
        if not indicator_key:
            logger.debug(f"No indicator mapping for event: {event_name}")
            return None
        
        return self.client._get_indicator(indicator_key)
    
    def calculate_sentiment(self, release: EconomicRelease) -> EventSentiment:
        """
        Calculate economic sentiment from a release.
        
        Logic:
        - Jobs UP → HAWKISH (Fed won't cut as much)
        - Jobs DOWN → DOVISH (Fed will cut more)
        - Inflation UP → HAWKISH (Fed fights inflation)
        - Inflation DOWN → DOVISH (Fed can ease)
        """
        indicator = release.name
        
        # Get rules
        higher_is_hawkish, threshold = self.SENTIMENT_RULES.get(
            indicator, (True, 0.5)
        )
        
        # Determine sentiment
        sentiment = "NEUTRAL"
        reasoning = f"{release.name} unchanged"
        
        if release.change is not None:
            abs_change = abs(release.change)
            
            if abs_change > threshold:
                if release.change > 0:
                    sentiment = "HAWKISH" if higher_is_hawkish else "DOVISH"
                else:
                    sentiment = "DOVISH" if higher_is_hawkish else "HAWKISH"
                
                direction = "rose" if release.change > 0 else "fell"
                reasoning = f"{release.name} {direction} {abs_change:.1f}%"
        
        return EventSentiment(
            event_name=release.name,
            sentiment=sentiment,
            reasoning=reasoning,
            latest_value=release.value,
            previous_value=release.previous,
            change_pct=release.change,
            release_date=release.date,
        )
    
    def get_sentiment_for_event(self, event_name: str) -> Optional[EventSentiment]:
        """Get sentiment for a specific calendar event."""
        release = self.get_release_for_event(event_name)
        if not release:
            return None
        
        sentiment = self.calculate_sentiment(release)
        self._last_sentiment = sentiment
        return sentiment
    
    def get_overall_economic_sentiment(self) -> str:
        """
        Get overall economic sentiment from key indicators.
        
        Returns: HAWKISH / DOVISH / NEUTRAL
        """
        key_indicators = ["NFP", "CPI", "UNEMPLOYMENT", "FED_FUNDS_RATE"]
        
        hawkish_count = 0
        dovish_count = 0
        
        for indicator in key_indicators:
            release = self.client._get_indicator(indicator)
            if release:
                sentiment = self.calculate_sentiment(release)
                if sentiment.sentiment == "HAWKISH":
                    hawkish_count += 1
                elif sentiment.sentiment == "DOVISH":
                    dovish_count += 1
        
        if hawkish_count > dovish_count:
            return "HAWKISH"
        elif dovish_count > hawkish_count:
            return "DOVISH"
        return "NEUTRAL"
    
    def get_summary(self) -> Dict:
        """Get a summary of all key economic indicators."""
        indicators = self.client.get_market_moving()
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "indicators": {},
            "overall_sentiment": "NEUTRAL",
        }
        
        hawkish = 0
        dovish = 0
        
        for name, release in indicators.items():
            sentiment = self.calculate_sentiment(release)
            summary["indicators"][name] = {
                "value": release.value,
                "date": release.date,
                "change": release.change,
                "sentiment": sentiment.sentiment,
            }
            
            if sentiment.sentiment == "HAWKISH":
                hawkish += 1
            elif sentiment.sentiment == "DOVISH":
                dovish += 1
        
        summary["overall_sentiment"] = (
            "HAWKISH" if hawkish > dovish 
            else "DOVISH" if dovish > hawkish 
            else "NEUTRAL"
        )
        
        return summary


# Quick test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    fetcher = EconomicDataFetcher()
    
    print("=" * 60)
    print("📊 ECONOMIC DATA + SENTIMENT")
    print("=" * 60)
    print()
    
    # Test event lookups
    events = ["Nonfarm Payrolls", "CPI", "Unemployment Rate", "Federal Funds Rate"]
    
    for event in events:
        sentiment = fetcher.get_sentiment_for_event(event)
        if sentiment:
            icon = "🔴" if sentiment.sentiment == "HAWKISH" else "🟢" if sentiment.sentiment == "DOVISH" else "⚪"
            print(f"{icon} {event}:")
            print(f"   Value: {sentiment.latest_value} → {sentiment.sentiment}")
            print(f"   Reason: {sentiment.reasoning}")
            print()
    
    print("-" * 60)
    print(f"Overall Economic Sentiment: {fetcher.get_overall_economic_sentiment()}")


