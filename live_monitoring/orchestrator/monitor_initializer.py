"""
🔧 MONITOR INITIALIZER

Initializes all monitoring components (Fed, Trump, Economic, DP, etc.)
"""

import os
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class MonitorInitializer:
    """Initializes all monitoring components."""
    
    def __init__(self, on_dp_outcome: Optional[Callable] = None):
        self.on_dp_outcome = on_dp_outcome
        self.initialized = {}
    
    def initialize_all(self) -> dict:
        """Initialize all monitors and return status dict."""
        # Initialize in ORDER - dp_monitor_engine needs dark_pool to be initialized first
        self.initialized = {}
        
        # Step 1: Core monitors (no dependencies)
        self.initialized['fed'] = self._init_fed()
        self.initialized['trump'] = self._init_trump()
        
        # Step 2: Dark Pool (no dependencies)
        self.initialized['dark_pool'] = self._init_dark_pool()
        
        # Step 3: DP Learning (no dependencies)
        self.initialized['dp_learning'] = self._init_dp_learning()
        
        # Step 4: DP Monitor Engine (DEPENDS ON dark_pool!)
        self.initialized['dp_monitor_engine'] = self._init_dp_monitor_engine()
        
        # Step 5: Signal Brain (depends on multiple)
        self.initialized['signal_brain'] = self._init_signal_brain()
        
        # Step 6: Other monitors
        self.initialized['narrative_brain'] = self._init_narrative_brain()
        self.initialized['economic'] = self._init_economic()
        self.initialized['tradytics'] = self._init_tradytics()
        
        return self.initialized
    
    def _init_fed(self) -> dict:
        """Initialize Fed Watch monitors."""
        try:
            from live_monitoring.agents.fed_watch_monitor import FedWatchMonitor
            from live_monitoring.agents.fed_officials_monitor import FedOfficialsMonitor
            
            fed_watch = FedWatchMonitor(alert_threshold=5.0)
            fed_officials = FedOfficialsMonitor()
            
            logger.info("   ✅ Fed monitors initialized")
            return {
                'enabled': True,
                'fed_watch': fed_watch,
                'fed_officials': fed_officials
            }
        except Exception as e:
            logger.warning(f"   ⚠️ Fed monitors failed: {e}")
            return {'enabled': False, 'error': str(e)}
    
    def _init_trump(self) -> dict:
        """Initialize Trump intelligence monitors."""
        try:
            from live_monitoring.agents.trump_pulse import TrumpPulse
            from live_monitoring.agents.trump_news_monitor import TrumpNewsMonitor
            
            trump_pulse = TrumpPulse()
            trump_news = TrumpNewsMonitor()
            
            logger.info("   ✅ Trump monitors initialized")
            return {
                'enabled': True,
                'trump_pulse': trump_pulse,
                'trump_news': trump_news
            }
        except Exception as e:
            logger.warning(f"   ⚠️ Trump monitors failed: {e}")
            return {'enabled': False, 'error': str(e)}
    
    def _init_dark_pool(self) -> dict:
        """Initialize Dark Pool intelligence."""
        try:
            api_key = os.getenv('CHARTEXCHANGE_API_KEY')
            if not api_key:
                logger.warning("   ⚠️ CHARTEXCHANGE_API_KEY not set - DP disabled")
                return {'enabled': False, 'error': 'API key not set'}
            
            from core.ultra_institutional_engine import UltraInstitutionalEngine
            from core.data.ultimate_chartexchange_client import UltimateChartExchangeClient
            
            dp_client = UltimateChartExchangeClient(api_key)
            dp_engine = UltraInstitutionalEngine(api_key)
            
            logger.info("   ✅ Dark Pool monitors initialized")
            return {
                'enabled': True,
                'dp_client': dp_client,
                'dp_engine': dp_engine
            }
        except Exception as e:
            logger.warning(f"   ⚠️ Dark Pool monitors failed: {e}")
            return {'enabled': False, 'error': str(e)}
    
    def _init_dp_learning(self) -> dict:
        """Initialize DP Learning Engine."""
        try:
            from live_monitoring.agents.dp_learning import DPLearningEngine
            
            dp_learning = DPLearningEngine(
                on_outcome=self.on_dp_outcome,
                on_prediction=None
            )
            dp_learning.start()
            
            logger.info("   ✅ Dark Pool Learning Engine initialized")
            return {
                'enabled': True,
                'dp_learning': dp_learning
            }
        except Exception as e:
            logger.warning(f"   ⚠️ DP Learning Engine failed: {e}")
            return {'enabled': False, 'error': str(e), 'dp_learning': None}
    
    def _init_dp_monitor_engine(self) -> dict:
        """Initialize DP Monitor Engine."""
        try:
            from live_monitoring.agents.dp_monitor import DPMonitorEngine
            
            dp_status = self.initialized.get('dark_pool', {})
            learning_status = self.initialized.get('dp_learning', {})
            
            dp_monitor_engine = DPMonitorEngine(
                api_key=os.getenv('CHARTEXCHANGE_API_KEY'),
                dp_client=dp_status.get('dp_client') if dp_status.get('enabled') else None,
                learning_engine=learning_status.get('dp_learning') if learning_status.get('enabled') else None,
                debounce_minutes=30
            )
            
            logger.info("   ✅ Dark Pool Monitor Engine (modular) initialized")
            return {
                'enabled': True,
                'dp_monitor_engine': dp_monitor_engine
            }
        except Exception as e:
            logger.warning(f"   ⚠️ DP Monitor Engine failed: {e}")
            return {'enabled': False, 'error': str(e), 'dp_monitor_engine': None}
    
    def _init_signal_brain(self) -> dict:
        """Initialize Signal Synthesis Brain."""
        try:
            from live_monitoring.agents.signal_brain import SignalBrainEngine
            from live_monitoring.agents.signal_brain.narrative import NarrativeEnricher
            from live_monitoring.agents.signal_brain.macro import MacroContextProvider
            
            # Initialize Narrative Enricher
            narrative_enricher = None
            try:
                narrative_enricher = NarrativeEnricher()
                logger.info("   📰 Narrative Enricher initialized")
            except Exception as ne:
                logger.warning(f"   ⚠️ Narrative Enricher failed: {ne}")
            
            # Initialize MacroContextProvider
            fed_status = self.initialized.get('fed', {})
            econ_status = self.initialized.get('economic', {})
            trump_status = self.initialized.get('trump', {})
            
            macro_provider = None
            try:
                macro_provider = MacroContextProvider(
                    fed_watch=fed_status.get('fed_watch') if fed_status.get('enabled') else None,
                    fed_officials=fed_status.get('fed_officials') if fed_status.get('enabled') else None,
                    economic_engine=econ_status.get('econ_engine') if econ_status.get('enabled') else None,
                    economic_calendar=econ_status.get('econ_calendar') if econ_status.get('enabled') else None,
                    trump_monitor=trump_status.get('trump_pulse') if trump_status.get('enabled') else None,
                )
                logger.info("   📊 MacroContextProvider initialized (REAL DATA!)")
            except Exception as me:
                logger.warning(f"   ⚠️ MacroContextProvider failed: {me}")
            
            # Initialize Signal Brain
            learning_status = self.initialized.get('dp_learning', {})
            signal_brain = SignalBrainEngine(
                dp_learning_engine=learning_status.get('dp_learning') if learning_status.get('enabled') else None,
                narrative_enricher=narrative_enricher
            )
            
            logger.info("   ✅ Signal Synthesis Brain initialized (THINKING LAYER)")
            return {
                'enabled': True,
                'signal_brain': signal_brain,
                'macro_provider': macro_provider,
                'narrative_enricher': narrative_enricher
            }
        except Exception as e:
            logger.warning(f"   ⚠️ Signal Brain failed: {e}")
            return {
                'enabled': False,
                'error': str(e),
                'signal_brain': None,
                'macro_provider': None
            }
    
    def _init_narrative_brain(self) -> dict:
        """Initialize Narrative Brain."""
        try:
            from live_monitoring.agents.narrative_brain import NarrativeBrain
            from live_monitoring.agents.narrative_brain.schedule_manager import NarrativeScheduler
            
            narrative_brain = NarrativeBrain()
            narrative_scheduler = NarrativeScheduler(narrative_brain)
            
            logger.info("   🧠 Narrative Brain initialized (CONTEXTUAL STORYTELLING)")
            return {
                'enabled': True,
                'narrative_brain': narrative_brain,
                'narrative_scheduler': narrative_scheduler
            }
        except Exception as e:
            logger.warning(f"   ⚠️ Narrative Brain failed: {e}")
            return {
                'enabled': False,
                'error': str(e),
                'narrative_brain': None,
                'narrative_scheduler': None
            }
    
    def _init_economic(self) -> dict:
        """Initialize Economic Intelligence Engine."""
        try:
            from live_monitoring.agents.economic import EconomicIntelligenceEngine
            from live_monitoring.agents.economic.calendar import EconomicCalendar, Importance
            from live_monitoring.agents.economic.models import EconomicRelease, EventType
            
            econ_engine = EconomicIntelligenceEngine()
            
            # Try EventLoader first, fallback to static calendar
            econ_calendar = None
            econ_calendar_type = None
            try:
                from live_monitoring.enrichment.apis.event_loader import EventLoader
                econ_calendar = EventLoader()
                econ_calendar_type = "api"
                logger.info("   ✅ Economic Calendar: REAL API (EventLoader - Baby-Pips)")
            except Exception as e:
                logger.warning(f"   ⚠️ EventLoader failed, using static calendar: {e}")
                econ_calendar = EconomicCalendar()
                econ_calendar_type = "static"
                logger.info("   ⚠️ Economic Calendar: STATIC (fallback - hard-coded)")
            
            # Seed with sample historical data
            historical = [
                EconomicRelease(
                    date="2024-12-06", time="08:30", event_type=EventType.NFP,
                    event_name="Nonfarm Payrolls", actual=227, forecast=200, previous=36,
                    surprise_pct=13.5, surprise_sigma=1.35,
                    fed_watch_before=66, fed_watch_after_1hr=74, fed_watch_shift_1hr=8,
                    days_to_fomc=12
                ),
                EconomicRelease(
                    date="2024-11-01", time="08:30", event_type=EventType.NFP,
                    event_name="Nonfarm Payrolls", actual=12, forecast=100, previous=254,
                    surprise_pct=-88, surprise_sigma=-2.2,
                    fed_watch_before=70, fed_watch_after_1hr=82, fed_watch_shift_1hr=12,
                    days_to_fomc=6
                ),
                EconomicRelease(
                    date="2024-10-04", time="08:30", event_type=EventType.NFP,
                    event_name="Nonfarm Payrolls", actual=254, forecast=140, previous=159,
                    surprise_pct=81, surprise_sigma=2.5,
                    fed_watch_before=95, fed_watch_after_1hr=85, fed_watch_shift_1hr=-10,
                    days_to_fomc=33
                ),
                EconomicRelease(
                    date="2024-09-06", time="08:30", event_type=EventType.NFP,
                    event_name="Nonfarm Payrolls", actual=142, forecast=160, previous=89,
                    surprise_pct=-11, surprise_sigma=-0.9,
                    fed_watch_before=60, fed_watch_after_1hr=70, fed_watch_shift_1hr=10,
                    days_to_fomc=12
                ),
                EconomicRelease(
                    date="2024-08-02", time="08:30", event_type=EventType.NFP,
                    event_name="Nonfarm Payrolls", actual=114, forecast=175, previous=179,
                    surprise_pct=-35, surprise_sigma=-1.8,
                    fed_watch_before=75, fed_watch_after_1hr=90, fed_watch_shift_1hr=15,
                    days_to_fomc=46
                ),
            ]
            econ_engine.add_historical_data(historical)
            
            logger.info("   ✅ Economic Intelligence Engine initialized")
            return {
                'enabled': True,
                'econ_engine': econ_engine,
                'econ_calendar': econ_calendar,
                'econ_calendar_type': econ_calendar_type
            }
        except Exception as e:
            logger.warning(f"   ⚠️ Economic engine failed: {e}")
            return {
                'enabled': False,
                'error': str(e),
                'econ_engine': None,
                'econ_calendar': None
            }
    
    def _init_tradytics(self) -> dict:
        """Initialize Tradytics LLM analysis."""
        try:
            from src.data.llm_api import query_llm
            logger.info("   ✅ Tradytics LLM analysis available")
            return {'enabled': True, 'llm_available': True}
        except Exception as e:
            logger.warning(f"   ⚠️ Tradytics LLM analysis unavailable: {e}")
            return {'enabled': False, 'llm_available': False, 'error': str(e)}

