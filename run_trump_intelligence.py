#!/usr/bin/env python3
"""
🎯 TRUMP INTELLIGENCE MONITOR - 24/7 EXPLOIT HUNTER

Continuously monitors Trump news and sends Discord alerts for exploitable opportunities.

Features:
- Scans for new Trump news every 5 minutes
- Scores each news item for exploitability (0-100)
- Enriches with market context and historical parallels
- Sends Discord alerts for high-score opportunities (60+)
- Daily briefings at 6 AM, 12 PM, 6 PM ET
- Learns from new data continuously

Usage:
    python3 run_trump_intelligence.py
    python3 run_trump_intelligence.py --interval 300  # 5 minute interval
    python3 run_trump_intelligence.py --min-score 50  # Alert threshold
"""

import os
import sys
import time
import logging
import argparse
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Add paths
base_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_path)
sys.path.insert(0, os.path.join(base_path, 'live_monitoring', 'agents'))
sys.path.insert(0, os.path.join(base_path, 'live_monitoring', 'alerting'))

from live_monitoring.agents.trump_news_monitor import TrumpNewsMonitor, ExploitableNews
from live_monitoring.agents.trump_pulse import TrumpPulse
from live_monitoring.agents.trump_exploiter import TrumpExploiter
from live_monitoring.alerting.discord_alerter import DiscordAlerter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


