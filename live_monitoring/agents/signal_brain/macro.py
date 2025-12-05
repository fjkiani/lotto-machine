"""
🧠 Signal Brain - Macro Context Provider
=========================================
Aggregates ALL macro data sources into one unified context.

NO MORE HARDCODED VALUES!

Data Sources:
1. Fed Watch Monitor - CME rate cut probabilities
2. Fed Officials Monitor - Hawkish/dovish comments
3. Economic Calendar - Recent events (NFP, CPI, etc.)
4. Economic Learning Engine - Pattern-based predictions
5. Trump News Monitor - Policy risk level

Output: MacroContext with real, live data
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


@dataclass
class EconomicEvent:
    """Recent economic event data."""
    name: str = ""  # NFP, CPI, PPI, etc.
    timestamp: datetime = field(default_factory=datetime.now)
    actual: Optional[float] = None
    forecast: Optional[float] = None
    previous: Optional[float] = None
    surprise_pct: float = 0.0  # (actual - forecast) / forecast
    importance: str = "MEDIUM"  # HIGH/MEDIUM/LOW
    market_impact: str = "NEUTRAL"  # BULLISH/BEARISH/NEUTRAL


@dataclass
class MacroContext:
    """
    Unified macro context from ALL data sources.
    This replaces hardcoded fed_sentiment and trump_risk!
    """
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Fed Watch (CME)
    fed_cut_probability: float = 50.0  # 0-100%
    fed_hold_probability: float = 50.0  # 0-100%
    fed_sentiment: str = "NEUTRAL"  # HAWKISH/DOVISH/NEUTRAL
    fed_source: str = "DEFAULT"  # CME/PERPLEXITY/DEFAULT
    
    # Economic Events
    recent_event: Optional[EconomicEvent] = None
    economic_sentiment: str = "NEUTRAL"  # Based on recent releases
    today_has_high_impact_event: bool = False  # NFP, CPI, etc today?
    event_name: str = ""  # Name of today's event
    event_time: str = ""  # Time of today's event (e.g., "08:30")
    
    # Fed Officials
    fed_official_latest: str = ""  # Most recent comment
    fed_official_sentiment: str = "NEUTRAL"  # HAWKISH/DOVISH/NEUTRAL
    fed_official_name: str = ""  # Powell, Waller, etc.
    
    # Trump
    trump_risk: str = "LOW"  # HIGH/MEDIUM/LOW
    trump_latest: str = ""  # Latest headline
    
    # Synthesis
    overall_bias: str = "NEUTRAL"  # BULLISH/BEARISH/NEUTRAL
    confidence: float = 0.5  # 0-1
    reasoning: str = ""
    
    def to_signal_brain_args(self) -> Dict[str, str]:
        """
        Convert to Signal Brain analyze() arguments.
        Replaces the hardcoded fed_sentiment and trump_risk!
        """
        return {
            'fed_sentiment': self.fed_sentiment,
            'trump_risk': self.trump_risk,
        }


class MacroContextProvider:
    """
    Aggregates all macro data sources.
    
    Usage:
        provider = MacroContextProvider(
            fed_watch=fed_watch_monitor,
            fed_officials=fed_officials_monitor,
            economic_engine=economic_learning_engine,
            trump_monitor=trump_pulse,
        )
        
        context = provider.get_context()
        # Now use context.fed_sentiment, context.trump_risk (REAL DATA!)
    """
    
    def __init__(
        self,
        fed_watch=None,
        fed_officials=None,
        economic_engine=None,
        economic_calendar=None,
        trump_monitor=None,
    ):
        """
        Initialize with existing monitor instances.
        Pass None for any monitor you don't have.
        """
        self.fed_watch = fed_watch
        self.fed_officials = fed_officials
        self.economic_engine = economic_engine
        self.economic_calendar = economic_calendar
        self.trump_monitor = trump_monitor
        
        # Cache
        self._cache: Optional[MacroContext] = None
        self._cache_time: Optional[datetime] = None
        self._cache_duration = timedelta(seconds=60)  # 1 minute cache
    
    def get_context(self, use_cache: bool = True) -> MacroContext:
        """
        Get unified macro context from all sources.
        
        Args:
            use_cache: Use cached data if available (default: True)
        
        Returns:
            MacroContext with real data from all sources
        """
        # Check cache
        if use_cache and self._cache and self._cache_time:
            if datetime.now() - self._cache_time < self._cache_duration:
                return self._cache
        
        context = MacroContext()
        
        # 1. Fed Watch (CME rate probabilities)
        self._load_fed_watch(context)
        
        # 2. Economic Events (NFP, CPI, etc.)
        self._load_economic_events(context)
        
        # 3. Fed Officials (hawkish/dovish comments)
        self._load_fed_officials(context)
        
        # 4. Trump Risk
        self._load_trump_risk(context)
        
        # 5. Synthesize overall bias
        self._synthesize_bias(context)
        
        # Cache result
        self._cache = context
        self._cache_time = datetime.now()
        
        return context
    
    def _load_fed_watch(self, context: MacroContext):
        """Load Fed Watch data (CME rate cut probabilities)."""
        if not self.fed_watch:
            logger.debug("Fed Watch not available")
            return
        
        try:
            # Get latest status from Fed Watch monitor
            # FedWatchStatus has: prob_cut, prob_hold, prob_hike, market_bias
            status = None
            
            # Try different methods
            if hasattr(self.fed_watch, 'get_current_status'):
                status = self.fed_watch.get_current_status()
            elif hasattr(self.fed_watch, 'get_status'):
                status = self.fed_watch.get_status()
            elif hasattr(self.fed_watch, 'prev_status'):
                status = self.fed_watch.prev_status
            
            if status:
                # FedWatchStatus is a dataclass, access attributes directly
                if hasattr(status, 'prob_cut'):
                    context.fed_cut_probability = status.prob_cut
                    context.fed_hold_probability = status.prob_hold
                    context.fed_source = "CME"
                elif isinstance(status, dict):
                    context.fed_cut_probability = status.get('cut_probability', status.get('prob_cut', 50))
                    context.fed_hold_probability = status.get('hold_probability', status.get('prob_hold', 50))
                    context.fed_source = "CME"
                
                # Determine sentiment from probabilities
                if context.fed_cut_probability > 70:
                    context.fed_sentiment = "DOVISH"  # High cut probability = dovish
                elif context.fed_cut_probability < 30:
                    context.fed_sentiment = "HAWKISH"  # Low cut probability = hawkish
                else:
                    context.fed_sentiment = "NEUTRAL"
                
                logger.info(f"📊 Fed Watch: {context.fed_cut_probability:.0f}% cut → {context.fed_sentiment}")
        except Exception as e:
            logger.warning(f"⚠️ Fed Watch load error: {e}")
    
    def _load_economic_events(self, context: MacroContext):
        """Load recent economic events (NFP, CPI, etc.) with LIVE data."""
        today_events = []
        
        # 1. Get today's events from Economic Calendar (static schedule)
        if self.economic_calendar:
            try:
                # Try both method names
                if hasattr(self.economic_calendar, 'get_today_events'):
                    today_events = self.economic_calendar.get_today_events()
                elif hasattr(self.economic_calendar, 'get_upcoming_events'):
                    # Filter to today only
                    from datetime import date
                    today_str = date.today().isoformat()
                    all_events = self.economic_calendar.get_upcoming_events(days=1)
                    today_events = [e for e in all_events if getattr(e, 'date', '') == today_str]
                
                if today_events:
                    # Find HIGH importance events
                    high_events = [
                        e for e in today_events 
                        if getattr(e, 'importance', None) and 
                        (str(getattr(e, 'importance', '')).upper() == 'HIGH' or 
                         'HIGH' in str(getattr(e, 'importance', '')))
                    ]
                    
                    if high_events:
                        event = high_events[0]
                        event_name = getattr(event, 'name', 'Unknown')
                        event_time = getattr(event, 'time', '08:30')
                        impact = getattr(event, 'typical_surprise_impact', 3.0)
                        
                        context.recent_event = EconomicEvent(
                            name=event_name,
                            importance='HIGH',
                        )
                        context.today_has_high_impact_event = True
                        context.event_name = event_name
                        context.event_time = event_time
                        
                        logger.info(f"📅 Today's HIGH Event: {event_name} @ {event_time}")
            except Exception as e:
                logger.warning(f"Economic calendar error: {e}")
        
        # 2. Try Alpha Vantage for LIVE economic data (actual values!)
        if context.event_name:
            try:
                from live_monitoring.enrichment.apis.economic_data_fetcher import EconomicDataFetcher
                av_fetcher = EconomicDataFetcher()
                
                sentiment = av_fetcher.get_sentiment_for_event(context.event_name)
                if sentiment:
                    context.economic_sentiment = sentiment.sentiment
                    context.recent_event = EconomicEvent(
                        name=context.event_name,
                        actual=sentiment.latest_value,
                        surprise_pct=sentiment.change_pct or 0,
                        importance='HIGH',
                    )
                    logger.info(f"📊 Alpha Vantage: {sentiment.event_name} → {sentiment.sentiment} ({sentiment.reasoning})")
            except Exception as e:
                logger.debug(f"Alpha Vantage error: {e}")
        
        # 3. Try Economic Learning Engine as fallback
        if self.economic_engine:
            try:
                # Check for recent predictions or events
                if hasattr(self.economic_engine, 'get_latest_event'):
                    event_data = self.economic_engine.get_latest_event()
                    if event_data:
                        context.recent_event = EconomicEvent(
                            name=event_data.get('name', 'Unknown'),
                            actual=event_data.get('actual'),
                            forecast=event_data.get('forecast'),
                            surprise_pct=event_data.get('surprise_pct', 0),
                            importance=event_data.get('importance', 'MEDIUM'),
                        )
                        
                        # Determine economic sentiment from surprise
                        self._calculate_economic_sentiment(context)
                        
                        logger.info(f"📊 Economic Data: {context.recent_event.name} → {context.economic_sentiment}")
            except Exception as e:
                logger.debug(f"Economic engine error: {e}")
        
        # 3. If we have today's event but no actual data, try to fetch from Perplexity
        if context.today_has_high_impact_event and not context.recent_event.actual:
            self._fetch_live_economic_data(context)
    
    def _calculate_economic_sentiment(self, context: MacroContext):
        """Calculate economic sentiment from event surprise."""
        if not context.recent_event or not context.recent_event.surprise_pct:
            return
        
        event_name = context.recent_event.name.upper()
        surprise = context.recent_event.surprise_pct
        
        # Jobs data: Positive surprise = HAWKISH (strong economy, less cuts)
        if 'NFP' in event_name or 'PAYROLL' in event_name or 'EMPLOYMENT' in event_name:
            if surprise > 0.5:
                context.economic_sentiment = "HAWKISH"
            elif surprise < -0.5:
                context.economic_sentiment = "DOVISH"
        # Inflation data: Higher = HAWKISH, Lower = DOVISH
        elif 'CPI' in event_name or 'PCE' in event_name or 'INFLATION' in event_name:
            if surprise > 0.1:
                context.economic_sentiment = "HAWKISH"
            elif surprise < -0.1:
                context.economic_sentiment = "DOVISH"
        # Jobless claims: LOWER is HAWKISH (strong jobs), HIGHER is DOVISH
        elif 'JOBLESS' in event_name or 'CLAIMS' in event_name:
            if surprise < -0.5:
                context.economic_sentiment = "HAWKISH"
            elif surprise > 0.5:
                context.economic_sentiment = "DOVISH"
    
    def _fetch_live_economic_data(self, context: MacroContext):
        """Try to fetch live economic data from Perplexity."""
        try:
            # Try to use Perplexity for live data
            perplexity_key = os.environ.get('PERPLEXITY_API_KEY')
            if not perplexity_key:
                return
            
            from live_monitoring.enrichment.apis.perplexity_search import PerplexitySearchClient
            client = PerplexitySearchClient(api_key=perplexity_key)
            
            event_name = context.event_name or 'NFP jobs'
            query = f"What was today's {event_name} report result? Was it above or below expectations?"
            
            result = client.search(query)
            if result and result.text:
                text = result.text.lower()
                
                # Parse sentiment from result
                if 'better than expected' in text or 'beat' in text or 'above' in text:
                    context.economic_sentiment = "HAWKISH"
                    logger.info(f"📊 Live Data: {event_name} BEAT expectations → HAWKISH")
                elif 'worse than expected' in text or 'miss' in text or 'below' in text:
                    context.economic_sentiment = "DOVISH"
                    logger.info(f"📊 Live Data: {event_name} MISSED expectations → DOVISH")
                elif 'inline' in text or 'as expected' in text or 'in line' in text:
                    context.economic_sentiment = "NEUTRAL"
                    logger.info(f"📊 Live Data: {event_name} inline → NEUTRAL")
        except Exception as e:
            logger.debug(f"Live economic data fetch error: {e}")
    
    def _load_fed_officials(self, context: MacroContext):
        """Load Fed official comments."""
        if not self.fed_officials:
            return
        
        try:
            if hasattr(self.fed_officials, 'get_latest_comment'):
                comment = self.fed_officials.get_latest_comment()
                if comment:
                    context.fed_official_latest = comment.get('text', '')[:100]
                    context.fed_official_name = comment.get('speaker', '')
                    context.fed_official_sentiment = comment.get('sentiment', 'NEUTRAL')
                    
                    logger.info(f"🏛️ Fed Official: {context.fed_official_name} → {context.fed_official_sentiment}")
            elif hasattr(self.fed_officials, 'prev_sentiment'):
                context.fed_official_sentiment = self.fed_officials.prev_sentiment or "NEUTRAL"
        except Exception as e:
            logger.debug(f"Fed officials error: {e}")
    
    def _load_trump_risk(self, context: MacroContext):
        """Load Trump policy risk."""
        if not self.trump_monitor:
            return
        
        try:
            # Try different monitor interfaces
            if hasattr(self.trump_monitor, 'get_current_situation'):
                situation = self.trump_monitor.get_current_situation()
                if situation:
                    # TrumpSituation has: total_statements_24h, sentiment_score, hot_topics
                    # Map statement count to risk level
                    stmt_count = getattr(situation, 'total_statements_24h', 0)
                    sentiment = getattr(situation, 'sentiment_score', 0.0)
                    overall_sentiment = getattr(situation, 'overall_sentiment', 'NEUTRAL')
                    
                    # High activity (5+ statements) or strongly negative sentiment = HIGH risk
                    if stmt_count >= 5 or sentiment < -0.5:
                        context.trump_risk = "HIGH"
                    elif stmt_count >= 2 or sentiment < -0.2:
                        context.trump_risk = "MEDIUM"
                    else:
                        context.trump_risk = "LOW"
                    
                    # Get latest topic
                    hot_topics = getattr(situation, 'hot_topics', [])
                    if hot_topics:
                        context.trump_latest = hot_topics[0][:50]
                    
                    # If bearish sentiment, that's additional risk
                    if overall_sentiment == "BEARISH":
                        context.trump_risk = "HIGH" if context.trump_risk != "HIGH" else "HIGH"
                    
                    logger.info(f"🇺🇸 Trump: {context.trump_risk} risk ({stmt_count} statements, sentiment={sentiment:.2f})")
            elif hasattr(self.trump_monitor, 'prev_sentiment'):
                sentiment = self.trump_monitor.prev_sentiment
                if sentiment and 'risk' in str(sentiment).lower():
                    context.trump_risk = "HIGH"
        except Exception as e:
            logger.debug(f"Trump monitor error: {e}")
    
    def _synthesize_bias(self, context: MacroContext):
        """
        Synthesize overall macro bias from all sources.
        
        Logic:
        - Fed Watch DOVISH (>70% cut) + Economic DOVISH = BULLISH for stocks
        - Fed Watch HAWKISH (<30% cut) + Economic HAWKISH = BEARISH for stocks
        - Mixed signals = NEUTRAL
        """
        bullish_count = 0
        bearish_count = 0
        total_signals = 0
        
        # Fed Watch sentiment
        if context.fed_sentiment == "DOVISH":
            bullish_count += 2  # Double weight for Fed
            total_signals += 2
        elif context.fed_sentiment == "HAWKISH":
            bearish_count += 2
            total_signals += 2
        else:
            total_signals += 2
        
        # Economic sentiment
        if context.economic_sentiment == "DOVISH":
            bullish_count += 1
            total_signals += 1
        elif context.economic_sentiment == "HAWKISH":
            bearish_count += 1
            total_signals += 1
        elif context.recent_event:
            total_signals += 1
        
        # Fed officials
        if context.fed_official_sentiment == "DOVISH":
            bullish_count += 1
            total_signals += 1
        elif context.fed_official_sentiment == "HAWKISH":
            bearish_count += 1
            total_signals += 1
        
        # Trump risk (HIGH = bearish)
        if context.trump_risk == "HIGH":
            bearish_count += 1
            total_signals += 1
        elif context.trump_risk == "LOW":
            total_signals += 1  # Neutral contribution
        
        # Calculate bias
        if total_signals > 0:
            bullish_ratio = bullish_count / total_signals
            bearish_ratio = bearish_count / total_signals
            
            if bullish_ratio > 0.5:
                context.overall_bias = "BULLISH"
            elif bearish_ratio > 0.5:
                context.overall_bias = "BEARISH"
            else:
                context.overall_bias = "NEUTRAL"
            
            context.confidence = max(bullish_ratio, bearish_ratio)
        
        # Build reasoning
        parts = []
        if context.fed_sentiment != "NEUTRAL":
            parts.append(f"Fed {context.fed_sentiment.lower()}")
        if context.recent_event:
            parts.append(f"{context.recent_event.name}")
        if context.trump_risk == "HIGH":
            parts.append("Trump risk elevated")
        
        context.reasoning = ", ".join(parts) if parts else "No significant macro signals"
        
        logger.info(f"🎯 Macro Bias: {context.overall_bias} ({context.confidence:.0%})")

