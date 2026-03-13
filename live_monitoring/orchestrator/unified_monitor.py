"""
🎯 UNIFIED ALPHA MONITOR (MODULAR VERSION)

Master orchestrator that delegates to modular components:
- AlertManager: Alert sending/deduplication
- RegimeDetector: Market regime detection
- MomentumDetector: Selloff/rally detection
- MonitorInitializer: Component initialization
- ExploitationManager: Squeeze/Gamma/Scanner/FTD/Reddit init
- CheckerScheduler: Interval-based checker dispatch
- OvernightManager: Post-market/overnight intelligence
"""

import os
import sys
import time
import logging
import threading
from collections import deque
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Callable

# Add paths
base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, base_path)

from .alert_manager import AlertManager
from .regime_detector import RegimeDetector
from .momentum_detector import MomentumDetector
from .monitor_initializer import MonitorInitializer
from .checker_health import CheckerHealthRegistry
from .exploitation_manager import ExploitationManager
from .checker_scheduler import CheckerScheduler
from .overnight_manager import OvernightManager
from .confluence_gate import ConfluenceGate
from .gate_outcome_tracker import GateOutcomeTracker
from .morning_brief import MorningBriefGenerator
from .checkers import (
    FedChecker,
    TrumpChecker,
    EconomicChecker,
    DarkPoolChecker,
    SynthesisChecker,
    NarrativeChecker,
    TradyticsChecker,
    SqueezeChecker,
    GammaChecker,
    ScannerChecker,
    FTDChecker,
    DailyRecapChecker,
    RedditChecker,
    PreMarketGapChecker,
    OptionsFlowChecker,
    NewsIntelligenceChecker,
    DPDivergenceChecker,
    EarningsChecker,
)

logger = logging.getLogger(__name__)


