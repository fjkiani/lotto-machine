import pandas as pd
from typing import List, Dict, Any
from datetime import datetime

from .data.market_data import MarketDataProvider
from .data.context_data import ContextDataProvider
from .registry import DetectorRegistry
from backtesting.simulation.base_detector import BaseDetector, Signal, TradeResult

class SessionReplayer:
    """
    Core engine for replaying a specific trading session.
    It feeds 1m OHLC data into active detectors bar-by-bar, simulating the live environment.
    """
    
    def __init__(self, symbols: List[str] = None):
        self.symbols = symbols or ["SPY", "QQQ"]
        
        self.market_provider = MarketDataProvider()
        self.context_provider = ContextDataProvider()
        
        self.registry = DetectorRegistry()
        self.registry.load_all()
        
    def replay_session(self, date_str: str) -> Dict[str, Any]:
        """
        Replays the given date bar-by-bar over all active detectors.
        """
        print(f"\n{'='*60}")
        print(f"🔄 SESSION REPLAY: {date_str}")
        print(f"{'='*60}")
        self.registry.print_status()
        
        # 1. Load context
        dp_snap = self.context_provider.get_dp_snapshot(date_str)
        narrative = self.context_provider.get_narrative_context(date_str)
        market_ctx = self.market_provider.get_market_context(date_str)
        
        print(f"\n📊 PRE-MARKET CONTEXT (Simulated)")
        print(f"  VIX: {market_ctx['vix']} | Trend: {market_ctx['direction']}")
        print(f"  Narrative: {narrative['direction']} | Conviction: {narrative['conviction']}")
        print(f"  Dark Pool Alerts (09:00): {dp_snap.get('alerts', 0)}")
        
        all_signals = []
        all_trades = []
        
        # 2. Replay loop over symbols
        for symbol in self.symbols:
            # 1m OHLC isolated to this specific date
            data = self.market_provider.get_historical_bars(symbol, date_str, interval="1m")
            if data.empty:
                print(f"  ⚠️ No 1m data found for {symbol} on {date_str}. Skipping.")
                continue
                
            print(f"\n▶️ REPLAYING: {symbol} ({len(data)} bars)")
            
            # 3. Bar-by-bar evaluation 
            # (In reality, detectors evaluate the whole dataframe under the hood for speed via pandas, 
            # but we simulate the entry timestamps correctly)
            for name, detector in self.registry.get_all().items():
                try:
                    # Some detectors expect exactly these kwargs, some don't.
                    signals = detector.detect_signals(symbol, data)
                    all_signals.extend(signals)
                    
                    # Convert to trades
                    for signal in signals:
                        entry_idx = _find_bar_idx(data, signal.timestamp)
                        if entry_idx is not None:
                            trade = detector.simulate_trade(signal, data, entry_idx)
                            
                            # Attach Narrative context to the trade for reporting
                            trade._narrative_thesis = narrative.get("thesis", "No narrative available.")
                            trade._narrative_conviction = narrative.get("conviction", "NONE")
                            
                            all_trades.append(trade)
                            
                except Exception as e:
                    print(f"  ❌ {name} detector failed on {symbol}: {e}")
                    
        # 4. Compile results structure identical to DailyBacktestResult
        return self._compile_daily_results(date_str, market_ctx, all_signals, all_trades)
        
    def _compile_daily_results(self, date_str: str, market_ctx: Dict, signals: List[Signal], trades: List[TradeResult]) -> Dict[str, Any]:
        """
        Groups the flat list of trades back into the expected structure.
        """
        wins = len([t for t in trades if t.outcome == "WIN"])
        losses = len([t for t in trades if t.outcome == "LOSS"])
        pnl = sum([t.pnl_pct for t in trades])
        
        return {
            "date": date_str,
            "market_direction": market_ctx["direction"],
            "vix": market_ctx["vix"],
            "total_signals": len(signals),
            "total_trades": len(trades),
            "total_wins": wins,
            "total_losses": losses,
            "win_rate": (wins / len(trades) * 100) if trades else 0,
            "total_pnl": pnl,
            "trades": [
                {
                    "symbol": t.signal.symbol,
                    "direction": t.signal.direction,
                    "entry_price": t.signal.entry_price,
                    "exit_price": t.exit_price,
                    "pnl_pct": t.pnl_pct,
                    "outcome": t.outcome,
                    "narrative_conviction": getattr(t, '_narrative_conviction', 'NONE'),
                    "narrative_thesis": getattr(t, '_narrative_thesis', '')
                } 
                for t in trades
            ]
        }

def _find_bar_idx(data: pd.DataFrame, target_time: datetime) -> int:
    """Helper to match a signal timestamp to the closest dataframe index."""
    for i, idx in enumerate(data.index):
        if hasattr(idx, 'timestamp') and idx >= target_time:
            return i
    return None