class TrumpIntelligenceMonitor:
    """
    24/7 Trump Intelligence Monitor with Discord alerts.
    """
    
    def __init__(self, check_interval: int = 300, min_alert_score: float = 60):
        self.check_interval = check_interval
        self.min_alert_score = min_alert_score
        
        # Components
        self.news_monitor = TrumpNewsMonitor()
        self.pulse = TrumpPulse()
        self.exploiter = TrumpExploiter()
        
        # Discord
        webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
        self.discord = DiscordAlerter(webhook_url=webhook_url, username="🎯 Trump Intel")
        
        # State
        self.alerted_news_ids = set()
        self.last_briefing_hour = None
        self.briefing_hours = [6, 12, 18]  # 6 AM, 12 PM, 6 PM ET
        
        # Stats
        self.total_scans = 0
        self.total_alerts = 0
        self.session_start = datetime.now()
        
        logger.info("=" * 60)
        logger.info("🎯 TRUMP INTELLIGENCE MONITOR INITIALIZED")
        logger.info("=" * 60)
        logger.info(f"   Check interval: {self.check_interval}s ({self.check_interval/60:.1f} min)")
        logger.info(f"   Alert threshold: {self.min_alert_score}+ score")
        logger.info(f"   Discord: {'✅ Configured' if self.discord.enabled else '❌ Missing webhook'}")
        logger.info("=" * 60)
    
    def _should_send_briefing(self) -> bool:
        """Check if it's time for a scheduled briefing."""
        from datetime import time
        import pytz
        
        try:
            et = pytz.timezone('US/Eastern')
            now_et = datetime.now(et)
            current_hour = now_et.hour
            
            if current_hour in self.briefing_hours:
                if self.last_briefing_hour != current_hour:
                    self.last_briefing_hour = current_hour
                    return True
        except:
            pass
        
        return False
    
    def _format_exploit_alert(self, exploit: ExploitableNews) -> dict:
        """Format an exploit as a Discord embed."""
        # Emoji based on action
        action_emoji = {
            "BUY": "🟢", "SHORT": "🔴", "FADE_BEARISH": "🔄",
            "FADE_BULLISH": "🔄", "PREPARE": "⚠️", "WATCH": "👀"
        }.get(exploit.suggested_action, "❓")
        
        # Color based on urgency
        color_map = {
            "IMMEDIATE": 15548997,  # Red
            "HIGH": 16776960,       # Yellow
            "MEDIUM": 3447003,      # Blue
            "LOW": 8421504          # Gray
        }
        color = color_map.get(exploit.urgency, 3447003)
        
        # Build fields
        fields = [
            {"name": "Action", "value": f"{action_emoji} {exploit.suggested_action}", "inline": True},
            {"name": "Confidence", "value": f"{exploit.confidence:.0f}%", "inline": True},
            {"name": "Urgency", "value": exploit.urgency, "inline": True},
            {"name": "Symbols", "value": ", ".join(exploit.suggested_symbols[:5]), "inline": True},
            {"name": "Score", "value": f"{exploit.exploit_score:.0f}/100", "inline": True},
        ]
        
        # Add historical context if available
        if exploit.exploit_context.similar_events:
            top = exploit.exploit_context.similar_events[0]
            fields.append({
                "name": "Historical",
                "value": f"'{top['topic']}' = {top['avg_impact']:+.2f}% avg (n={top['count']})",
                "inline": False
            })
        
        # Add playbook if detected
        if exploit.exploit_context.playbook_pattern:
            bluff = " 🎭 BLUFF!" if exploit.exploit_context.is_likely_bluff else ""
            fields.append({
                "name": "Playbook",
                "value": f"{exploit.exploit_context.playbook_pattern}{bluff}",
                "inline": False
            })
        
        # Add timing
        if exploit.optimal_entry_window:
            fields.append({
                "name": "Entry Timing",
                "value": exploit.optimal_entry_window,
                "inline": False
            })
        
        # Market context
        ctx = exploit.market_context
        fields.append({
            "name": "Market Context",
            "value": f"SPY: ${ctx.spy_price:.2f} ({ctx.spy_change_pct:+.2f}%) | VIX: {ctx.vix_level:.1f} | Session: {ctx.session}",
            "inline": False
        })
        
        embed = {
            "title": f"🎯 EXPLOITABLE NEWS (Score: {exploit.exploit_score:.0f})",
            "description": f"**{exploit.news.headline[:200]}...**\n\nSource: {exploit.news.source}",
            "color": color,
            "fields": fields,
            "footer": {"text": "Trump Intelligence Monitor | Trade the pattern, not the panic"},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return embed
    
    def _send_briefing(self):
        """Send scheduled briefing to Discord."""
        if not self.discord.enabled:
            return
        
        logger.info("📋 Sending scheduled briefing...")
        
        try:
            # Get current situation
            situation = self.pulse.get_current_situation()
            exploit_report = self.exploiter.get_exploit_signals()
            
            # Build briefing
            sentiment_emoji = "📈" if situation.overall_sentiment == "BULLISH" else "📉" if situation.overall_sentiment == "BEARISH" else "➡️"
            stance_emoji = {"AGGRESSIVE": "🚀", "NEUTRAL": "✋", "CAUTIOUS": "⚠️", "DEFENSIVE": "🛡️"}.get(exploit_report.overall_stance, "❓")
            
            briefing_text = f"""
**📋 TRUMP INTELLIGENCE BRIEFING**

**{sentiment_emoji} Sentiment:** {situation.overall_sentiment} ({situation.sentiment_score:+.2f})
**📊 Activity:** {situation.total_statements_24h} statements in 24h
**🔥 Hot Topics:** {', '.join(situation.hot_topics[:3]) if situation.hot_topics else 'None'}

**{stance_emoji} Recommended Stance:** {exploit_report.overall_stance}
**💵 Cash Level:** {exploit_report.recommended_cash_pct:.0f}%
"""
            
            if exploit_report.top_trade:
                top = exploit_report.top_trade
                briefing_text += f"""
**🎯 Top Trade:** {top.action} {top.symbol}
   Confidence: {top.confidence:.0f}%
   Reason: {top.reason[:100]}...
"""
            
            self.discord.alert_info(briefing_text, title="🎯 Scheduled Briefing")
            logger.info("✅ Briefing sent")
            
        except Exception as e:
            logger.error(f"❌ Failed to send briefing: {e}")
    
    def scan_once(self):
        """Run a single scan cycle."""
        self.total_scans += 1
        logger.info(f"🔍 Scan #{self.total_scans} starting...")
        
        try:
            # Get exploitable news
            exploitable = self.news_monitor.get_exploitable_news(
                hours=6,
                min_score=self.min_alert_score * 0.5  # Get more, filter later
            )
            
            logger.info(f"   Found {len(exploitable)} items above minimum threshold")
            
            # Filter for high-score items we haven't alerted yet
            new_alerts = []
            for exp in exploitable:
                if exp.exploit_score >= self.min_alert_score:
                    if exp.news.id not in self.alerted_news_ids:
                        new_alerts.append(exp)
                        self.alerted_news_ids.add(exp.news.id)
            
            # Send alerts
            for exp in new_alerts:
                logger.info(f"   🚨 NEW EXPLOIT: {exp.news.headline[:50]}... (Score: {exp.exploit_score:.0f})")
                
                if self.discord.enabled:
                    embed = self._format_exploit_alert(exp)
                    try:
                        if self.discord.send_embed(embed):
                            self.total_alerts += 1
                            logger.info(f"   ✅ Alert sent to Discord")
                        else:
                            logger.warning(f"   ⚠️ Discord send returned False")
                    except Exception as e:
                        logger.error(f"   ❌ Failed to send alert: {e}")
            
            if not new_alerts:
                logger.info(f"   No new high-score exploits")
            
            # Check for scheduled briefing
            if self._should_send_briefing():
                self._send_briefing()
            
        except Exception as e:
            logger.error(f"❌ Scan failed: {e}")
            if self.discord.enabled:
                self.discord.alert_error(f"Scan failed: {str(e)[:200]}")
    
    def run(self):
        """Run the continuous monitor."""
        logger.info("")
        logger.info("🚀 STARTING CONTINUOUS MONITORING")
        logger.info(f"   Press Ctrl+C to stop")
        logger.info("")
        
        # Initial scan
        self.scan_once()
        
        # Send startup notification
        if self.discord.enabled:
            self.discord.alert_info(
                f"Trump Intelligence Monitor started!\n"
                f"• Check interval: {self.check_interval}s\n"
                f"• Alert threshold: {self.min_alert_score}+ score\n"
                f"• Briefings: 6 AM, 12 PM, 6 PM ET",
                title="🎯 Monitor Started"
            )
        
        # Main loop
        try:
            while True:
                time.sleep(self.check_interval)
                self.scan_once()
                
        except KeyboardInterrupt:
            logger.info("")
            logger.info("=" * 60)
            logger.info("👋 SHUTTING DOWN")
            logger.info("=" * 60)
            
            # Print stats
            runtime = datetime.now() - self.session_start
            logger.info(f"   Runtime: {runtime}")
            logger.info(f"   Total scans: {self.total_scans}")
            logger.info(f"   Total alerts: {self.total_alerts}")
            
            # Send shutdown notification
            if self.discord.enabled:
                self.discord.alert_info(
                    f"Monitor shutting down.\n"
                    f"• Runtime: {runtime}\n"
                    f"• Scans: {self.total_scans}\n"
                    f"• Alerts: {self.total_alerts}",
                    title="👋 Monitor Stopped"
                )


def main():
    parser = argparse.ArgumentParser(description="Trump Intelligence Monitor")
    parser.add_argument("--interval", type=int, default=300, help="Check interval in seconds (default: 300)")
    parser.add_argument("--min-score", type=float, default=60, help="Minimum score for alerts (default: 60)")
    
    args = parser.parse_args()
    
    monitor = TrumpIntelligenceMonitor(
        check_interval=args.interval,
        min_alert_score=args.min_score
    )
    monitor.run()


if __name__ == "__main__":
    main()

