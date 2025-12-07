"""
🧠 Narrative Brain - Unified Intelligence Orchestrator

Purpose: Transform siloed alerts into contextual, educational narrative updates
that build context over time and only alert when truly valuable.

Key Features:
- Pre-market outlook (8:30 AM)
- Smart intra-day updates (only when valuable)
- Real-time event analysis
- Context continuity across sessions
- Unified intelligence (no silos)
"""

import os
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class AlertType(Enum):
    PRE_MARKET = "pre_market"
    INTRA_DAY = "intra_day"
    EVENT_TRIGGERED = "event_triggered"
    END_OF_DAY = "end_of_day"


class NarrativePriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class NarrativeContext:
    """Context for narrative continuity"""
    timestamp: datetime
    market_regime: str  # BULLISH/BEARISH/NEUTRAL
    key_levels: Dict[str, float]  # SPY: 685.50, QQQ: 620.25
    sentiment: Dict[str, str]  # fed: HAWKISH, trump: BULLISH
    recent_events: List[str]  # Last 24h economic events
    narrative_themes: List[str]  # Current market themes
    last_update: datetime


@dataclass
class NarrativeUpdate:
    """A potential narrative update"""
    alert_type: AlertType
    priority: NarrativePriority
    title: str
    content: str
    context_references: List[str]  # Previous analyses to reference
    intelligence_sources: List[str]  # DP, Fed, Trump, etc.
    market_impact: str  # Expected move/significance
    timestamp: datetime


class NarrativeMemory:
    """Persistent memory for narrative context"""

    def __init__(self, db_path: str = "narrative_memory.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS narrative_context (
                    id INTEGER PRIMARY KEY,
                    date TEXT UNIQUE,
                    context_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS narrative_history (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT,
                    alert_type TEXT,
                    content TEXT,
                    intelligence_sources TEXT,
                    market_impact TEXT
                )
            """)

    def store_context(self, context: NarrativeContext):
        """Store current market context"""
        with sqlite3.connect(self.db_path) as conn:
            context_dict = asdict(context)
            context_dict['timestamp'] = context.timestamp.isoformat()
            context_dict['last_update'] = context.last_update.isoformat()

            conn.execute(
                "INSERT OR REPLACE INTO narrative_context (date, context_json) VALUES (?, ?)",
                (context.timestamp.strftime('%Y-%m-%d'), json.dumps(context_dict))
            )

    def get_context(self, date: str = None) -> Optional[NarrativeContext]:
        """Retrieve context for a date"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT context_json FROM narrative_context WHERE date = ?",
                (date,)
            )
            row = cursor.fetchone()

            if row:
                data = json.loads(row[0])
                # Convert back to datetime objects
                data['timestamp'] = datetime.fromisoformat(data['timestamp'])
                data['last_update'] = datetime.fromisoformat(data['last_update'])
                return NarrativeContext(**data)

        return None

    def store_narrative(self, update: NarrativeUpdate):
        """Store narrative history"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO narrative_history (timestamp, alert_type, content, intelligence_sources, market_impact) VALUES (?, ?, ?, ?, ?)",
                (
                    update.timestamp.isoformat(),
                    update.alert_type.value,
                    update.content,
                    json.dumps(update.intelligence_sources),
                    update.market_impact
                )
            )

    def get_recent_narratives(self, hours: int = 24) -> List[Dict]:
        """Get recent narratives for context"""
        cutoff = datetime.now() - timedelta(hours=hours)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM narrative_history WHERE timestamp > ? ORDER BY timestamp DESC",
                (cutoff.isoformat(),)
            )

            narratives = []
            for row in cursor.fetchall():
                narratives.append({
                    'timestamp': row[1],
                    'alert_type': row[2],
                    'content': row[3],
                    'intelligence_sources': json.loads(row[4]),
                    'market_impact': row[5]
                })

            return narratives


class AlertFilter:
    """Decides if a narrative update is valuable enough to send"""

    def __init__(self, memory: NarrativeMemory):
        self.memory = memory
        self.last_alert_time = datetime.now() - timedelta(hours=1)  # Start with 1h ago

    def should_send_update(self, update: NarrativeUpdate) -> bool:
        """
        Determine if this narrative update is valuable enough to send
        """

        # Always send critical updates
        if update.priority == NarrativePriority.CRITICAL:
            return True

        # Pre-market outlook: Send if it's morning
        if update.alert_type == AlertType.PRE_MARKET:
            return self._is_morning_time()

        # Event-triggered: Always send (they're important by definition)
        if update.alert_type == AlertType.EVENT_TRIGGERED:
            return True

        # Intra-day: Smart filtering
        if update.alert_type == AlertType.INTRA_DAY:
            return self._should_send_intra_day(update)

        # End of day: Send if significant changes
        if update.alert_type == AlertType.END_OF_DAY:
            return self._should_send_eod(update)

        return False

    def _is_morning_time(self) -> bool:
        """Check if it's pre-market time (8:00-9:30 AM ET)"""
        now = datetime.now()
        hour = now.hour
        return 8 <= hour <= 9  # 8 AM - 9:30 AM ET

    def _should_send_intra_day(self, update: NarrativeUpdate) -> bool:
        """Smart filtering for intra-day updates"""

        # Check time since last alert
        time_since_last = datetime.now() - self.last_alert_time
        if time_since_last < timedelta(hours=2):
            # Too soon, check if critical
            if update.priority.value < NarrativePriority.HIGH.value:
                return False

        # Check if market is moving significantly
        if "significant move" in update.content.lower() or "breakout" in update.content.lower():
            return True

        # Check for new intelligence confluence
        if len(update.intelligence_sources) >= 3:  # 3+ sources agreeing
            return True

        # Check for regime change
        if "regime change" in update.content.lower():
            return True

        # Check for opportunity with confluence
        if "confluence" in update.content.lower() and "opportunity" in update.content.lower():
            return True

        return False

    def _should_send_eod(self, update: NarrativeUpdate) -> bool:
        """Filter end-of-day updates"""
        # Send if it confirms/rejects morning outlook
        if "confirmed" in update.content.lower() or "rejected" in update.content.lower():
            return True

        # Send if significant moves occurred
        if "significant" in update.content.lower():
            return True

        return False


