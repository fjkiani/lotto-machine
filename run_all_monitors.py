#!/usr/bin/env python3
"""
🎯 ALPHA INTELLIGENCE - UNIFIED MONITOR

Runs ALL monitoring systems in parallel:
1. 🏦 Fed Watch - Rate cut/hike probabilities + Fed official comments
2. 🎯 Trump Intelligence - Trump statements + market exploitation
3. 📰 News Exploit - News vs Dark Pool divergences

This is the MASTER DEPLOYMENT script for 24/7 monitoring.

Usage:
    python3 run_all_monitors.py

Environment Variables Required:
    PERPLEXITY_API_KEY: For news fetching
    DISCORD_WEBHOOK_URL: For alerts
    CHARTEXCHANGE_API_KEY: For dark pool data
"""

import os
import sys
import time
import logging
import threading
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add paths
base_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_path)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


class UnifiedAlphaMonitor:
    """
    Master orchestrator for all monitoring systems.
    """
    
    def __init__(self):
        self.discord_webhook = os.getenv('DISCORD_WEBHOOK_URL')
        self.running = True
        
        # Intervals (in seconds)
        self.fed_interval = 300      # 5 minutes for Fed
        self.trump_interval = 180    # 3 minutes for Trump
        self.news_interval = 300     # 5 minutes for news
        
        # Track last run times
        self.last_fed_check = None
        self.last_trump_check = None
        self.last_news_check = None
        
        # Import monitors
        self._init_monitors()
        
        logger.info("=" * 70)
        logger.info("🎯 ALPHA INTELLIGENCE - UNIFIED MONITOR STARTED")
        logger.info("=" * 70)
        logger.info(f"   Discord: {'✅' if self.discord_webhook else '❌'}")
        logger.info(f"   Fed Watch: Every {self.fed_interval/60:.0f} min")
        logger.info(f"   Trump Intel: Every {self.trump_interval/60:.0f} min")
        logger.info(f"   News Exploit: Every {self.news_interval/60:.0f} min")
        logger.info("=" * 70)
    
    def _init_monitors(self):
        """Initialize all monitor components."""
        
        # Fed Watch Monitor
        try:
            from live_monitoring.agents.fed_watch_monitor import FedWatchMonitor
            from live_monitoring.agents.fed_officials_monitor import FedOfficialsMonitor
            self.fed_watch = FedWatchMonitor(alert_threshold=5.0)
            self.fed_officials = FedOfficialsMonitor()
            self.fed_enabled = True
            logger.info("   ✅ Fed monitors initialized")
        except Exception as e:
            logger.warning(f"   ⚠️ Fed monitors failed: {e}")
            self.fed_enabled = False
        
        # Trump Intelligence
        try:
            from live_monitoring.agents.trump_pulse import TrumpPulse
            from live_monitoring.agents.trump_news_monitor import TrumpNewsMonitor
            self.trump_pulse = TrumpPulse()
            self.trump_news = TrumpNewsMonitor()
            self.trump_enabled = True
            logger.info("   ✅ Trump monitors initialized")
        except Exception as e:
            logger.warning(f"   ⚠️ Trump monitors failed: {e}")
            self.trump_enabled = False
        
        # Track previous states
        self.prev_fed_status = None
        self.prev_trump_sentiment = None
        self.seen_trump_news = set()
    
    def send_discord(self, embed: dict, content: str = None) -> bool:
        """Send Discord notification."""
        if not self.discord_webhook:
            return False
        
        try:
            payload = {"embeds": [embed]}
            if content:
                payload["content"] = content
            
            response = requests.post(self.discord_webhook, json=payload, timeout=10)
            return response.status_code in [200, 204]
        except Exception as e:
            logger.error(f"Discord error: {e}")
            return False
    
    def check_fed(self):
        """Check Fed Watch and officials."""
        if not self.fed_enabled:
            return
        
        logger.info("🏦 Checking Fed Watch...")
        
        try:
            # Get current status
            status = self.fed_watch.get_current_status(force_refresh=True)
            
            # Check for significant changes
            if self.prev_fed_status:
                cut_change = abs(status.prob_cut - self.prev_fed_status.prob_cut)
                hold_change = abs(status.prob_hold - self.prev_fed_status.prob_hold)
                
                if cut_change >= 5.0 or hold_change >= 5.0:
                    logger.info(f"   🚨 SIGNIFICANT CHANGE! Cut: {status.prob_cut:.1f}% ({cut_change:+.1f}%)")
                    
                    # Send alert
                    embed = {
                        "title": "🏦 FED WATCH ALERT - Probability Change!",
                        "color": 15548997,
                        "fields": [
                            {"name": "📉 Cut Probability", "value": f"{status.prob_cut:.1f}%", "inline": True},
                            {"name": "➡️ Hold Probability", "value": f"{status.prob_hold:.1f}%", "inline": True},
                            {"name": "🎯 Most Likely", "value": status.most_likely_outcome, "inline": True},
                        ],
                        "footer": {"text": "CME FedWatch | Rate expectations move markets!"},
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    self.send_discord(embed, content="@everyone 🏦 Fed rate probability change!")
            
            self.prev_fed_status = status
            logger.info(f"   Cut: {status.prob_cut:.1f}% | Hold: {status.prob_hold:.1f}% | Most Likely: {status.most_likely_outcome}")
            
            # Check Fed officials
            logger.info("   🎤 Checking Fed officials...")
            report = self.fed_officials.get_report()
            
            if report.comments:
                for comment in report.comments[:3]:
                    comment_id = f"{comment.official.name}:{comment.content[:30]}"
                    if comment_id not in self.seen_trump_news:  # Reusing set for dedup
                        self.seen_trump_news.add(comment_id)
                        
                        if comment.official.name == "Jerome Powell" or comment.confidence >= 0.5:
                            # Alert on significant Fed comments
                            sent_emoji = {"HAWKISH": "🦅", "DOVISH": "🕊️", "NEUTRAL": "➡️"}.get(comment.sentiment, "❓")
                            embed = {
                                "title": f"🎤 {comment.official.name} - {comment.sentiment}",
                                "color": 3066993 if comment.sentiment == "DOVISH" else 15548997 if comment.sentiment == "HAWKISH" else 3447003,
                                "description": f'"{comment.content[:200]}..."',
                                "fields": [
                                    {"name": f"{sent_emoji} Sentiment", "value": comment.sentiment, "inline": True},
                                    {"name": "📊 Impact", "value": comment.market_impact, "inline": True},
                                ],
                                "footer": {"text": "Fed Officials Monitor"},
                                "timestamp": datetime.utcnow().isoformat()
                            }
                            self.send_discord(embed)
            
        except Exception as e:
            logger.error(f"   ❌ Fed check error: {e}")
    
    def check_trump(self):
        """Check Trump intelligence."""
        if not self.trump_enabled:
            return
        
        logger.info("🎯 Checking Trump Intelligence...")
        
        try:
            # Get current pulse
            situation = self.trump_pulse.get_current_situation()
            
            # Check for exploitable news
            exploitable = self.trump_news.get_exploitable_news()
            
            for exp in exploitable[:3]:
                news_id = exp.news.headline[:50]
                if news_id not in self.seen_trump_news and exp.exploit_score >= 60:
                    self.seen_trump_news.add(news_id)
                    
                    # Send alert
                    embed = {
                        "title": f"🎯 TRUMP EXPLOIT: {exp.suggested_action} (Score: {exp.exploit_score:.0f})",
                        "color": 16776960,
                        "description": exp.news.headline[:200],
                        "fields": [
                            {"name": "📊 Action", "value": exp.suggested_action, "inline": True},
                            {"name": "📈 Symbols", "value": ", ".join(exp.suggested_symbols[:3]), "inline": True},
                            {"name": "💯 Confidence", "value": f"{exp.confidence:.0f}%", "inline": True},
                        ],
                        "footer": {"text": "Trump Intelligence | Trade the pattern!"},
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    self.send_discord(embed)
            
            activity = getattr(situation, 'activity_level', 'N/A')
            sentiment = getattr(situation, 'overall_sentiment', 'UNKNOWN')
            logger.info(f"   Sentiment: {sentiment} | Exploits: {len(exploitable)}")
            
        except Exception as e:
            logger.error(f"   ❌ Trump check error: {e}")
    
    def send_startup_alert(self):
        """Send startup notification."""
        if not self.discord_webhook:
            return
        
        embed = {
            "title": "🎯 ALPHA INTELLIGENCE - ONLINE",
            "color": 3066993,
            "description": "All monitoring systems activated",
            "fields": [
                {"name": "🏦 Fed Watch", "value": "✅ Active" if self.fed_enabled else "❌ Disabled", "inline": True},
                {"name": "🎯 Trump Intel", "value": "✅ Active" if self.trump_enabled else "❌ Disabled", "inline": True},
                {"name": "⏱️ Intervals", "value": f"Fed: {self.fed_interval/60:.0f}m | Trump: {self.trump_interval/60:.0f}m", "inline": False},
            ],
            "footer": {"text": "Monitoring markets 24/7"},
            "timestamp": datetime.utcnow().isoformat()
        }
        self.send_discord(embed)
    
    def run(self):
        """Main run loop."""
        logger.info("🚀 Starting unified monitoring...")
        
        # Startup alert
        self.send_startup_alert()
        
        # Initial checks
        self.check_fed()
        self.check_trump()
        
        while self.running:
            try:
                now = datetime.now()
                
                # Check Fed (every 5 min)
                if self.last_fed_check is None or (now - self.last_fed_check).seconds >= self.fed_interval:
                    self.check_fed()
                    self.last_fed_check = now
                
                # Check Trump (every 3 min)
                if self.last_trump_check is None or (now - self.last_trump_check).seconds >= self.trump_interval:
                    self.check_trump()
                    self.last_trump_check = now
                
                # Sleep for 60 seconds between checks
                time.sleep(60)
                
            except KeyboardInterrupt:
                logger.info("\n🛑 Monitor stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Main loop error: {e}")
                time.sleep(60)


# ============================================================================
# WEB SERVICE WRAPPER (For Render deployment)
# ============================================================================

def create_web_app():
    """Create FastAPI app for Render web service."""
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        import uvicorn
    except ImportError:
        logger.warning("FastAPI not installed, running without web server")
        return None
    
    app = FastAPI(title="Alpha Intelligence Monitor")
    monitor = None
    
    @app.on_event("startup")
    async def startup():
        nonlocal monitor
        monitor = UnifiedAlphaMonitor()
        # Start monitoring in background thread
        import threading
        thread = threading.Thread(target=monitor.run, daemon=True)
        thread.start()
        logger.info("✅ Monitor started in background")
    
    @app.get("/")
    def root():
        return {"status": "ALPHA INTELLIGENCE ONLINE", "timestamp": datetime.now().isoformat()}
    
    @app.get("/health")
    def health():
        return JSONResponse({"status": "healthy", "monitors": {
            "fed": getattr(monitor, 'fed_enabled', False) if monitor else False,
            "trump": getattr(monitor, 'trump_enabled', False) if monitor else False,
        }})
    
    @app.get("/status")
    def status():
        if monitor and monitor.prev_fed_status:
            return {
                "fed": {
                    "prob_cut": monitor.prev_fed_status.prob_cut,
                    "prob_hold": monitor.prev_fed_status.prob_hold,
                    "most_likely": monitor.prev_fed_status.most_likely_outcome
                }
            }
        return {"status": "initializing"}
    
    return app


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Alpha Intelligence Unified Monitor")
    parser.add_argument("--web", action="store_true", help="Run as web service (for Render)")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", 10000)), help="Port for web service")
    
    args = parser.parse_args()
    
    if args.web:
        app = create_web_app()
        if app:
            import uvicorn
            uvicorn.run(app, host="0.0.0.0", port=args.port)
        else:
            # Fallback to direct monitoring
            monitor = UnifiedAlphaMonitor()
            monitor.run()
    else:
        monitor = UnifiedAlphaMonitor()
        monitor.run()


if __name__ == "__main__":
    main()

