"""
Synthesis Checker - Generates unified market synthesis signals.

Extracted from unified_monitor.py for modularity.

This checker analyzes DP levels, prices, and macro context to generate
unified market synthesis signals.
"""

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any

from .base_checker import BaseChecker, CheckerAlert

logger = logging.getLogger(__name__)


class SynthesisChecker(BaseChecker):
    """
    Checks Signal Synthesis Brain and generates unified market synthesis.
    
    Responsibilities:
    - Fetch current SPY/QQQ prices
    - Extract DP levels from recent alerts
    - Get macro context (Fed sentiment, Trump risk)
    - Generate synthesis analysis
    - Send alerts when thresholds met
    """
    
    def __init__(
        self,
        alert_manager,
        signal_brain=None,
        macro_provider=None,
        unified_mode=False
    ):
        """
        Initialize Synthesis checker.
        
        Args:
            alert_manager: AlertManager instance for deduplication
            signal_brain: SignalBrain instance for analysis
            macro_provider: MacroProvider instance for context
            unified_mode: If True, sends synthesis when DP alerts exist
        """
        super().__init__(alert_manager, unified_mode)
        self.signal_brain = signal_brain
        self.macro_provider = macro_provider
        
        # State management
        self.last_synthesis_sent = None
    
    @property
    def name(self) -> str:
        """Return checker name for identification."""
        return "synthesis_checker"

    def check(
        self,
        recent_dp_alerts: List,
        spy_price: Optional[float] = None,
        qqq_price: Optional[float] = None
    ) -> tuple[List[CheckerAlert], Optional[Any]]:
        """
        Check Signal Synthesis Brain.
        
        Args:
            recent_dp_alerts: List of recent DP alerts
            spy_price: Current SPY price (optional, will fetch if None)
            qqq_price: Current QQQ price (optional, will fetch if None)
            
        Returns:
            Tuple of (List[CheckerAlert], synthesis_result)
            synthesis_result is returned so orchestrator can pass to Narrative checker
        """
        if not self.signal_brain:
            return [], None
        
        try:
            import yfinance as yf
            
            # Fetch prices if not provided
            if spy_price is None or qqq_price is None:
                yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                
                fetched_spy_price = 0.0
                fetched_qqq_price = 0.0
                for symbol in ['SPY', 'QQQ']:
                    try:
                        ticker = yf.Ticker(symbol)
                        hist = ticker.history(period='1d', interval='1m')
                        if not hist.empty:
                            price = float(hist['Close'].iloc[-1])
                            if symbol == 'SPY':
                                fetched_spy_price = price
                            else:
                                fetched_qqq_price = price
                    except Exception as e:
                        logger.debug(f"   ⚠️ Could not fetch {symbol} price: {e}")
                        continue
                
                if spy_price is None:
                    spy_price = fetched_spy_price
                if qqq_price is None:
                    qqq_price = fetched_qqq_price
            
            # Extract DP levels from recent alerts
            spy_levels = []
            qqq_levels = []
            
            if recent_dp_alerts:
                for alert in recent_dp_alerts:
                    bg = alert.battleground
                    level_data = {'price': bg.price, 'volume': bg.volume}
                    if bg.symbol == 'SPY':
                        spy_levels.append(level_data)
                    elif bg.symbol == 'QQQ':
                        qqq_levels.append(level_data)
            
            if not spy_levels and not qqq_levels:
                logger.info(f"   ⚠️  No DP levels extracted from {len(recent_dp_alerts)} recent alerts")
                return [], None
            
            logger.info(f"   📊 Extracted {len(spy_levels)} SPY levels, {len(qqq_levels)} QQQ levels from {len(recent_dp_alerts)} alerts")
            
            # Get macro context
            fed_sentiment = "NEUTRAL"
            trump_risk = "LOW"
            
            if self.macro_provider:
                try:
                    macro_context = self.macro_provider.get_context()
                    fed_sentiment = macro_context.fed_sentiment
                    trump_risk = macro_context.trump_risk
                except Exception as e:
                    logger.debug(f"   ⚠️ Could not get macro context: {e}")
            
            # Generate synthesis
            logger.info(f"   🧠 Generating synthesis with {len(spy_levels)} SPY + {len(qqq_levels)} QQQ levels...")
            result = self.signal_brain.analyze(
                spy_levels=spy_levels,
                qqq_levels=qqq_levels,
                spy_price=spy_price,
                qqq_price=qqq_price,
                fed_sentiment=fed_sentiment,
                trump_risk=trump_risk,
            )
            
            # Log synthesis result
            if result:
                confluence = getattr(result, 'confluence', None)
                logger.info(f"   📊 Synthesis result: confluence={confluence}, unified_mode={self.unified_mode}, recent_alerts={len(recent_dp_alerts)}")

                # ── Wave 7: 3-factor bearish override ──
                bearish, override_score = self._compute_bearish_override(spy_price or 0)
                if bearish and confluence:
                    try:
                        confluence.bias.value = "BEARISH"
                        confluence.score = override_score
                        logger.info(f"🔴 Bearish override applied: {override_score:.0f}% BEARISH (3-factor score)")
                    except Exception as e:
                        logger.warning(f"⚠️ Bearish override mutation failed: {e}")
            
            # Check if should send
            should_send = False
            if self.unified_mode and len(recent_dp_alerts) > 0:
                should_send = True
                logger.info(f"   ✅ Should send (unified_mode + {len(recent_dp_alerts)} alerts)")
            elif self.signal_brain.should_alert(result):
                should_send = True
                logger.info(f"   ✅ Should send (should_alert returned True)")
            else:
                logger.info(f"   ⚠️  Should NOT send (should_alert returned False)")
            
            if not should_send:
                return [], result  # Return result even if not alerting (for Narrative checker)
            
            # Cooldown check
            current_time = time.time()
            if self.last_synthesis_sent:
                elapsed = current_time - self.last_synthesis_sent
                if elapsed < 300:
                    return [], result  # Return result even on cooldown
            
            self.last_synthesis_sent = current_time
            
            # Create alert
            embed = self.signal_brain.to_discord(result)
            content = f"🧠 **UNIFIED MARKET SYNTHESIS** | {result.confluence.score:.0f}% {result.confluence.bias.value}"
            
            return [CheckerAlert(
                embed=embed,
                content=content,
                alert_type="synthesis",
                source="synthesis_checker",
                symbol="SPY,QQQ"
            )], result
                
        except Exception as e:
            logger.error(f"   ❌ Synthesis error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return [], None


    def _compute_bearish_override(self, spy_price: float) -> tuple:
        """3-factor bearish bias check: COT + DP Flow + Gamma.
        
        Returns (should_override: bool, override_score: float).
        2/3 or 3/3 factors → override to BEARISH.
        """
        import json, os
        score = 0

        # Factor 1: COT positioning — read from cot_history.db (VX specs_net)
        try:
            import sqlite3
            cot_db = Path(__file__).resolve().parent.parent.parent.parent / "data" / "external" / "cftc_cot" / "db" / "cot_history.db"
            if cot_db.exists():
                conn = sqlite3.connect(str(cot_db))
                row = conn.execute(
                    "SELECT specs_net FROM weekly_positioning WHERE contract_key='VX' ORDER BY report_date DESC LIMIT 1"
                ).fetchone()
                conn.close()
                if row and row[0] < -5000:
                    score += 1
            else:
                # Fallback: legacy JSON file
                with open("data/cot_positioning.json") as f:
                    cot = json.load(f)
                if cot.get("net_speculator_position", 0) < -5000:
                    score += 1
        except Exception:
            pass  # Missing DB or file → 0 points

        # Factor 2: DP Flow — declining net volume trend (last 3 data points)
        dp_data = None
        try:
            with open("data/axlfi_dark_pool_live.json") as f:
                dp_data = json.load(f)
            
            # Real format: URL-keyed → individual_short_volume.net_volume
            dp_flow_history = []
            for key, val in dp_data.items():
                if isinstance(val, dict) and 'symbol=SPY' in str(key) and 'window' in str(key):
                    isv = val.get("individual_short_volume", {})
                    if isinstance(isv, dict):
                        nv = isv.get("net_volume", [])
                        if isinstance(nv, list) and len(nv) >= 3:
                            dp_flow_history = [float(v) for v in nv[-3:]]
                    break
            
            # Fallback: legacy epoch format
            if not dp_flow_history:
                epochs = dp_data.get("epochs", dp_data.get("data", []))
                if len(epochs) >= 3:
                    dp_flow_history = [e.get("net_premium", 0.0) for e in epochs[-3:]]
            
            if len(dp_flow_history) >= 3:
                if dp_flow_history[2] < dp_flow_history[1] < dp_flow_history[0] and dp_flow_history[2] < 0:
                    score += 1
        except Exception:
            pass  # Missing file or insufficient data → 0 points

        # Factor 3: Gamma — wall proximity
        try:
            if dp_data is None:
                with open("data/axlfi_dark_pool_live.json") as f:
                    dp_data = json.load(f)
            call_wall = float(dp_data.get("call_wall", 0))
            put_wall = float(dp_data.get("put_wall", 0))
            if call_wall > 0 and put_wall > 0 and spy_price > 0:
                if (spy_price - put_wall) < (call_wall - spy_price):
                    score += 1
        except Exception:
            pass

        if score >= 2:
            override_score = 90.0 if score == 3 else 65.0
            return True, override_score
        return False, 0.0