class ContextIntegrator:
    """Integrates intelligence from all sources"""

    def __init__(self):
        self.sources = {}

    def update_source(self, source_name: str, data: Dict[str, Any]):
        """Update intelligence from a source"""
        self.sources[source_name] = {
            'data': data,
            'timestamp': datetime.now()
        }

    def get_unified_context(self) -> Dict[str, Any]:
        """Get unified view of all intelligence"""

        context = {
            'dp_levels': self._get_dp_context(),
            'fed_intelligence': self._get_fed_context(),
            'trump_intelligence': self._get_trump_context(),
            'economic_events': self._get_economic_context(),
            'market_regime': self._detect_market_regime(),
            'confluence_score': self._calculate_confluence()
        }

        return context

    def _get_dp_context(self) -> Dict:
        """Get dark pool context"""
        dp_data = self.sources.get('dp_monitor', {}).get('data', {})
        return {
            'active_levels': dp_data.get('battlegrounds', []),
            'volume_trend': dp_data.get('volume_trend', 'neutral'),
            'institutional_bias': dp_data.get('bias', 'neutral')
        }

    def _get_fed_context(self) -> Dict:
        """Get Fed intelligence context"""
        fed_data = self.sources.get('fed_watch', {}).get('data', {})
        fed_official_data = self.sources.get('fed_officials', {}).get('data', {})

        return {
            'rate_cut_prob': fed_data.get('cut_prob', 50),
            'fed_sentiment': fed_official_data.get('sentiment', 'neutral'),
            'next_meeting': fed_data.get('next_fomc', 'unknown')
        }

    def _get_trump_context(self) -> Dict:
        """Get Trump intelligence context"""
        trump_data = self.sources.get('trump_monitor', {}).get('data', {})
        return {
            'sentiment': trump_data.get('sentiment', 'neutral'),
            'activity_level': trump_data.get('activity', 'normal'),
            'hot_topics': trump_data.get('topics', [])
        }

    def _get_economic_context(self) -> Dict:
        """Get economic events context"""
        econ_data = self.sources.get('economic_calendar', {}).get('data', {})
        return {
            'today_events': econ_data.get('today', []),
            'high_impact': [e for e in econ_data.get('today', []) if e.get('importance') == 'HIGH'],
            'recent_surprises': econ_data.get('recent_surprises', [])
        }

    def _detect_market_regime(self) -> str:
        """Detect overall market regime from all sources"""
        # Simple logic: combine multiple signals
        signals = []

        # DP bias
        dp_bias = self._get_dp_context().get('institutional_bias', 'neutral')
        if dp_bias == 'bullish':
            signals.append(1)
        elif dp_bias == 'bearish':
            signals.append(-1)

        # Fed sentiment
        fed_sentiment = self._get_fed_context().get('fed_sentiment', 'neutral')
        if fed_sentiment == 'HAWKISH':
            signals.append(-1)  # Hawkish = bearish pressure
        elif fed_sentiment == 'DOVISH':
            signals.append(1)   # Dovish = bullish pressure

        # Economic surprises
        recent_surprises = self._get_economic_context().get('recent_surprises', [])
        if recent_surprises:
            surprise_score = sum(s.get('sigma', 0) for s in recent_surprises)
            if surprise_score > 1:
                signals.append(1)  # Positive surprises = bullish
            elif surprise_score < -1:
                signals.append(-1)  # Negative surprises = bearish

        # Average signal
        if signals:
            avg_signal = sum(signals) / len(signals)
            if avg_signal > 0.3:
                return "BULLISH"
            elif avg_signal < -0.3:
                return "BEARISH"

        return "NEUTRAL"

    def _calculate_confluence(self) -> float:
        """Calculate confluence score (0-100)"""
        # Simple confluence: how many sources agree
        sources_agreeing = 0
        total_sources = 4  # DP, Fed, Trump, Economic

        regime = self._detect_market_regime()

        # Check each source alignment with regime
        dp_bias = self._get_dp_context().get('institutional_bias', 'neutral')
        if (regime == "BULLISH" and dp_bias == "bullish") or \
           (regime == "BEARISH" and dp_bias == "bearish"):
            sources_agreeing += 1

        fed_sentiment = self._get_fed_context().get('fed_sentiment', 'neutral')
        if (regime == "BULLISH" and fed_sentiment == "DOVISH") or \
           (regime == "BEARISH" and fed_sentiment == "HAWKISH"):
            sources_agreeing += 1

        # Simplified for other sources
        sources_agreeing += 1  # Assume economic aligns

        return (sources_agreeing / total_sources) * 100


