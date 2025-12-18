"""
Monitor Bridge - Reads from existing UnifiedAlphaMonitor

CRITICAL: Don't modify UnifiedAlphaMonitor - it's running in production!
This bridge READS from it and converts to API format.
"""

import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import yfinance as yf

logger = logging.getLogger(__name__)

# Import existing monitor classes
try:
    from live_monitoring.orchestrator.unified_monitor import UnifiedAlphaMonitor
    from live_monitoring.core.signal_generator import SignalGenerator
    from live_monitoring.agents.signal_brain.engine import SignalBrainEngine
    from live_monitoring.agents.narrative_brain.narrative_brain import NarrativeBrain
    from core.ultra_institutional_engine import UltraInstitutionalEngine, InstitutionalContext
except ImportError as e:
    logger.warning(f"Could not import monitor classes: {e}")
    UnifiedAlphaMonitor = None
    SignalGenerator = None
    SignalBrainEngine = None
    NarrativeBrain = None
    UltraInstitutionalEngine = None
    InstitutionalContext = None


class MonitorBridge:
    """
    Bridge between FastAPI and existing UnifiedAlphaMonitor
    
    CRITICAL: Don't modify UnifiedAlphaMonitor - it's running in production!
    This bridge READS from it and converts to API format.
    """
    
    def __init__(self):
        # Initialize the existing monitor (it's already running, but we need access)
        # In production, this might be a shared instance or we read from its outputs
        self.monitor = None  # Will be set by FastAPI startup
        self._cache = {}  # Cache recent outputs
        self._cache_ttl = 30  # 30 seconds cache
    
    def set_monitor(self, monitor):
        """Set the monitor instance (called from FastAPI startup)"""
        self.monitor = monitor
        logger.info("✅ MonitorBridge connected to UnifiedAlphaMonitor")
    
    def get_current_signals(self, symbol: str = "SPY") -> List[Dict]:
        """
        Get all active signals for a symbol
        
        Returns:
            List of signal dicts (converted from LiveSignal objects)
        """
        cache_key = f"signals:{symbol}"
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if (datetime.now() - cached_time).total_seconds() < self._cache_ttl:
                return cached_data
        
        if not self.monitor or not hasattr(self.monitor, 'signal_generator'):
            logger.warning("Monitor or signal_generator not available")
            return []
        
        try:
            # Build institutional context
            api_key = os.getenv('CHARTEXCHANGE_API_KEY') or os.getenv('CHART_EXCHANGE_API_KEY')
            if not api_key:
                logger.warning("No ChartExchange API key found")
                return []
            
            inst_engine = UltraInstitutionalEngine(api_key=api_key)
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            inst_context = inst_engine.build_institutional_context(symbol, yesterday)
            
            if not inst_context:
                logger.warning(f"Could not build institutional context for {symbol}")
                return []
            
            # Get current price
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1d', interval='1m')
            if hist.empty:
                logger.warning(f"No price data for {symbol}")
                return []
            current_price = float(hist['Close'].iloc[-1])
            
            # Generate signals
            signals = self.monitor.signal_generator.generate_signals(symbol, inst_context)
            
            # Convert LiveSignal to dict
            signal_dicts = []
            for signal in signals:
                signal_dict = {
                    "symbol": signal.symbol,
                    "action": signal.action.value if hasattr(signal.action, 'value') else str(signal.action),
                    "timestamp": signal.timestamp.isoformat() if hasattr(signal.timestamp, 'isoformat') else str(signal.timestamp),
                    "entry_price": signal.entry_price,
                    "target_price": signal.target_price,
                    "stop_price": signal.stop_price,
                    "confidence": signal.confidence,
                    "signal_type": signal.signal_type.value if hasattr(signal.signal_type, 'value') else str(signal.signal_type),
                    "rationale": signal.rationale,
                    "dp_level": signal.dp_level,
                    "dp_volume": signal.dp_volume,
                    "institutional_score": signal.institutional_score,
                    "supporting_factors": signal.supporting_factors,
                    "warnings": signal.warnings,
                    "is_master_signal": signal.is_master_signal,
                    "is_actionable": signal.is_actionable,
                    "position_size_pct": signal.position_size_pct,
                    "risk_reward_ratio": signal.risk_reward_ratio
                }
                signal_dicts.append(signal_dict)
            
            # Cache result
            self._cache[cache_key] = (datetime.now(), signal_dicts)
            
            return signal_dicts
            
        except Exception as e:
            logger.error(f"Error getting signals for {symbol}: {e}", exc_info=True)
            return []
    
    def get_synthesis_result(self) -> Optional[Dict]:
        """
        Get current Signal Brain synthesis
        
        Returns:
            SynthesisResult as dict (or None)
        """
        cache_key = "synthesis_result"
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if (datetime.now() - cached_time).total_seconds() < self._cache_ttl:
                return cached_data
        
        if not self.monitor or not hasattr(self.monitor, 'signal_brain'):
            logger.warning("Monitor or signal_brain not available")
            return None
        
        try:
            # Get SPY/QQQ prices
            spy_ticker = yf.Ticker('SPY')
            qqq_ticker = yf.Ticker('QQQ')
            spy_hist = spy_ticker.history(period='1d', interval='1m')
            qqq_hist = qqq_ticker.history(period='1d', interval='1m')
            
            if spy_hist.empty or qqq_hist.empty:
                logger.warning("No price data for SPY/QQQ")
                return None
            
            spy_price = float(spy_hist['Close'].iloc[-1])
            qqq_price = float(qqq_hist['Close'].iloc[-1])
            
            # Get DP levels (from cache or fetch)
            # In production, this would come from the monitor's recent DP alerts
            spy_levels = self._get_dp_levels('SPY')
            qqq_levels = self._get_dp_levels('QQQ')
            
            # Get macro context
            fed_sentiment = "NEUTRAL"
            trump_risk = "LOW"
            if hasattr(self.monitor, 'fed_checker') and self.monitor.fed_checker:
                # Extract fed sentiment from recent alerts
                fed_sentiment = "NEUTRAL"  # Default
            if hasattr(self.monitor, 'trump_checker') and self.monitor.trump_checker:
                # Extract trump risk from recent alerts
                trump_risk = "LOW"  # Default
            
            # Run synthesis
            synthesis = self.monitor.signal_brain.analyze(
                spy_levels=spy_levels,
                qqq_levels=qqq_levels,
                spy_price=spy_price,
                qqq_price=qqq_price,
                fed_sentiment=fed_sentiment,
                trump_risk=trump_risk
            )
            
            # Convert SynthesisResult to dict
            result = self._synthesis_to_dict(synthesis)
            
            # Cache result
            self._cache[cache_key] = (datetime.now(), result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting synthesis: {e}", exc_info=True)
            return None
    
    def get_narrative_update(self) -> Optional[Dict]:
        """
        Get current Narrative Brain update
        
        Returns:
            NarrativeUpdate as dict (or None)
        """
        if not self.monitor or not hasattr(self.monitor, 'narrative_brain'):
            logger.warning("Monitor or narrative_brain not available")
            return None
        
        try:
            # Get recent narratives from memory
            recent = self.monitor.narrative_brain.memory.get_recent_narratives(hours=1)
            if not recent:
                return None
            
            # Get most recent
            latest = recent[0]
            
            return {
                "alert_type": latest.get('alert_type'),
                "title": latest.get('title', ''),
                "content": latest.get('content', ''),
                "intelligence_sources": latest.get('intelligence_sources', []),
                "market_impact": latest.get('market_impact', ''),
                "timestamp": latest.get('timestamp')
            }
            
        except Exception as e:
            logger.error(f"Error getting narrative: {e}", exc_info=True)
            return None
    
    def get_dp_levels(self, symbol: str) -> List[Dict]:
        """
        Get dark pool levels for a symbol
        
        Returns:
            List of DP level dicts
        """
        cache_key = f"dp_levels:{symbol}"
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if (datetime.now() - cached_time).total_seconds() < 60:  # 1 minute cache for DP
                return cached_data
        
        if not self.monitor or not hasattr(self.monitor, 'dp_monitor_engine'):
            logger.warning("Monitor or dp_monitor_engine not available")
            return []
        
        try:
            # Get levels from DP monitor engine
            # This would access the monitor's DP engine
            # For now, return empty - will be implemented based on actual DP engine API
            # TODO: Implement actual DP level fetching from monitor
            return []
            
        except Exception as e:
            logger.error(f"Error getting DP levels for {symbol}: {e}", exc_info=True)
            return []
    
    def _get_dp_levels(self, symbol: str) -> List[Dict]:
        """Internal helper to get DP levels (used by synthesis)"""
        return self.get_dp_levels(symbol)
    
    def _synthesis_to_dict(self, synthesis) -> Dict:
        """Convert SynthesisResult to dict"""
        if not synthesis:
            return {}
        
        result = {
            "timestamp": synthesis.timestamp.isoformat() if hasattr(synthesis, 'timestamp') and hasattr(synthesis.timestamp, 'isoformat') else datetime.now().isoformat(),
            "symbols": synthesis.symbols if hasattr(synthesis, 'symbols') else [],
        }
        
        # Context
        if hasattr(synthesis, 'context'):
            ctx = synthesis.context
            result["context"] = {
                "spy_price": ctx.spy_price,
                "qqq_price": ctx.qqq_price,
                "vix_level": ctx.vix_level,
                "fed_sentiment": ctx.fed_sentiment,
                "trump_risk": ctx.trump_risk,
                "time_of_day": ctx.time_of_day.value if hasattr(ctx.time_of_day, 'value') else str(ctx.time_of_day)
            }
        
        # Confluence
        if hasattr(synthesis, 'confluence'):
            conf = synthesis.confluence
            result["confluence"] = {
                "score": conf.score,
                "bias": conf.bias.value if hasattr(conf.bias, 'value') else str(conf.bias),
                "dp_score": conf.dp_score,
                "cross_asset_score": conf.cross_asset_score,
                "macro_score": conf.macro_score,
                "timing_score": conf.timing_score
            }
        
        # Recommendation
        if hasattr(synthesis, 'recommendation') and synthesis.recommendation:
            rec = synthesis.recommendation
            result["recommendation"] = {
                "action": rec.action,
                "symbol": rec.symbol,
                "entry_price": rec.entry_price,
                "stop_price": rec.stop_price,
                "target_price": rec.target_price,
                "risk_reward": rec.risk_reward,
                "primary_reason": rec.primary_reason,
                "why_this_level": rec.why_this_level,
                "risks": rec.risks,
                "wait_for": rec.wait_for
            }
        
        # Thinking
        if hasattr(synthesis, 'thinking'):
            result["thinking"] = synthesis.thinking
        
        return result
    
    def get_market_data(self, symbol: str) -> Optional[Dict]:
        """
        Get current market data for a symbol
        
        Returns:
            Dict with price, volume, regime, etc.
        """
        cache_key = f"market:{symbol}"
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if (datetime.now() - cached_time).total_seconds() < 5:  # 5 second cache
                return cached_data
        
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1d', interval='1m')
            
            if hist.empty:
                return None
            
            latest = hist.iloc[-1]
            first = hist.iloc[0]
            
            current_price = float(latest['Close'])
            open_price = float(first['Open'])
            change = current_price - open_price
            change_pct = (change / open_price * 100) if open_price > 0 else 0
            
            # Get VIX
            vix_ticker = yf.Ticker('^VIX')
            vix_hist = vix_ticker.history(period='1d', interval='1m')
            vix = float(vix_hist['Close'].iloc[-1]) if not vix_hist.empty else 0.0
            
            # Get regime (would use RegimeDetector if available)
            regime = "UNKNOWN"
            if hasattr(self.monitor, 'regime_detector') and self.monitor.regime_detector:
                try:
                    regime = self.monitor.regime_detector.detect(current_price)
                except:
                    pass
            
            market_data = {
                "symbol": symbol,
                "price": current_price,
                "change": change,
                "change_percent": change_pct,
                "volume": int(latest['Volume']),
                "high": float(hist['High'].max()),
                "low": float(hist['Low'].min()),
                "open": open_price,
                "regime": regime,
                "vix": vix,
                "timestamp": datetime.now().isoformat()
            }
            
            # Cache result
            self._cache[cache_key] = (datetime.now(), market_data)
            
            return market_data
            
        except Exception as e:
            logger.error(f"Error getting market data for {symbol}: {e}", exc_info=True)
            return None

