"""
Event Loader

Fetches and parses economic calendar events.
Isolates macro event logic from the main pipeline.
"""
import logging
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


def load_economic_events(symbol: str, date: str) -> List[Dict[str, Any]]:
    """
    Load economic calendar events for a given date.
    
    Args:
        symbol: Ticker symbol (used for logging)
        date: Date string in 'YYYY-MM-DD' format
        
    Returns:
        List of event dictionaries
    """
    try:
        from live_monitoring.enrichment.apis.event_loader import EventLoader
        
        loader = EventLoader()
        events_dict = loader.load_events(date)
        
        # EventLoader returns a dict with "macro_events" key
        if isinstance(events_dict, dict):
            return events_dict
        
        logger.info("📅 Loaded events for %s", date)
        return {"macro_events": events_dict if isinstance(events_dict, list) else []}
        
    except Exception as e:
        logger.error("Error loading events for %s: %s", date, e)
        return []


def extract_macro_data(event_schedule: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Extract macro data points from economic events.
    
    Looks for PMI misses, consumer sentiment, etc.
    
    Args:
        event_schedule: List of event dictionaries
        
    Returns:
        Dictionary with macro data points:
        - pmi_services_miss: bool
        - pmi_manufacturing_miss: bool
        - consumer_sentiment: float or None
    """
    data = {
        "pmi_services_miss": False,
        "pmi_manufacturing_miss": False,
        "consumer_sentiment": None,
    }
    
    for event in event_schedule:
        title = event.get("title", "").lower()
        
        # Check for PMI misses
        if 'pmi' in title or 's&p global' in title:
            actual = event.get('actual')
            forecast = event.get('forecast')
            
            if actual is not None and forecast is not None:
                try:
                    if float(actual) < float(forecast):
                        if 'services' in title or 'service' in title:
                            data['pmi_services_miss'] = True
                        elif 'manufacturing' in title or 'manufact' in title:
                            data['pmi_manufacturing_miss'] = True
                except (ValueError, TypeError):
                    pass
        
        # Consumer sentiment
        if 'consumer sentiment' in title or 'michigan' in title:
            actual = event.get('actual')
            if actual is not None:
                try:
                    data['consumer_sentiment'] = float(actual)
                except (ValueError, TypeError):
                    pass
    
    return data