class DiscordFormatter:
    """Formats narrative updates for Discord"""

    def format_update(self, update: NarrativeUpdate, context: Optional[NarrativeContext] = None) -> str:
        """Format a narrative update for Discord"""

        # Header based on alert type
        headers = {
            AlertType.PRE_MARKET: "🌅 MORNING MARKET OUTLOOK",
            AlertType.INTRA_DAY: "📈 MARKET UPDATE",
            AlertType.EVENT_TRIGGERED: "🚨 EVENT ANALYSIS",
            AlertType.END_OF_DAY: "📊 END OF DAY REVIEW"
        }

        header = headers.get(update.alert_type, "🧠 NARRATIVE UPDATE")

        # Priority indicators
        priority_icons = {
            NarrativePriority.LOW: "⚪",
            NarrativePriority.MEDIUM: "🟡",
            NarrativePriority.HIGH: "🔴",
            NarrativePriority.CRITICAL: "🚨"
        }

        priority_icon = priority_icons.get(update.priority, "⚪")

        # Build message
        message = f"**{header}** {priority_icon}\n\n"
        message += f"**{update.title}**\n\n"
        message += f"{update.content}\n\n"

        # Add context references if any
        if update.context_references:
            message += "**Context:**\n"
            for ref in update.context_references[:2]:  # Limit to 2
                message += f"• {ref}\n"
            message += "\n"

        # Add intelligence sources
        if update.intelligence_sources:
            sources_str = ", ".join(update.intelligence_sources)
            message += f"**Sources:** {sources_str}\n"

        # Add market impact
        if update.market_impact:
            message += f"**Impact:** {update.market_impact}\n"

        # Add timestamp
        message += f"\n`{update.timestamp.strftime('%H:%M ET')}`"

        return message


