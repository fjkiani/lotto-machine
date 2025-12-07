#!/usr/bin/env python3
"""
🏦 FED WATCH CONTINUOUS MONITOR

Continuously monitors Fed rate cut/hike probabilities and sends
Discord alerts when significant changes occur.

Usage:
    python3 run_fed_watch_monitor.py
    
Environment:
    DISCORD_WEBHOOK_URL: Discord webhook for alerts

Features:
    - Checks probabilities every 5 minutes
    - Alerts on 5%+ changes in any probability
    - Provides market implications with each alert
    - Tracks changes over time
"""

import os
import sys
import time
import logging
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add paths
base_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_path)

from live_monitoring.agents.fed_watch_monitor import FedWatchMonitor, FedWatchStatus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


class FedWatchContinuousMonitor:
    """
    Continuous monitor for Fed rate probabilities with Discord alerts.
    """
    
    def __init__(
        self,
        check_interval: int = 300,  # 5 minutes
        alert_threshold: float = 5.0,  # 5% change triggers alert
        discord_webhook: str = None
    ):
        self.check_interval = check_interval
        self.alert_threshold = alert_threshold
        self.discord_webhook = discord_webhook or os.getenv('DISCORD_WEBHOOK_URL')
        
        self.monitor = FedWatchMonitor(alert_threshold=alert_threshold)
        self.last_status: FedWatchStatus = None
        self.check_count = 0
        self.alert_count = 0
        
        # History tracking
        self.history = []
        
        logger.info("=" * 60)
        logger.info("🏦 FED WATCH CONTINUOUS MONITOR STARTED")
        logger.info("=" * 60)
        logger.info(f"   Check interval: {check_interval} seconds ({check_interval/60:.1f} min)")
        logger.info(f"   Alert threshold: {alert_threshold}% change")
        logger.info(f"   Discord webhook: {'✅ Configured' if self.discord_webhook else '❌ Not configured'}")
        logger.info("=" * 60)
    
    def send_discord_alert(self, embed: dict, content: str = None) -> bool:
        """Send alert to Discord."""
        if not self.discord_webhook:
            logger.warning("Discord webhook not configured, skipping alert")
            return False
        
        try:
            payload = {"embeds": [embed]}
            if content:
                payload["content"] = content
            
            response = requests.post(
                self.discord_webhook,
                json=payload,
                timeout=10
            )
            
            if response.status_code in [200, 204]:
                logger.info("✅ Discord alert sent successfully")
                return True
            else:
                logger.warning(f"Discord alert failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Discord alert error: {e}")
            return False
    
    def check_and_alert(self) -> bool:
        """
        Check current probabilities and alert if significant changes.
        Returns True if alert was sent.
        """
        self.check_count += 1
        
        current = self.monitor.get_current_status(force_refresh=True)
        
        # Add to history
        self.history.append({
            'timestamp': current.timestamp,
            'prob_cut': current.prob_cut,
            'prob_hold': current.prob_hold,
            'prob_hike': current.prob_hike
        })
        
        # Keep only last 288 entries (24 hours at 5-min intervals)
        if len(self.history) > 288:
            self.history = self.history[-288:]
        
        # Check for changes
        alert_sent = False
        
        if self.last_status:
            changes = []
            
            # Check each probability for changes
            cut_change = current.prob_cut - self.last_status.prob_cut
            hold_change = current.prob_hold - self.last_status.prob_hold
            hike_change = current.prob_hike - self.last_status.prob_hike
            
            if abs(cut_change) >= self.alert_threshold:
                changes.append(('CUT', cut_change, current.prob_cut))
            if abs(hold_change) >= self.alert_threshold:
                changes.append(('HOLD', hold_change, current.prob_hold))
            if abs(hike_change) >= self.alert_threshold:
                changes.append(('HIKE', hike_change, current.prob_hike))
            
            if changes:
                self.alert_count += 1
                logger.info("=" * 60)
                logger.info("🚨 SIGNIFICANT CHANGE DETECTED!")
                logger.info("=" * 60)
                
                for prob_type, change, new_value in changes:
                    direction = "↑" if change > 0 else "↓"
                    logger.info(f"   {prob_type}: {new_value:.1f}% ({change:+.1f}%)")
                
                # Send Discord alert
                if self.discord_webhook:
                    embed = self._create_alert_embed(current, changes)
                    self.send_discord_alert(embed, content="@everyone 🚨 Fed rate probability change!")
                    alert_sent = True
        
        # Print current status
        logger.info(f"📊 Check #{self.check_count}: Cut {current.prob_cut:.1f}% | Hold {current.prob_hold:.1f}% | Hike {current.prob_hike:.1f}%")
        
        self.last_status = current
        return alert_sent
    
    def _create_alert_embed(self, status: FedWatchStatus, changes: list) -> dict:
        """Create Discord embed for alert."""
        
        # Determine severity color
        max_change = max(abs(c[1]) for c in changes)
        if max_change >= 15:
            color = 15548997  # Red
        elif max_change >= 10:
            color = 16776960  # Yellow
        else:
            color = 3447003  # Blue
        
        # Build change description
        change_lines = []
        for prob_type, change, new_value in changes:
            emoji = "📈" if change > 0 else "📉"
            change_lines.append(f"{emoji} **{prob_type}**: {new_value:.1f}% ({change:+.1f}%)")
        
        # Get implications
        implications = self.monitor.get_market_implications(status)
        
        # Trade ideas
        trade_lines = [f"• {t['action']} {t['symbol']}" for t in implications['trades'][:3]]
        
        embed = {
            "title": "🏦 FED WATCH ALERT - Rate Probability Change",
            "color": color,
            "fields": [
                {
                    "name": "📊 Changes Detected",
                    "value": "\n".join(change_lines),
                    "inline": False
                },
                {
                    "name": "📈 Current Probabilities",
                    "value": f"Cut: {status.prob_cut:.1f}% | Hold: {status.prob_hold:.1f}% | Hike: {status.prob_hike:.1f}%",
                    "inline": False
                },
                {
                    "name": "🎯 Most Likely",
                    "value": f"{status.most_likely_outcome} ({status.most_likely_probability:.1f}%)",
                    "inline": True
                },
                {
                    "name": "📅 Next FOMC",
                    "value": f"{status.next_meeting.date.strftime('%b %d')} ({status.next_meeting.days_until}d)" if status.next_meeting else "N/A",
                    "inline": True
                },
                {
                    "name": f"{'🟢' if status.market_bias == 'BULLISH' else '🔴' if status.market_bias == 'BEARISH' else '🟡'} Market Bias",
                    "value": status.market_bias,
                    "inline": True
                },
                {
                    "name": "💡 Implication",
                    "value": implications['summary'][:200],
                    "inline": False
                },
                {
                    "name": "💰 Trade Ideas",
                    "value": "\n".join(trade_lines) if trade_lines else "Monitor for clearer signal",
                    "inline": False
                }
            ],
            "footer": {"text": "Fed Watch Monitor | Rate expectations move markets!"},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return embed
    
    def send_startup_alert(self):
        """Send startup notification with current status."""
        if not self.discord_webhook:
            return
        
        status = self.monitor.get_current_status()
        
        embed = {
            "title": "🏦 Fed Watch Monitor - ONLINE",
            "color": 3066993,  # Green
            "description": "Monitoring Fed rate cut/hike probabilities",
            "fields": [
                {
                    "name": "📊 Current Probabilities",
                    "value": f"Cut: {status.prob_cut:.1f}% | Hold: {status.prob_hold:.1f}% | Hike: {status.prob_hike:.1f}%",
                    "inline": False
                },
                {
                    "name": "🎯 Most Likely Outcome",
                    "value": f"{status.most_likely_outcome} ({status.most_likely_probability:.1f}%)",
                    "inline": True
                },
                {
                    "name": "📅 Next FOMC Meeting",
                    "value": f"{status.next_meeting.date.strftime('%B %d, %Y')} ({status.next_meeting.days_until} days)" if status.next_meeting else "N/A",
                    "inline": True
                },
                {
                    "name": "⚙️ Settings",
                    "value": f"Check interval: {self.check_interval/60:.0f} min | Alert threshold: {self.alert_threshold}%",
                    "inline": False
                }
            ],
            "footer": {"text": "Will alert on significant probability changes"},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.send_discord_alert(embed)
    
    def run(self):
        """Run the continuous monitor."""
        logger.info("🚀 Starting continuous monitoring...")
        
        # Send startup alert
        self.send_startup_alert()
        
        # Initial check
        self.check_and_alert()
        
        while True:
            try:
                # Wait for next check
                logger.info(f"⏳ Next check in {self.check_interval} seconds...")
                time.sleep(self.check_interval)
                
                # Check and alert
                self.check_and_alert()
                
            except KeyboardInterrupt:
                logger.info("\n🛑 Monitor stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Error in monitor loop: {e}")
                time.sleep(60)  # Wait a minute before retrying
    
    def scan_once(self):
        """Run a single scan (for testing)."""
        logger.info("🔍 Running single Fed Watch scan...")
        
        status = self.monitor.get_current_status(force_refresh=True)
        self.monitor.print_fed_dashboard(status)
        
        # Check if significant change from last known
        if self.last_status:
            changes = []
            cut_change = status.prob_cut - self.last_status.prob_cut
            hold_change = status.prob_hold - self.last_status.prob_hold
            hike_change = status.prob_hike - self.last_status.prob_hike
            
            if abs(cut_change) >= self.alert_threshold:
                changes.append(('CUT', cut_change, status.prob_cut))
            if abs(hold_change) >= self.alert_threshold:
                changes.append(('HOLD', hold_change, status.prob_hold))
            if abs(hike_change) >= self.alert_threshold:
                changes.append(('HIKE', hike_change, status.prob_hike))
            
            if changes:
                logger.info("🚨 WOULD ALERT: Significant changes detected!")
                for prob_type, change, new_value in changes:
                    logger.info(f"   {prob_type}: {new_value:.1f}% ({change:+.1f}%)")
        
        self.last_status = status
        return status


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Fed Watch Continuous Monitor")
    parser.add_argument("--interval", type=int, default=300, help="Check interval in seconds (default: 300)")
    parser.add_argument("--threshold", type=float, default=5.0, help="Alert threshold in % (default: 5.0)")
    parser.add_argument("--once", action="store_true", help="Run single scan only")
    
    args = parser.parse_args()
    
    monitor = FedWatchContinuousMonitor(
        check_interval=args.interval,
        alert_threshold=args.threshold
    )
    
    if args.once:
        monitor.scan_once()
    else:
        monitor.run()


if __name__ == "__main__":
    main()



