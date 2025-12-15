"""
Pipeline Orchestrator - Main Coordinator

Replaces UnifiedAlphaMonitor (1951 lines) with clean orchestration.
Coordinates ALL components without mixing responsibilities.
"""

import logging
import time
import os
import requests
import hashlib
import re
from datetime import datetime, time as dt_time
from typing import Dict, Optional, List

from .config import PipelineConfig
from .components import (
    DPFetcher, SynthesisEngine, AlertManager,
    FedMonitor, TrumpMonitor, EconomicMonitor,
    DPMonitor, SignalBrainMonitor, AlertLogger
)

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """
    Orchestrates the entire monitoring pipeline.
    
    Before: 1951-line monolith with mixed responsibilities
    After: Clean orchestration, delegates to modular components
    """
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        """
        Initialize pipeline orchestrator.
        
        Args:
            config: PipelineConfig (creates default if None)
        """
        self.config = config or PipelineConfig()
        self.running = False
        
        # Alert logger (always initialized)
        self.alert_logger = AlertLogger()
        
        # Alert deduplication tracking
        self.sent_alerts = {}  # alert_hash -> timestamp
        self.alert_cooldown_seconds = 60  # 1 minute cooldown (reduced from 5 min to prevent over-blocking)
        self.alert_stats = {'total': 0, 'sent': 0, 'blocked': 0}  # Track alert statistics
        
        # Alert callback (logs to DB + sends to Discord with deduplication)
        def alert_callback(alert_dict):
            """Handle alert: deduplicate, log to DB, then send to Discord"""
            self.alert_stats['total'] += 1
            
            # Generate unique hash for this alert
            alert_hash = self._generate_alert_hash(alert_dict)
            
            # Check if we've sent this alert recently
            if alert_hash in self.sent_alerts:
                last_sent = self.sent_alerts[alert_hash]
                elapsed = time.time() - last_sent
                if elapsed < self.alert_cooldown_seconds:
                    self.alert_stats['blocked'] += 1
                    logger.info(f"   ⏭️ Alert duplicate (sent {elapsed:.0f}s ago) - skipping: {alert_dict.get('type', 'unknown')} {alert_dict.get('symbol', '')} (hash: {alert_hash[:8]})")
                    return
            
            # New alert - mark as sent
            self.alert_stats['sent'] += 1
            self.sent_alerts[alert_hash] = time.time()
            logger.info(f"   📤 NEW alert: {alert_dict.get('type', 'unknown')} {alert_dict.get('symbol', '')} (hash: {alert_hash[:8]})")
            
            # Cleanup old entries (keep last 100)
            if len(self.sent_alerts) > 100:
                # Remove entries older than 1 hour
                cutoff = time.time() - 3600
                self.sent_alerts = {k: v for k, v in self.sent_alerts.items() if v > cutoff}
            
            # Log to database first
            self.alert_logger.log_alert(
                alert_type=alert_dict.get('type', 'general'),
                embed=alert_dict.get('embed', {}),
                content=alert_dict.get('content'),
                source=alert_dict.get('source', 'monitor'),
                symbol=alert_dict.get('symbol')
            )
            
            # Send to Discord if webhook configured
            if self.config.alerts.discord_webhook:
                try:
                    payload = {"embeds": [alert_dict.get('embed', {})]}
                    if alert_dict.get('content'):
                        payload["content"] = alert_dict['content']
                    requests.post(self.config.alerts.discord_webhook, json=payload, timeout=10)
                    logger.debug(f"   ✅ Alert sent to Discord: {alert_dict.get('type', 'unknown')} {alert_dict.get('symbol', '')}")
                except Exception as e:
                    logger.debug(f"   ⚠️ Discord send failed: {e}")
        
        # Initialize all components
        self._init_components(alert_callback)
        
        # Track last check times
        self.last_checks = {}
        
        # Phase 3: Async monitoring task
        self.monitoring_task = None
        
        logger.info("🚀 PipelineOrchestrator initialized")
        logger.info(f"   DP min_volume: {self.config.dp.min_volume:,}")
        logger.info(f"   Synthesis min_confluence: {self.config.synthesis.min_confluence:.0%}")
        logger.info(f"   Unified mode: {self.config.unified_mode}")
        logger.info(f"   Alert cooldown: {self.alert_cooldown_seconds}s (deduplication enabled)")
    
    def _generate_alert_hash(self, alert_dict):
        """Generate unique hash for alert deduplication
        
        Made more specific to avoid false duplicates:
        - Includes more unique identifiers (prices, levels, timestamps)
        - Different alerts with same type/symbol but different data = different hash
        """
        # Extract key identifying information
        alert_type = alert_dict.get('type', 'unknown')
        symbol = alert_dict.get('symbol', '')
        source = alert_dict.get('source', '')
        
        # Get embed data
        embed = alert_dict.get('embed', {})
        title = embed.get('title', '')
        content = alert_dict.get('content', '')
        
        # Create hash from key fields
        # Include timestamp (rounded to minute) to allow same alert after 1 min
        current_minute = int(time.time() / 60)
        key_data = f"{alert_type}:{symbol}:{source}:{current_minute}"
        
        # Extract unique identifiers from title/content
        if title:
            # Include full title (more specific)
            key_data += f":title:{title[:200]}"
            # Also extract key numbers for price/level matching
            numbers = re.findall(r'\d+\.?\d*', title)
            if numbers:
                key_data += f":nums:{':'.join(numbers[:5])}"  # More numbers
        
        # Add content if it has unique identifiers
        if content:
            # Include more of content for uniqueness
            key_data += f":content:{content[:150]}"
        
        # Add embed fields that uniquely identify the alert
        if 'fields' in embed:
            for field in embed.get('fields', [])[:6]:  # More fields
                field_name = field.get('name', '')
                field_value = str(field.get('value', ''))
                # Include full field value (truncated) for uniqueness
                key_data += f":{field_name}:{field_value[:50]}"
        
        # Add timestamp from embed if available (for more uniqueness)
        if 'timestamp' in embed:
            # Round timestamp to minute for cooldown purposes
            try:
                from datetime import datetime
                ts = embed['timestamp']
                if isinstance(ts, str):
                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    minute_ts = int(dt.timestamp() / 60)
                    key_data += f":ts:{minute_ts}"
            except:
                pass
        
        # Hash it
        return hashlib.md5(key_data.encode()).hexdigest()[:16]
    
    def _init_components(self, alert_callback):
        """Initialize all monitoring components"""
        
        # Fed Monitor
        self.fed_monitor = None
        if self.config.enable_fed:
            try:
                from live_monitoring.agents.fed_watch_monitor import FedWatchMonitor
                from live_monitoring.agents.fed_officials_monitor import FedOfficialsMonitor
                
                fed_watch = FedWatchMonitor(alert_threshold=self.config.fed.alert_threshold)
                fed_officials = FedOfficialsMonitor()
                
                self.fed_monitor = FedMonitor(
                    fed_watch_monitor=fed_watch,
                    fed_officials_monitor=fed_officials,
                    unified_mode=self.config.unified_mode,
                    alert_callback=alert_callback
                )
                logger.info("   ✅ Fed Monitor initialized")
            except Exception as e:
                logger.warning(f"   ⚠️ Fed Monitor failed: {e}")
        
        # Trump Monitor
        self.trump_monitor = None
        if self.config.enable_trump:
            try:
                from live_monitoring.agents.trump_pulse import TrumpPulse
                from live_monitoring.agents.trump_news_monitor import TrumpNewsMonitor
                
                trump_pulse = TrumpPulse()
                trump_news = TrumpNewsMonitor()
                
                self.trump_monitor = TrumpMonitor(
                    trump_pulse=trump_pulse,
                    trump_news_monitor=trump_news,
                    unified_mode=self.config.unified_mode,
                    alert_callback=alert_callback,
                    cooldown_minutes=self.config.trump.cooldown_minutes,
                    min_exploit_score=self.config.trump.min_exploit_score
                )
                logger.info("   ✅ Trump Monitor initialized")
            except Exception as e:
                logger.warning(f"   ⚠️ Trump Monitor failed: {e}")
        
        # Economic Monitor
        self.economic_monitor = None
        if self.config.enable_economic:
            try:
                from live_monitoring.agents.economic import EconomicIntelligenceEngine
                
                econ_engine = EconomicIntelligenceEngine()
                
                # EconomicMonitor now handles Trading Economics internally
                # PRIMARY: Trading Economics (with forecast/previous)
                # FALLBACK 1: EventLoader (Baby-Pips API)
                # FALLBACK 2: Static EconomicCalendar
                self.economic_monitor = EconomicMonitor(
                    econ_engine=econ_engine,
                    unified_mode=self.config.unified_mode,
                    alert_callback=alert_callback,
                    fed_watch_prob=89.0  # Will be updated from Fed Monitor
                )
                
                # Phase 3: Connect monitors for pre-event analyzer
                if self.economic_monitor.pre_event_analyzer:
                    if self.fed_monitor:
                        self.economic_monitor.set_fed_watch_monitor(self.fed_monitor)
                    if self.dp_monitor:
                        self.economic_monitor.set_dp_monitor(self.dp_monitor)
                
                logger.info("   ✅ Economic Monitor initialized (Trading Economics PRIMARY + Phase 3)")
            except Exception as e:
                logger.warning(f"   ⚠️ Economic Monitor failed: {e}")
        
        # DP Monitor
        self.dp_monitor = None
        if self.config.enable_dp:
            try:
                from live_monitoring.agents.dp_monitor import DPMonitorEngine
                from live_monitoring.agents.dp_learning import DPLearningEngine
                
                api_key = os.getenv('CHARTEXCHANGE_API_KEY')
                if api_key:
                    dp_monitor_engine = DPMonitorEngine(
                        api_key=api_key,
                        debounce_minutes=self.config.dp.debounce_minutes
                    )
                    
                    dp_learning_engine = None
                    try:
                        dp_learning_engine = DPLearningEngine()
                        dp_learning_engine.start()
                    except Exception as e:
                        logger.warning(f"   ⚠️ DP Learning Engine failed: {e}")
                    
                    self.dp_monitor = DPMonitor(
                        dp_monitor_engine=dp_monitor_engine,
                        dp_learning_engine=dp_learning_engine,
                        symbols=self.config.symbols,
                        unified_mode=self.config.unified_mode,
                        alert_callback=alert_callback
                    )
                    logger.info("   ✅ DP Monitor initialized")
            except Exception as e:
                logger.warning(f"   ⚠️ DP Monitor failed: {e}")
        
        # Signal Brain Monitor
        self.signal_brain_monitor = None
        if self.config.enable_signal_brain:
            try:
                from live_monitoring.agents.signal_brain import SignalBrainEngine
                from live_monitoring.agents.signal_brain.macro import MacroContextProvider
                
                signal_brain = SignalBrainEngine()
                
                macro_provider = None
                try:
                    macro_provider = MacroContextProvider(
                        fed_watch=self.fed_monitor.fed_watch if self.fed_monitor else None,
                        fed_officials=self.fed_monitor.fed_officials if self.fed_monitor else None,
                        economic_engine=self.economic_monitor.econ_engine if self.economic_monitor else None,
                        economic_calendar=self.economic_monitor.econ_calendar if self.economic_monitor else None,
                        trump_monitor=self.trump_monitor.trump_pulse if self.trump_monitor else None,
                    )
                except Exception as e:
                    logger.warning(f"   ⚠️ MacroProvider failed: {e}")
                
                self.signal_brain_monitor = SignalBrainMonitor(
                    signal_brain_engine=signal_brain,
                    macro_provider=macro_provider,
                    unified_mode=self.config.unified_mode,
                    alert_callback=alert_callback
                )
                logger.info("   ✅ Signal Brain Monitor initialized")
            except Exception as e:
                logger.warning(f"   ⚠️ Signal Brain Monitor failed: {e}")
    
    def _is_market_hours(self) -> bool:
        """Check if currently in RTH (9:30 AM - 4:00 PM ET, Mon-Fri)"""
        now = datetime.now()
        current_time = now.time()
        
        market_open = dt_time(9, 30)
        market_close = dt_time(16, 0)
        
        is_weekday = now.weekday() < 5
        in_hours = market_open <= current_time < market_close
        
        return is_weekday and in_hours
    
    def _should_check(self, component: str) -> bool:
        """Check if component should run based on interval"""
        if component not in self.last_checks:
            return True
        
        interval_map = {
            'fed': self.config.intervals.fed_watch,
            'trump': self.config.intervals.trump_intel,
            'economic': self.config.intervals.economic,
            'dp': self.config.intervals.dark_pool,
            'synthesis': self.config.intervals.synthesis,
        }
        
        interval = interval_map.get(component, 60)
        elapsed = time.time() - self.last_checks[component]
        return elapsed >= interval
    
    def _should_check_pending(self) -> bool:
        """Check if pending events should be checked (every 15 min)"""
        key = 'pending_events'
        if key not in self.last_checks:
            self.last_checks[key] = 0
            return True
        
        elapsed = time.time() - self.last_checks[key]
        if elapsed >= 900:  # 15 minutes
            self.last_checks[key] = time.time()
            return True
        return False
    
    def run(self):
        """Run the monitoring pipeline"""
        self.running = True
        logger.info("=" * 70)
        logger.info("🎯 ALPHA INTELLIGENCE - MODULAR PIPELINE STARTED")
        logger.info("=" * 70)
        
        # Send startup alert
        self._send_startup_alert()
        
        # Phase 3: Start async release monitoring
        if self.economic_monitor and self.economic_monitor.surprise_detector:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is already running, create task
                    self.monitoring_task = asyncio.create_task(
                        self.economic_monitor.start_release_monitoring()
                    )
                else:
                    # If no loop, run in background thread
                    import threading
                    def run_monitoring():
                        asyncio.run(self.economic_monitor.start_release_monitoring())
                    thread = threading.Thread(target=run_monitoring, daemon=True)
                    thread.start()
                logger.info("   🚀 Release monitoring started (Phase 3)")
            except Exception as e:
                logger.warning(f"   ⚠️ Failed to start release monitoring: {e}")
        
        try:
            while self.running:
                cycle_start = time.time()
                now = datetime.now()
                
                # Check Fed (every 5 min)
                if self.fed_monitor and self._should_check('fed'):
                    result = self.fed_monitor.check()
                    self.last_checks['fed'] = time.time()
                    
                    # Update Economic Monitor with Fed Watch prob
                    if self.economic_monitor and result.get('status'):
                        self.economic_monitor.update_fed_watch_prob(result['status'].prob_cut)
                
                # Check Trump (every 3 min)
                if self.trump_monitor and self._should_check('trump'):
                    self.trump_monitor.check()
                    self.last_checks['trump'] = time.time()
                
                # Check Economics (every hour for discovery)
                if self.economic_monitor and self._should_check('economic'):
                    # Main check for events
                    result = self.economic_monitor.check()
                    
                    # Discover new events (hourly)
                    self.economic_monitor.discover_upcoming_events(hours_ahead=24)
                    
                    self.last_checks['economic'] = time.time()
                
                # Check Pending Events (every 15 min for 4h alerts)
                if self.economic_monitor and self._should_check_pending():
                    pending_alerts = self.economic_monitor.check_pending_events()
                    if pending_alerts:
                        logger.info(f"   📊 Generated {len(pending_alerts)} pre-event alerts")
                
                # Check if market is open
                is_market_hours = self._is_market_hours()
                
                # Check Dark Pools (every 60 sec) - ONLY DURING RTH
                if is_market_hours and self.dp_monitor and self._should_check('dp'):
                    result = self.dp_monitor.check()
                    self.last_checks['dp'] = time.time()
                    
                    # Trigger synthesis if we have buffered alerts
                    if result.get('buffered') and len(result['buffered']) >= 2:
                        if self.signal_brain_monitor and self._should_check('synthesis'):
                            self._run_synthesis(result['buffered'])
                            self.last_checks['synthesis'] = time.time()
                
                # Run synthesis (every 60 sec) - ONLY DURING RTH
                if is_market_hours and self.signal_brain_monitor and self._should_check('synthesis'):
                    # Get buffered alerts from DP Monitor
                    buffered = self.dp_monitor.get_buffered_alerts() if self.dp_monitor else []
                    if buffered:
                        self._run_synthesis(buffered)
                        self.last_checks['synthesis'] = time.time()
                
                # Sleep until next cycle
                cycle_time = time.time() - cycle_start
                sleep_time = max(0, 30 - cycle_time)  # 30 second base cycle
                time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            logger.info("⏹️  Pipeline stopped by user")
        except Exception as e:
            logger.error(f"❌ Pipeline error: {e}", exc_info=True)
        finally:
            self.running = False
    
    def _run_synthesis(self, dp_alerts: List):
        """Run signal synthesis"""
        try:
            # Get current prices
            import yfinance as yf
            spy_price = 0.0
            qqq_price = 0.0
            
            for symbol in ['SPY', 'QQQ']:
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period='1d', interval='1m')
                    if not hist.empty:
                        price = float(hist['Close'].iloc[-1])
                        if symbol == 'SPY':
                            spy_price = price
                        else:
                            qqq_price = price
                except:
                    continue
            
            # Run synthesis
            result = self.signal_brain_monitor.synthesize(
                dp_alerts=dp_alerts,
                spy_price=spy_price,
                qqq_price=qqq_price
            )
            
            # Clear buffer if synthesis sent
            if result.get('should_send') and result.get('alert'):
                if self.dp_monitor:
                    self.dp_monitor.clear_buffer()
            
        except Exception as e:
            logger.error(f"   ❌ Synthesis failed: {e}", exc_info=True)
    
    def _send_startup_alert(self):
        """Send startup notification"""
        try:
            embed = {
                "title": "🎯 ALPHA INTELLIGENCE - ONLINE",
                "color": 3066993,
                "description": "Modular pipeline started - ALL components initialized",
                "fields": [
                    {"name": "🏦 Fed Monitor", "value": "✅ Active" if self.fed_monitor else "❌ Disabled", "inline": True},
                    {"name": "🎯 Trump Monitor", "value": "✅ Active" if self.trump_monitor else "❌ Disabled", "inline": True},
                    {"name": "📊 Economic Monitor", "value": "✅ Active" if self.economic_monitor else "❌ Disabled", "inline": True},
                    {"name": "🔒 DP Monitor", "value": "✅ Active" if self.dp_monitor else "❌ Disabled", "inline": True},
                    {"name": "🧠 Signal Brain", "value": "✅ Active" if self.signal_brain_monitor else "❌ Disabled", "inline": True},
                    {"name": "📝 Alert Logger", "value": "✅ Active", "inline": True},
                ],
                "footer": {"text": "Modular Pipeline | All components separated"},
                "timestamp": datetime.utcnow().isoformat()
            }
            
            alert_dict = {
                'type': 'startup',
                'embed': embed,
                'content': None,
                'source': 'orchestrator',
                'symbol': None
            }
            
            # Log and send
            self.alert_logger.log_alert(**{
                'alert_type': alert_dict['type'],
                'embed': alert_dict['embed'],
                'content': alert_dict.get('content'),
                'source': alert_dict['source'],
                'symbol': alert_dict.get('symbol')
            })
            
            if self.config.alerts.discord_webhook:
                try:
                    payload = {"embeds": [embed]}
                    requests.post(self.config.alerts.discord_webhook, json=payload, timeout=10)
                except:
                    pass
                    
        except Exception as e:
            logger.debug(f"Startup alert failed: {e}")
    
    def stop(self):
        """Stop the pipeline"""
        self.running = False
        logger.info("⏹️  Pipeline stopping...")