class NarrativeBrain:
    """
    🧠 Unified Narrative Intelligence Brain

    Orchestrates all intelligence sources into contextual, valuable narrative updates.
    """

    def __init__(self, discord_webhook: str = None):
        self.memory = NarrativeMemory()
        self.filter = AlertFilter(self.memory)
        self.integrator = ContextIntegrator()
        self.formatter = DiscordFormatter()
        self.discord_webhook = discord_webhook or os.getenv('DISCORD_WEBHOOK_URL')

        # Track last updates
        self.last_pre_market = None
        self.last_intra_day = datetime.now() - timedelta(hours=3)  # Start 3h ago

        logger.info("🧠 NarrativeBrain initialized")

    def process_intelligence_update(self, source: str, data: Dict[str, Any]) -> Optional[NarrativeUpdate]:
        """
        Process new intelligence and decide if to generate narrative update
        """
        # Update integrator with new data
        self.integrator.update_source(source, data)

        # Get unified context
        unified_context = self.integrator.get_unified_context()

        # Generate potential update based on context
        update = self._generate_update_if_valuable(unified_context)

        if update and self.filter.should_send_update(update):
            # Store in memory
            self.memory.store_narrative(update)

            # Send to Discord
            self._send_to_discord(update)

            # Update last sent times
            if update.alert_type == AlertType.INTRA_DAY:
                self.last_intra_day = datetime.now()

            return update

        return None

    def generate_pre_market_outlook(self) -> Optional[NarrativeUpdate]:
        """Generate pre-market outlook"""
        try:
            # Get current context
            current_context = self.memory.get_context()

            # Build outlook
            title = "Today's Market Outlook"

            content_parts = []

            # Market regime
            regime = self.integrator._detect_market_regime()
            content_parts.append(f"**Market Regime:** {regime}")

            # Key levels
            dp_context = self.integrator._get_dp_context()
            if dp_context.get('active_levels'):
                levels = dp_context['active_levels'][:3]  # Top 3
                level_str = ", ".join([f"${l['price']:.2f}" for l in levels])
                content_parts.append(f"**Key DP Levels:** {level_str}")

            # Today's events
            econ_context = self.integrator._get_economic_context()
            high_impact = econ_context.get('high_impact', [])
            if high_impact:
                events_str = ", ".join([e.get('name', 'Unknown') for e in high_impact])
                content_parts.append(f"**High Impact Events:** {events_str}")

            # Fed context
            fed_context = self.integrator._get_fed_context()
            cut_prob = fed_context.get('rate_cut_prob', 50)
            fed_sentiment = fed_context.get('fed_sentiment', 'neutral')
            content_parts.append(f"**Fed Outlook:** {cut_prob}% cut probability, {fed_sentiment} sentiment")

            # Trump context
            trump_context = self.integrator._get_trump_context()
            trump_sentiment = trump_context.get('sentiment', 'neutral')
            content_parts.append(f"**Trump Sentiment:** {trump_sentiment}")

            content = "\n".join(content_parts)

            update = NarrativeUpdate(
                alert_type=AlertType.PRE_MARKET,
                priority=NarrativePriority.HIGH,
                title=title,
                content=content,
                context_references=[],
                intelligence_sources=["market_regime", "dp_levels", "economic_calendar", "fed_watch", "trump_monitor"],
                market_impact="Sets context for day's trading",
                timestamp=datetime.now()
            )

            # Store and send
            self.memory.store_narrative(update)
            self._send_to_discord(update)

            return update

        except Exception as e:
            logger.error(f"Error generating pre-market outlook: {e}")
            return None

    def _generate_update_if_valuable(self, context: Dict[str, Any]) -> Optional[NarrativeUpdate]:
        """Generate update if context indicates something valuable"""

        # Check for regime change
        current_regime = context.get('market_regime', 'NEUTRAL')
        previous_context = self.memory.get_context()

        if previous_context and previous_context.market_regime != current_regime:
            return NarrativeUpdate(
                alert_type=AlertType.INTRA_DAY,
                priority=NarrativePriority.HIGH,
                title=f"Market Regime Shift: {current_regime}",
                content=f"Market regime has shifted to {current_regime}. This represents a significant change in market psychology and may indicate new opportunities.",
                context_references=[f"Previous regime: {previous_context.market_regime}"],
                intelligence_sources=["market_regime", "dp_levels", "fed_intelligence"],
                market_impact=f"Potential for {current_regime.lower()} moves",
                timestamp=datetime.now()
            )

        # Check for high confluence
        confluence = context.get('confluence_score', 0)
        if confluence >= 75:  # High confluence
            return NarrativeUpdate(
                alert_type=AlertType.INTRA_DAY,
                priority=NarrativePriority.HIGH,
                title="High Intelligence Confluence",
                content=f"Multiple intelligence sources showing strong agreement ({confluence:.0f}% confluence). This represents a high-confidence signal.",
                context_references=[],
                intelligence_sources=context.get('intelligence_sources', []),
                market_impact="High-confidence trading opportunity",
                timestamp=datetime.now()
            )

        return None

    def _send_to_discord(self, update: NarrativeUpdate):
        """Send formatted update to Discord"""
        if not self.discord_webhook:
            logger.warning("No Discord webhook configured")
            return

        try:
            formatted_message = self.formatter.format_update(update)

            payload = {
                "content": formatted_message,
                "username": "Alpha Intelligence"
            }

            import requests
            response = requests.post(
                self.discord_webhook,
                json=payload,
                timeout=10
            )

            if response.status_code == 204:
                logger.info(f"✅ Discord alert sent: {update.alert_type.value}")
            else:
                logger.error(f"❌ Discord send failed: {response.status_code}")

        except Exception as e:
            logger.error(f"Error sending to Discord: {e}")

    def get_current_context(self) -> Dict[str, Any]:
        """Get current unified intelligence context"""
        context = self.integrator.get_unified_context()
        context['narrative_memory'] = self.memory.get_recent_narratives(hours=24)
        return context