class UnifiedAlphaMonitor:
    """
    Master orchestrator for all monitoring systems (MODULAR VERSION).

    Delegates to:
    - ExploitationManager: Squeeze/Gamma/Scanner/FTD/Reddit init
    - CheckerScheduler: Interval-based checker dispatch
    - OvernightManager: Post-market/overnight intelligence
    - AlertManager: Discord alerting + dedup
    - RegimeDetector: Market regime classification
    - MomentumDetector: Selloff/rally detection
    """

    def __init__(self):
        self.running = True
        self.symbols = ['SPY', 'QQQ']

        # Intervals (in seconds) — Render free tier optimized
        self.fed_interval = 900
        self.trump_interval = 600
        self.econ_interval = 3600
        self.dp_interval = 300
        self.synthesis_interval = 300
        self.squeeze_interval = 3600
        self.reddit_interval = 3600
        self.premarket_gap_interval = 600
        self.options_flow_interval = 1800
        self.overnight_interval = 7200
        self.last_overnight_check = None

        # Core components
        self.alert_manager = AlertManager()
        self.regime_detector = RegimeDetector()
        self.health_registry = CheckerHealthRegistry()

        # State tracking
        self.prev_fed_status = None
        self.prev_trump_sentiment = None
        self.seen_fed_comments = set()
        self.seen_trump_news = set()
        self.alerted_events = set()
        self.recent_dp_alerts = []
        self.startup_alert_sent = False
        self.last_synthesis_sent = None
        self.last_narrative_sent = None
        self._last_level_directions = {}

        # 🔥 Signal buffer: stores recent LiveSignal objects for API retrieval.
        # TTL-based: signals older than 60 minutes are pruned on read.
        self._signal_buffer: deque = deque(maxlen=200)
        self._signal_lock = threading.Lock()
        self._last_regime_details = {}

        # Initialize monitors (sets up Fed, Trump, DP, Brain, Narrative, Econ)
        self._init_monitors()

        # Initialize exploitation modules (Squeeze, Gamma, Scanner, FTD, Reddit)
        self.exploitation = ExploitationManager(dp_client=getattr(self, 'dp_client', None))
        self._expose_exploitation_attrs()

        # Initialize momentum detector
        self.momentum_detector = MomentumDetector(
            signal_generator=getattr(self, 'signal_generator', None),
            institutional_engine=getattr(self, 'institutional_engine', None)
        )

        # Initialize checkers and scheduler
        self._init_checkers()
        self._init_scheduler()

        # Initialize overnight manager
        self.overnight = OvernightManager(
            send_discord=self.send_discord,
            run_checker_with_health=self._run_checker_with_health,
            trump_checker=self.trump_checker,
            news_intelligence_checker=self.news_intelligence_checker,
            gamma_tracker=self.exploitation.gamma_tracker,
            symbols=self.symbols,
            gamma_enabled=self.exploitation.gamma_enabled,
            squeeze_enabled=self.exploitation.squeeze_enabled,
        )

        logger.info("=" * 70)
        logger.info("🎯 ALPHA INTELLIGENCE - UNIFIED MONITOR STARTED (MODULAR)")
        logger.info("=" * 70)

    # ═══════════════════════════════════════════════════════════════
    # INITIALIZATION
    # ═══════════════════════════════════════════════════════════════

    def _init_monitors(self):
        """Initialize all monitor components using MonitorInitializer."""
        initializer = MonitorInitializer(on_dp_outcome=self._on_dp_outcome)
        status = initializer.initialize_all()

        fed_status = status.get('fed', {})
        self.fed_enabled = fed_status.get('enabled', False)
        self.fed_watch = fed_status.get('fed_watch')
        self.fed_officials = fed_status.get('fed_officials')

        trump_status = status.get('trump', {})
        self.trump_enabled = trump_status.get('enabled', False)
        self.trump_pulse = trump_status.get('trump_pulse')
        self.trump_news = trump_status.get('trump_news')

        dp_status = status.get('dark_pool', {})
        self.dp_enabled = dp_status.get('enabled', False)
        self.dp_client = dp_status.get('dp_client')
        self.dp_engine = dp_status.get('dp_engine')

        learning_status = status.get('dp_learning', {})
        self.dp_learning_enabled = learning_status.get('enabled', False)
        self.dp_learning = learning_status.get('dp_learning')

        monitor_status = status.get('dp_monitor_engine', {})
        self.dp_monitor_engine = monitor_status.get('dp_monitor_engine')

        brain_status = status.get('signal_brain', {})
        self.brain_enabled = brain_status.get('enabled', False)
        self.signal_brain = brain_status.get('signal_brain')
        self.macro_provider = brain_status.get('macro_provider')
        self.unified_mode = brain_status.get('enabled', False)

        narrative_status = status.get('narrative_brain', {})
        self.narrative_enabled = narrative_status.get('enabled', False)
        self.narrative_brain = narrative_status.get('narrative_brain')
        self.narrative_scheduler = narrative_status.get('narrative_scheduler')

        econ_status = status.get('economic', {})
        self.econ_enabled = econ_status.get('enabled', False)
        self.econ_engine = econ_status.get('econ_engine')
        self.econ_calendar = econ_status.get('econ_calendar')
        self.econ_calendar_type = econ_status.get('econ_calendar_type')

        tradytics_status = status.get('tradytics', {})
        self.tradytics_llm_available = tradytics_status.get('llm_available', False)
        self.tradytics_analysis_interval = 300

        # Initialize signal generator for momentum detection
        try:
            from live_monitoring.core.signal_generator import SignalGenerator
            api_key = os.getenv('CHARTEXCHANGE_API_KEY')
            self.signal_generator = SignalGenerator(api_key=api_key)
            self.momentum_detector = MomentumDetector(
                signal_generator=self.signal_generator,
                institutional_engine=self.dp_engine
            )
        except Exception as e:
            logger.warning(f"   ⚠️ SignalGenerator not available: {e}")
            self.signal_generator = None

        self.institutional_engine = self.dp_engine

        logger.info(f"   Fed: {'✅' if self.fed_enabled else '❌'}")
        logger.info(f"   Trump: {'✅' if self.trump_enabled else '❌'}")
        logger.info(f"   Economic: {'✅' if self.econ_enabled else '❌'}")
        logger.info(f"   Dark Pool: {'✅' if self.dp_enabled else '❌'}")
        logger.info(f"   Signal Brain: {'✅' if self.brain_enabled else '❌'}")
        logger.info(f"   Narrative Brain: {'✅' if self.narrative_enabled else '❌'}")

    def _expose_exploitation_attrs(self):
        """Expose exploitation manager attributes for checker init compatibility."""
        self.squeeze_enabled = self.exploitation.squeeze_enabled
        self.squeeze_detector = self.exploitation.squeeze_detector
        self.gamma_enabled = self.exploitation.gamma_enabled
        self.gamma_tracker = self.exploitation.gamma_tracker
        self.scanner_enabled = self.exploitation.scanner_enabled
        self.opportunity_scanner = self.exploitation.opportunity_scanner
        self.ftd_enabled = self.exploitation.ftd_enabled
        self.ftd_analyzer = self.exploitation.ftd_analyzer
        self.reddit_enabled = self.exploitation.reddit_enabled
        self.reddit_exploiter = self.exploitation.reddit_exploiter
        self.squeeze_candidates = self.exploitation.squeeze_candidates
        self.ftd_candidates = self.exploitation.ftd_candidates

    def _init_checkers(self):
        """Initialize all checker modules."""
        logger.info("🔧 Initializing checker modules...")

        self.fed_checker = FedChecker(
            alert_manager=self.alert_manager, fed_watch=self.fed_watch,
            fed_officials=self.fed_officials, unified_mode=self.unified_mode
        ) if self.fed_enabled else None

        self.trump_checker = TrumpChecker(
            alert_manager=self.alert_manager, trump_pulse=self.trump_pulse,
            trump_news=self.trump_news, unified_mode=self.unified_mode
        ) if self.trump_enabled else None

        self.economic_checker = EconomicChecker(
            alert_manager=self.alert_manager, econ_calendar=self.econ_calendar,
            econ_engine=self.econ_engine, econ_calendar_type=self.econ_calendar_type,
            prev_fed_status=self.prev_fed_status, unified_mode=self.unified_mode
        ) if self.econ_enabled else None

        self.dp_checker = DarkPoolChecker(
            alert_manager=self.alert_manager, dp_monitor_engine=self.dp_monitor_engine,
            symbols=self.symbols, unified_mode=self.unified_mode,
            on_synthesis_trigger=lambda: None
        ) if self.dp_enabled else None

        self.synthesis_checker = SynthesisChecker(
            alert_manager=self.alert_manager, signal_brain=self.signal_brain,
            macro_provider=self.macro_provider, unified_mode=self.unified_mode
        ) if self.brain_enabled else None

        self.narrative_checker = NarrativeChecker(
            alert_manager=self.alert_manager, narrative_brain=self.narrative_brain,
            regime_detector=self.regime_detector, dp_monitor_engine=self.dp_monitor_engine,
            unified_mode=self.unified_mode
        ) if self.narrative_enabled else None

        self.tradytics_checker = TradyticsChecker(
            alert_manager=self.alert_manager, tradytics_llm_available=self.tradytics_llm_available,
            tradytics_analysis_interval=self.tradytics_analysis_interval, unified_mode=self.unified_mode
        ) if self.tradytics_llm_available else None

        # ─── SHARED CONFLUENCE GATE (one instance, all checkers) ──────
        self.confluence_gate = ConfluenceGate(
            regime_detector=self.regime_detector,
        )

        # Outcome tracker (logs signals, settles after close)
        self.outcome_tracker = GateOutcomeTracker()

        # Morning brief generator
        self.morning_brief = MorningBriefGenerator(
            confluence_gate=self.confluence_gate,
            regime_detector=self.regime_detector,
            gamma_tracker=self.gamma_tracker if self.gamma_enabled else None,
            outcome_tracker=self.outcome_tracker,
            send_discord=self.send_discord,
        )

        self.squeeze_checker = SqueezeChecker(
            alert_manager=self.alert_manager, squeeze_detector=self.squeeze_detector,
            opportunity_scanner=self.opportunity_scanner, squeeze_candidates=self.squeeze_candidates,
            unified_mode=self.unified_mode,
            confluence_gate=self.confluence_gate,
        ) if self.squeeze_enabled else None

        gamma_exposure_tracker = None
        if hasattr(self, 'signal_generator') and hasattr(self.signal_generator, 'gamma_tracker'):
            gamma_exposure_tracker = self.signal_generator.gamma_tracker

        self.gamma_checker = GammaChecker(
            alert_manager=self.alert_manager, gamma_tracker=self.gamma_tracker,
            gamma_exposure_tracker=gamma_exposure_tracker, symbols=self.symbols,
            unified_mode=self.unified_mode,
            confluence_gate=self.confluence_gate,
        ) if self.gamma_enabled else None

        self.scanner_checker = ScannerChecker(
            alert_manager=self.alert_manager, opportunity_scanner=self.opportunity_scanner,
            squeeze_detector=self.squeeze_detector, unified_mode=self.unified_mode
        ) if self.scanner_enabled else None

        self.ftd_checker = FTDChecker(
            alert_manager=self.alert_manager, ftd_analyzer=self.ftd_analyzer,
            ftd_candidates=self.ftd_candidates, unified_mode=self.unified_mode
        ) if self.ftd_enabled else None

        self.daily_recap_checker = DailyRecapChecker(
            alert_manager=self.alert_manager, gamma_tracker=self.gamma_tracker,
            symbols=self.symbols, squeeze_enabled=self.squeeze_enabled,
            gamma_enabled=self.gamma_enabled, unified_mode=self.unified_mode
        )

        api_key = os.getenv('CHARTEXCHANGE_API_KEY') or os.getenv('CHART_EXCHANGE_API_KEY')

        self.reddit_checker = RedditChecker(
            alert_manager=self.alert_manager, reddit_exploiter=self.reddit_exploiter,
            api_key=api_key
        ) if self.reddit_enabled else None

        self.premarket_gap_checker = PreMarketGapChecker(
            alert_manager=self.alert_manager, api_key=api_key, unified_mode=self.unified_mode
        )

        rapidapi_key = os.getenv('YAHOO_RAPIDAPI_KEY')

        self.options_flow_checker = OptionsFlowChecker(
            alert_manager=self.alert_manager, api_key=rapidapi_key, unified_mode=self.unified_mode,
            confluence_gate=self.confluence_gate,
        )

        self.news_intelligence_checker = NewsIntelligenceChecker(
            alert_manager=self.alert_manager, api_key=rapidapi_key, unified_mode=self.unified_mode
        )

        # DP Divergence Checker (Phase 7)
        from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
        from core.data.rapidapi_options_client import RapidAPIOptionsClient

        chartexchange_client = UltimateChartExchangeClient(api_key=api_key) if api_key else None
        options_client = RapidAPIOptionsClient(
            api_key=rapidapi_key
        ) if rapidapi_key else None

        self.dp_divergence_checker = DPDivergenceChecker(
            alert_manager=self.alert_manager, chartexchange_client=chartexchange_client,
            options_client=options_client, symbols=self.symbols,
            unified_mode=self.unified_mode,
            learning_engine=self.dp_learning if self.dp_learning_enabled else None
        ) if (api_key and rapidapi_key) else None

        # Earnings Checker (Phase 8)
        self.earnings_checker = EarningsChecker(
            alert_manager=self.alert_manager, unified_mode=self.unified_mode
        )

        logger.info("   ✅ All checkers initialized (Phase 1-8)")

    def _init_scheduler(self):
        """Register all checkers with the scheduler."""
        self.scheduler = CheckerScheduler(
            run_checker_with_health=self._run_checker_with_health,
            send_discord=self.send_discord,
        )

        # Standard checkers (simple run-and-dispatch)
        self.scheduler.register('fed', self.fed_checker, self.fed_interval, requires_market_hours=False)
        self.scheduler.register('trump', self.trump_checker, self.trump_interval, requires_market_hours=False)
        self.scheduler.register('economic', self.economic_checker, self.econ_interval, requires_market_hours=False)
        self.scheduler.register('dark_pool', self.dp_checker, self.dp_interval)
        self.scheduler.register('squeeze', self.squeeze_checker, self.squeeze_interval)
        self.scheduler.register('gamma', self.gamma_checker, 3600)
        self.scheduler.register('scanner', self.scanner_checker, 3600)
        self.scheduler.register('ftd', self.ftd_checker, 3600)
        self.scheduler.register('reddit', self.reddit_checker, self.reddit_interval)
        self.scheduler.register('premarket_gap', self.premarket_gap_checker, self.premarket_gap_interval, requires_market_hours=False, run_immediately=True)
        self.scheduler.register('options_flow', self.options_flow_checker, self.options_flow_interval, run_immediately=True)
        self.scheduler.register('news_intelligence', self.news_intelligence_checker, 1800, run_immediately=True)
        self.scheduler.register('dp_divergence', self.dp_divergence_checker, self.dp_interval, run_immediately=True)
        self.scheduler.register('earnings', self.earnings_checker, 3600 * 4, requires_market_hours=False, run_immediately=True)

        # Custom-handler checkers (need special logic)
        self.scheduler.register('synthesis', self.synthesis_checker, self.synthesis_interval,
                                custom_handler=self._handle_synthesis_narrative)
        self.scheduler.register('tradytics', self.tradytics_checker, self.tradytics_analysis_interval,
                                custom_handler=self._handle_tradytics)

        # Set initial timers (prevent all from firing on first loop)
        now = datetime.now()
        self.scheduler.reset_timers(now, set_initial=[
            'fed', 'trump', 'economic', 'dark_pool', 'squeeze', 'gamma', 'reddit',
        ])

        logger.info(f"   ⏱️ Scheduler initialized with {self.scheduler.checker_count} checkers")

    # ═══════════════════════════════════════════════════════════════
    # ALERT METHODS
    # ═══════════════════════════════════════════════════════════════

    def send_discord(self, embed: dict, content: str = None, alert_type: str = "general",
                     source: str = "monitor", symbol: str = None):
        """Send Discord notification (delegates to AlertManager).
        
        Checks thesis_valid from intraday snapshot. If thesis is invalid,
        directional signal alerts get a prominent ⚠️ warning prepended.
        """
        # ── Thesis check: warn on directional alerts when thesis is invalid ──
        _directional_types = {"selloff", "rally", "dp_divergence", "narrative_brain",
                              "gamma_flip", "squeeze", "options_flow", "signal"}
        if alert_type in _directional_types:
            try:
                import json as _json, os as _os
                _snap_path = "/tmp/intraday_snapshot.json"
                if _os.path.exists(_snap_path):
                    with open(_snap_path) as _f:
                        _snap = _json.load(_f)
                    if _snap.get("market_open") and not _snap.get("thesis_valid", True):
                        _reason = _snap.get("thesis_invalidation_reason", "Thesis invalidated")
                        # Prepend warning to embed and content
                        embed["title"] = f"⚠️ THESIS INVALID | {embed.get('title', '')}"
                        embed.setdefault("fields", []).insert(0, {
                            "name": "🚨 THESIS WARNING",
                            "value": _reason,
                            "inline": False,
                        })
                        if content:
                            content = f"⚠️ THESIS INVALID — {_reason} | {content}"
                        logger.warning(f"⚠️ Thesis invalid but alert firing: {alert_type} {symbol}")
            except Exception:
                pass  # Don't block alert delivery on snapshot read failure
        return self.alert_manager.send_discord(embed, content, alert_type, source, symbol)

    def _log_alert_to_database(self, alert_type: str, embed: dict, content: str = None,
                               source: str = "monitor", symbol: str = None):
        """Log alert to database (delegates to AlertManager)."""
        self.alert_manager._log_alert_to_database(alert_type, embed, content, source, symbol)

    # ═══════════════════════════════════════════════════════════════
    # REGIME DETECTION
    # ═══════════════════════════════════════════════════════════════

    def _detect_market_regime(self, current_price: float):
        """Detect market regime (delegates to RegimeDetector)."""
        result = self.regime_detector.detect(current_price)
        if result.get('regime_changed'):
            logger.info(f"   📊 Regime change: {result.get('regime')}")
        return result.get('regime', 'NEUTRAL')

    # ═══════════════════════════════════════════════════════════════
    # SIGNAL BUFFER (API reads from this)
    # ═══════════════════════════════════════════════════════════════

    def get_active_signals(self, max_age_minutes: int = 60) -> List:
        """Return recent signals younger than max_age_minutes.
        Called by the /signals API endpoint."""
        cutoff = datetime.now() - timedelta(minutes=max_age_minutes)
        with self._signal_lock:
            # Prune expired
            while self._signal_buffer and self._signal_buffer[0].timestamp < cutoff:
                self._signal_buffer.popleft()
            return list(self._signal_buffer)

    def _store_signal(self, signal) -> None:
        """Thread-safe append a LiveSignal to the buffer."""
        with self._signal_lock:
            self._signal_buffer.append(signal)

    # ═══════════════════════════════════════════════════════════════
    # MOMENTUM DETECTION (delegates to MomentumDetector)
    # ═══════════════════════════════════════════════════════════════

    def _check_selloffs(self):
        """Check for selloffs (delegates to MomentumDetector)."""
        try:
            selloff_signals = self.momentum_detector.check_selloffs(self.symbols)
            alert_count = 0
            for item in selloff_signals:
                symbol = item['symbol']
                signal = item['signal']
                current_price = item['current_price']
                embed = {
                    "title": f"🚨 **REAL-TIME SELLOFF** - {symbol}",
                    "description": signal.rationale or "Rapid price drop with volume spike detected",
                    "color": 0xff0000,
                    "fields": [{"name": "🎯 Trade Setup", "value": (
                        f"**Action:** {signal.action.value}\n**Entry:** ${signal.entry_price:.2f}\n"
                        f"**Stop:** ${signal.stop_price:.2f}\n**Target:** ${signal.target_price:.2f}\n"
                        f"**Confidence:** {signal.confidence:.0%}"
                    ), "inline": False}],
                    "footer": {"text": "Real-time momentum detection"},
                    "timestamp": datetime.now().isoformat()
                }
                content = f"🚨 **REAL-TIME SELLOFF** | {symbol} | {signal.action.value} @ ${current_price:.2f}"
                market_regime = self._detect_market_regime(current_price)
                if market_regime in ["DOWNTREND", "STRONG_DOWNTREND"] and signal.action.value == "LONG":
                    logger.warning(f"   ⛔ REGIME FILTER: Blocking LONG selloff signal in {market_regime}")
                    continue
                self._store_signal(signal)  # 🔥 Store before discarding
                self.send_discord(embed, content=content, alert_type="selloff", source="selloff_detector", symbol=symbol)
                alert_count += 1
                self.health_registry.record_alert('selloff_rally', 'selloff', symbol, signal.action.value, signal.entry_price)
            self.health_registry.record_run('selloff_rally', success=True, alerts_generated=alert_count)
        except Exception as e:
            logger.error(f"❌ selloff detection failed: {e}")
            self.health_registry.record_run('selloff_rally', success=False, error=str(e))

    def _check_rallies(self):
        """Check for rallies (delegates to MomentumDetector)."""
        try:
            rally_signals = self.momentum_detector.check_rallies(self.symbols)
            alert_count = 0
            for item in rally_signals:
                symbol = item['symbol']
                signal = item['signal']
                current_price = item['current_price']
                embed = {
                    "title": f"🚀 **REAL-TIME RALLY** - {symbol}",
                    "description": signal.rationale or "Rapid price rise with volume spike detected",
                    "color": 0x00ff00,
                    "fields": [{"name": "🎯 Trade Setup", "value": (
                        f"**Action:** {signal.action.value}\n**Entry:** ${signal.entry_price:.2f}\n"
                        f"**Stop:** ${signal.stop_price:.2f}\n**Target:** ${signal.target_price:.2f}\n"
                        f"**Confidence:** {signal.confidence:.0%}"
                    ), "inline": False}],
                    "footer": {"text": "Real-time momentum detection"},
                    "timestamp": datetime.now().isoformat()
                }
                content = f"🚀 **REAL-TIME RALLY** | {symbol} | {signal.action.value} @ ${current_price:.2f}"
                market_regime = self._detect_market_regime(current_price)
                if market_regime in ["UPTREND", "STRONG_UPTREND"] and signal.action.value == "SELL":
                    logger.warning(f"   ⛔ REGIME FILTER: Blocking SHORT rally signal in {market_regime}")
                    continue
                if market_regime == "STRONG_DOWNTREND" and signal.action.value == "BUY":
                    logger.warning(f"   ⛔ REGIME FILTER: Blocking BUY rally signal in {market_regime} (don't chase)")
                    continue
                self._store_signal(signal)  # 🔥 Store before discarding
                self.send_discord(embed, content=content, alert_type="rally", source="rally_detector", symbol=symbol)
                alert_count += 1
                self.health_registry.record_alert('selloff_rally', 'rally', symbol, signal.action.value, signal.entry_price)
            self.health_registry.record_run('selloff_rally', success=True, alerts_generated=alert_count)
        except Exception as e:
            logger.error(f"❌ rally detection failed: {e}")
            self.health_registry.record_run('selloff_rally', success=False, error=str(e))

    # ═══════════════════════════════════════════════════════════════
    # CUSTOM CHECKER HANDLERS (for checkers needing special logic)
    # ═══════════════════════════════════════════════════════════════

    def _handle_synthesis_narrative(self, now: datetime, is_market_hours: bool) -> int:
        """Custom handler for synthesis + narrative checkers (they chain together)."""
        if not is_market_hours or not self.synthesis_checker:
            return 0

        alert_count = 0
        try:
            # Get prices
            spy_price, qqq_price = self._get_current_prices()

            alerts, synthesis_result = self.synthesis_checker.check(
                recent_dp_alerts=self.recent_dp_alerts,
                spy_price=spy_price, qqq_price=qqq_price
            )
            self.health_registry.record_run('synthesis', success=True, alerts_generated=len(alerts))
            for alert in alerts:
                self.health_registry.record_alert('synthesis', getattr(alert, 'alert_type', None), getattr(alert, 'symbol', None))
                self.send_discord(alert.embed, alert.content, alert.alert_type, alert.source, alert.symbol)
                alert_count += 1

            # Chain: narrative needs synthesis result
            if synthesis_result and self.narrative_checker:
                narrative_alerts = self.narrative_checker.check(
                    recent_dp_alerts=self.recent_dp_alerts,
                    synthesis_result=synthesis_result,
                    spy_price=spy_price, qqq_price=qqq_price
                )
                for alert in narrative_alerts:
                    self.send_discord(alert.embed, alert.content, alert.alert_type, alert.source, alert.symbol)
                    alert_count += 1
                if not narrative_alerts:
                    self.recent_dp_alerts = []

            # ─── WIRE SYNTHESIS INTO GATE ──────────────────────────────
            if synthesis_result and hasattr(synthesis_result, 'confluence'):
                try:
                    bias = synthesis_result.confluence.bias.value
                    score = synthesis_result.confluence.score
                    self.confluence_gate.update_synthesis(bias, score)
                except Exception as e:
                    logger.warning(f"⚠️ Gate synthesis update failed: {e}")

        except Exception as e:
            logger.error(f"❌ synthesis/narrative checker failed: {e}")
            self.health_registry.record_run('synthesis', success=False, error=str(e))

        return alert_count

    def _handle_tradytics(self, now: datetime, is_market_hours: bool) -> int:
        """Custom handler for tradytics checker (with timeout protection)."""
        if not self.tradytics_checker:
            return 0
        try:
            alerts = self.tradytics_checker.check()
            for alert in alerts:
                self.send_discord(alert.embed, alert.content, alert.alert_type, alert.source, alert.symbol)
            logger.info("   ✅ Tradytics check complete")
            return len(alerts)
        except Exception as e:
            logger.error(f"   ❌ Tradytics checker error: {e}")
            return 0

    # ═══════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════

    def _on_dp_outcome(self, interaction_id: int, outcome):
        """Callback when DP interaction outcome is determined."""
        try:
            outcome_emoji = {
                'BOUNCE': '✅ LEVEL HELD', 'BREAK': '❌ LEVEL BROKE', 'FADE': '⚪ NO CLEAR OUTCOME'
            }.get(outcome.outcome.value, '❓ UNKNOWN')

            if not self.unified_mode:
                embed = {
                    "title": f"🎯 DP OUTCOME: {outcome_emoji}",
                    "color": 3066993 if outcome.outcome.value == 'BOUNCE' else 15158332,
                    "description": f"Interaction #{interaction_id} resolved after {outcome.time_to_outcome_min} min",
                    "fields": [
                        {"name": "📊 Max Move", "value": f"{outcome.max_move_pct:+.2f}%", "inline": True},
                        {"name": "⏱️ Tracking Time", "value": f"{outcome.time_to_outcome_min} min", "inline": True},
                    ],
                    "footer": {"text": "Learning from this outcome... Patterns updated!"},
                    "timestamp": datetime.utcnow().isoformat()
                }
                self.send_discord(embed, alert_type="dp_outcome", source="dp_learning")
        except Exception as e:
            logger.error(f"❌ Outcome alert error: {e}")

    def _is_market_hours(self) -> bool:
        """Check if currently in RTH (Eastern Time)."""
        from datetime import time as dt_time
        import pytz

        et = pytz.timezone('America/New_York')
        now_utc = datetime.now(pytz.UTC)
        now_et = now_utc.astimezone(et)

        current_time = now_et.time()
        market_open = dt_time(9, 30)
        market_close = dt_time(16, 0)
        is_weekday = now_et.weekday() < 5
        in_hours = market_open <= current_time < market_close

        logger.debug(f"   🕐 Market hours check: ET={now_et.strftime('%H:%M:%S')}, weekday={is_weekday}, in_hours={in_hours}")

        return is_weekday and in_hours

    def _get_current_prices(self):
        """Get current SPY/QQQ prices."""
        spy_price, qqq_price = 0.0, 0.0
        try:
            import yfinance as yf
            spy_hist = yf.Ticker('SPY').history(period='1d', interval='1m')
            qqq_hist = yf.Ticker('QQQ').history(period='1d', interval='1m')
            if not spy_hist.empty:
                spy_price = float(spy_hist['Close'].iloc[-1])
            if not qqq_hist.empty:
                qqq_price = float(qqq_hist['Close'].iloc[-1])
        except:
            pass
        return spy_price, qqq_price

    def _get_current_intelligence_snapshot(self) -> dict:
        """Get current snapshot of all intelligence sources."""
        return {
            'fed_watch': {}, 'fed_officials': {}, 'trump_monitor': {},
            'economic_calendar': {}, 'dp_monitor': {}
        }

    def _run_checker_with_health(self, checker_name: str, checker_func: Callable) -> List:
        """Run a checker with health tracking."""
        alerts = []
        try:
            alerts = checker_func()
            self.health_registry.record_run(checker_name, success=True, alerts_generated=len(alerts))
            for alert in alerts:
                symbol = getattr(alert, 'symbol', None)
                alert_type = getattr(alert, 'alert_type', None)
                direction, entry_price = None, None
                if hasattr(alert, 'embed') and alert.embed and 'fields' in alert.embed:
                    import re
                    for field in alert.embed['fields']:
                        if 'Entry' in field.get('name', ''):
                            match = re.search(r'\$?([\d,]+\.?\d*)', field.get('value', ''))
                            if match:
                                entry_price = float(match.group(1).replace(',', ''))
                        if 'Direction' in field.get('name', '') or 'Action' in field.get('name', ''):
                            value = field.get('value', '').upper()
                            if 'LONG' in value or 'BUY' in value:
                                direction = 'LONG'
                            elif 'SHORT' in value or 'SELL' in value:
                                direction = 'SHORT'
                self.health_registry.record_alert(checker_name, alert_type or 'unknown', symbol, direction, entry_price)
        except Exception as e:
            logger.error(f"❌ {checker_name} checker failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.health_registry.record_run(checker_name, success=False, error=str(e))
        return alerts

    def send_startup_alert(self):
        """Send DYNAMIC startup notification using health registry."""
        logger.info("   📤 send_startup_alert() called")
        if self.startup_alert_sent:
            logger.info("   ⏭️ Startup alert already sent, skipping")
            return
        logger.info("   📝 Generating dynamic health embed...")
        embed = self.health_registry.generate_health_embed()
        logger.info("   📤 Calling send_discord for startup alert...")
        result = self.send_discord(embed, alert_type="startup", source="monitor")
        logger.info(f"   {'✅' if result else '❌'} send_discord returned: {result}")
        self.startup_alert_sent = True
        logger.info("   ✅ Startup alert marked as sent")

    # ═══════════════════════════════════════════════════════════════
    # MAIN RUN LOOP
    # ═══════════════════════════════════════════════════════════════

    def run(self):
        """Main run loop — delegates to CheckerScheduler and OvernightManager."""
        logger.info("🚀 Starting unified monitoring (MODULAR)...")

        import pytz
        et = pytz.timezone('America/New_York')
        now_utc = datetime.now(pytz.UTC)
        now_et = now_utc.astimezone(et)
        logger.info(f"   🕐 Server UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info(f"   🕐 Eastern Time: {now_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info(f"   📊 Market hours check: {self._is_market_hours()}")

        # Send startup alert
        logger.info("📤 Attempting to send startup alert to Discord...")
        try:
            self.send_startup_alert()
            logger.info("✅ Startup alert method completed")
        except Exception as e:
            logger.error(f"❌ Startup alert failed: {e}")
            import traceback
            logger.error(traceback.format_exc())

        # Heartbeat tracking
        last_heartbeat = datetime.now()
        heartbeat_interval = 300
        loop_count = 0

        while self.running:
            try:
                now = datetime.now()
                loop_count += 1
                is_market_hours = self._is_market_hours()

                # Heartbeat logging (every 5 minutes)
                if (now - last_heartbeat).seconds >= heartbeat_interval:
                    import pytz
                    et = pytz.timezone('America/New_York')
                    now_et = now.astimezone(et) if now.tzinfo else pytz.UTC.localize(now).astimezone(et)
                    try:
                        import psutil
                        mem_mb = psutil.Process().memory_info().rss / 1024 / 1024
                        mem_str = f"{mem_mb:.1f}MB"
                    except:
                        mem_str = "N/A"
                    logger.info(f"💓 HEARTBEAT | Loop #{loop_count} | ET: {now_et.strftime('%H:%M:%S')} | Market: {'OPEN' if is_market_hours else 'CLOSED'} | Mem: {mem_str}")
                    last_heartbeat = now

                # ── Fed checker special handling (prev_fed_status sync) ──
                if self.fed_checker:
                    self.fed_checker.prev_fed_status = self.prev_fed_status

                # ── Dark pool checker special handling (recent_dp_alerts) ──
                if is_market_hours and self.dp_checker:
                    # Handled by scheduler, but we need to sync dp_alerts after
                    pass

                # ── Run all scheduled checkers ──
                self.scheduler.tick(now, is_market_hours)

                # ── Post-tick state sync ──
                if self.fed_checker and hasattr(self.fed_checker, 'prev_fed_status'):
                    self.prev_fed_status = self.fed_checker.prev_fed_status
                if self.dp_checker and hasattr(self.dp_checker, 'get_recent_alerts'):
                    self.recent_dp_alerts = self.dp_checker.get_recent_alerts()

                # ── Momentum detection (every minute during RTH) ──
                if is_market_hours:
                    self._check_selloffs()
                    self._check_rallies()

                # ── Narrative Brain scheduled updates ──
                try:
                    if self.narrative_enabled and self.narrative_scheduler:
                        self.narrative_scheduler.check_and_run_scheduled_updates()
                        if self.narrative_scheduler.can_run_intra_day_update():
                            intelligence_data = self._get_current_intelligence_snapshot()
                            update = self.narrative_brain.process_intelligence_update("intelligence_snapshot", intelligence_data)
                            if update:
                                self.narrative_scheduler.mark_intra_day_update_sent()
                                logger.info(f"🧠 Narrative update sent: {update.alert_type.value}")
                except Exception as e:
                    logger.error(f"   ❌ Narrative scheduler error: {e}")

                # ── Daily Recap ──
                try:
                    recap_alerts = self.daily_recap_checker.check(now)
                    for alert in recap_alerts:
                        self.send_discord(alert.embed, alert.content, alert.alert_type, alert.source, alert.symbol)
                    # Settle gate outcomes right after recap (16:05 ET)
                    if recap_alerts and self.outcome_tracker:
                        try:
                            self.outcome_tracker.settle_day()
                            logger.info("📊 Gate outcomes settled for today")
                        except Exception as e:
                            logger.error(f"   ❌ Outcome settlement error: {e}")
                except Exception as e:
                    logger.error(f"   ❌ Daily recap error: {e}")

                # ── Morning Brief (07:45 ET, pre-market) ──
                try:
                    if self.morning_brief and self.morning_brief.should_generate(now):
                        self.morning_brief.generate()
                        logger.info("📋 Morning brief sent")
                except Exception as e:
                    logger.error(f"   ❌ Morning brief error: {e}")

                # ── Overnight check (every 2h when market closed) ──
                if not is_market_hours and (self.last_overnight_check is None or (now - self.last_overnight_check).seconds >= self.overnight_interval):
                    self.overnight.run_overnight_check(now)
                    self.last_overnight_check = now

                # Log every 10 loops
                if loop_count % 10 == 0:
                    logger.info(f"✅ Loop #{loop_count} complete | Sleeping 30s...")

                time.sleep(30)

            except KeyboardInterrupt:
                logger.info("\n🛑 Monitor stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Main loop error: {e}")
                time.sleep(60)
