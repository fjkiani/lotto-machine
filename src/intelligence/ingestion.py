"""
Continuous Ingestion Layer
Implements Alpha's blueprint for continuous polling

Features:
- Continuous polling (every 15-30 seconds) for all sources
- Every event gets: Ticker, Time (to the second), Source/Type, Headline or Transaction data
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import deque

logger = logging.getLogger(__name__)

class ContinuousIngestion:
    """
    Continuous ingestion layer for real-time data
    
    Implements Alpha's blueprint:
    - Continuous polling (every 15-30 seconds) for all sources
    - Every event gets: Ticker, Time (to the second), Source/Type, Headline or Transaction data
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # Polling configuration
        self.polling_interval = config.get('polling_interval', 20)  # seconds
        self.max_events_per_cycle = config.get('max_events_per_cycle', 1000)
        
        # Event storage
        self.event_buffer = deque(maxlen=10000)  # Keep last 10k events
        self.last_poll_times = {}  # Track last poll time per source
        
        # Source configuration
        self.sources = config.get('sources', {
            'news': {'enabled': True, 'interval': 30},
            'market': {'enabled': True, 'interval': 15},
            'options': {'enabled': True, 'interval': 20},
            'social': {'enabled': True, 'interval': 45}
        })
        
        logger.info("ContinuousIngestion initialized - ready for relentless polling")
    
    async def initialize(self):
        """Initialize ingestion layer"""
        try:
            # Initialize source timers
            for source_name in self.sources.keys():
                self.last_poll_times[source_name] = datetime.now() - timedelta(seconds=60)
            
            logger.info("ContinuousIngestion initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing ContinuousIngestion: {e}")
    
    async def cleanup(self):
        """Cleanup resources"""
        pass
    
    async def ingest_events(self, source_name: str, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Ingest events from a source
        
        Every event gets:
        - Ticker
        - Time (to the second)
        - Source/Type
        - Headline or Transaction data (raw text)
        """
        try:
            ingested_events = []
            current_time = datetime.now()
            
            for event_data in events:
                # Standardize event format
                standardized_event = self._standardize_event(event_data, source_name, current_time)
                
                if standardized_event:
                    # Add to buffer
                    self.event_buffer.append(standardized_event)
                    ingested_events.append(standardized_event)
            
            # Update last poll time
            self.last_poll_times[source_name] = current_time
            
            logger.debug(f"Ingested {len(ingested_events)} events from {source_name}")
            return ingested_events
            
        except Exception as e:
            logger.error(f"Error ingesting events from {source_name}: {e}")
            return []
    
    def _standardize_event(self, event_data: Dict[str, Any], source_name: str, timestamp: datetime) -> Optional[Dict[str, Any]]:
        """Standardize event format"""
        try:
            # Extract ticker
            ticker = self._extract_ticker(event_data)
            
            # Extract event type
            event_type = self._extract_event_type(event_data, source_name)
            
            # Extract raw text
            raw_text = self._extract_raw_text(event_data)
            
            # Create standardized event
            standardized_event = {
                'ticker': ticker,
                'timestamp': timestamp.isoformat(),
                'source': source_name,
                'event_type': event_type,
                'data': event_data,
                'raw_text': raw_text,
                'ingested_at': timestamp.isoformat()
            }
            
            return standardized_event
            
        except Exception as e:
            logger.error(f"Error standardizing event: {e}")
            return None
    
    def _extract_ticker(self, event_data: Dict[str, Any]) -> str:
        """Extract ticker from event data"""
        try:
            # Try direct ticker field
            if 'ticker' in event_data:
                return event_data['ticker'].upper()
            
            # Try symbol field
            if 'symbol' in event_data:
                return event_data['symbol'].upper()
            
            # Extract from text
            text = str(event_data.get('text', '')) + str(event_data.get('headline', '')) + str(event_data.get('title', ''))
            
            # Look for $SYMBOL pattern
            import re
            ticker_match = re.search(r'\$([A-Z]{1,5})', text)
            if ticker_match:
                return ticker_match.group(1)
            
            # Look for common tickers
            common_tickers = ['SPY', 'QQQ', 'IWM', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA']
            for ticker in common_tickers:
                if ticker in text.upper():
                    return ticker
            
            return 'MARKET'
            
        except Exception as e:
            logger.error(f"Error extracting ticker: {e}")
            return 'MARKET'
    
    def _extract_event_type(self, event_data: Dict[str, Any], source_name: str) -> str:
        """Extract event type from event data"""
        try:
            # Try direct type field
            if 'event_type' in event_data:
                return event_data['event_type']
            
            if 'type' in event_data:
                return event_data['type']
            
            # Infer from source
            source_type_map = {
                'tavily': 'news',
                'rss': 'news',
                'twitter': 'news',
                'broker': 'trade',
                'yahoo': 'quote',
                'barchart': 'options',
                'tradingview': 'options',
                'reddit': 'social'
            }
            
            return source_type_map.get(source_name, 'unknown')
            
        except Exception as e:
            logger.error(f"Error extracting event type: {e}")
            return 'unknown'
    
    def _extract_raw_text(self, event_data: Dict[str, Any]) -> str:
        """Extract raw text from event data"""
        try:
            # Try different text fields
            text_fields = ['text', 'headline', 'title', 'content', 'summary', 'description']
            
            for field in text_fields:
                if field in event_data and event_data[field]:
                    return str(event_data[field])[:500]  # Limit to 500 chars
            
            # Fallback to string representation
            return str(event_data)[:500]
            
        except Exception as e:
            logger.error(f"Error extracting raw text: {e}")
            return str(event_data)[:500]
    
    def get_recent_events(self, minutes: int = 10) -> List[Dict[str, Any]]:
        """Get recent events from buffer"""
        try:
            cutoff_time = datetime.now() - timedelta(minutes=minutes)
            
            recent_events = []
            for event in self.event_buffer:
                event_time = datetime.fromisoformat(event['timestamp'])
                if event_time >= cutoff_time:
                    recent_events.append(event)
            
            return recent_events
            
        except Exception as e:
            logger.error(f"Error getting recent events: {e}")
            return []
    
    def get_events_by_ticker(self, ticker: str, minutes: int = 10) -> List[Dict[str, Any]]:
        """Get recent events for specific ticker"""
        try:
            recent_events = self.get_recent_events(minutes)
            return [event for event in recent_events if event['ticker'] == ticker]
            
        except Exception as e:
            logger.error(f"Error getting events by ticker: {e}")
            return []
    
    def get_events_by_type(self, event_type: str, minutes: int = 10) -> List[Dict[str, Any]]:
        """Get recent events of specific type"""
        try:
            recent_events = self.get_recent_events(minutes)
            return [event for event in recent_events if event['event_type'] == event_type]
            
        except Exception as e:
            logger.error(f"Error getting events by type: {e}")
            return []
    
    def get_ingestion_stats(self) -> Dict[str, Any]:
        """Get ingestion statistics"""
        try:
            total_events = len(self.event_buffer)
            
            # Count by source
            source_counts = {}
            for event in self.event_buffer:
                source = event['source']
                source_counts[source] = source_counts.get(source, 0) + 1
            
            # Count by type
            type_counts = {}
            for event in self.event_buffer:
                event_type = event['event_type']
                type_counts[event_type] = type_counts.get(event_type, 0) + 1
            
            # Count by ticker
            ticker_counts = {}
            for event in self.event_buffer:
                ticker = event['ticker']
                ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1
            
            return {
                'total_events': total_events,
                'source_counts': source_counts,
                'type_counts': type_counts,
                'ticker_counts': ticker_counts,
                'last_poll_times': {k: v.isoformat() for k, v in self.last_poll_times.items()},
                'buffer_size': self.event_buffer.maxlen
            }
            
        except Exception as e:
            logger.error(f"Error getting ingestion stats: {e}")
            return {}
    
    def should_poll_source(self, source_name: str) -> bool:
        """Check if source should be polled based on interval"""
        try:
            if source_name not in self.sources:
                return False
            
            source_config = self.sources[source_name]
            if not source_config.get('enabled', True):
                return False
            
            last_poll = self.last_poll_times.get(source_name)
            if not last_poll:
                return True
            
            interval_seconds = source_config.get('interval', self.polling_interval)
            time_since_last_poll = (datetime.now() - last_poll).total_seconds()
            
            return time_since_last_poll >= interval_seconds
            
        except Exception as e:
            logger.error(f"Error checking poll status for {source_name}: {e}")
            return False



