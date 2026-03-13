import pandas as pd
from typing import List, Dict, Any
from datetime import datetime

from .data.market_data import MarketDataProvider
from .data.context_data import ContextDataProvider
from .registry import DetectorRegistry
from backtesting.simulation.base_detector import BaseDetector, Signal, TradeResult
from live_monitoring.core.signal_generator import SignalGenerator
from core.ultra_institutional_engine import InstitutionalContext

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
        
        # Instantiate SignalGenerator strictly for the kill shot hook
        self.signal_generator = SignalGenerator(use_narrative=True)
        
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
        # We actively synthesize the narrative here instead of failing silently on an empty JSON
        from live_monitoring.enrichment.narrative_engine import run_narrative_engine
        try:
            print("\n🧠 SYNTHESIZING LIVE NARRATIVE FOR SESSION REPLAY...")
            # We enforce run_narrative_engine to spit out the actual dict
            narrative = run_narrative_engine(self.symbols[0], date_str, verbose=False)
        except Exception as e:
            print(f"  ❌ Narrative Engine failed: {e}")
            narrative = self.context_provider.get_narrative_context(date_str)
            
        market_ctx = self.market_provider.get_market_context(date_str)
        
        print(f"\n📊 PRE-MARKET CONTEXT (Simulated)")
        print(f"  VIX: {market_ctx['vix']} | Trend: {market_ctx['direction']}")
        print(f"  Narrative: {narrative.get('direction', 'UNKNOWN')} | Conviction: {narrative.get('conviction', 'LOW')}")
        print(f"  Dark Pool Alerts (09:00): {dp_snap.get('alerts', 0)}")
        
        all_signals = []
        all_trades = []
        
        # Build InstitutionalContext from our mock context for the kill shots
        inst_context = InstitutionalContext(
            symbol="",
            date=date_str,
            dp_battlegrounds=dp_snap.get("levels", []),
            dp_total_volume=dp_snap.get("total_volume", 0),
            dp_buy_sell_ratio=dp_snap.get("buy_sell_ratio", 1.0),
            dp_avg_print_size=0.0,
            dark_pool_pct=dp_snap.get("pct", 50.0),
            short_volume_pct=0.0,
            short_interest=0,
            days_to_cover=0.0,
            borrow_fee_rate=0.0,
            max_pain=0.0,
            put_call_ratio=1.0,
            total_option_oi=0,
            institutional_buying_pressure=0.5, # Default mock
            squeeze_potential=0.5,
            gamma_pressure=market_ctx.get("gex_proxy", 0.5), # From our mock
        )
        if narrative.get("thesis"):
            # Attach narrative to context so kill shots can score divergence
            inst_context.narrative = type('NarrativeMock', (), {
                'thesis': narrative.get('thesis', ''),
                'conviction': narrative.get('conviction', 'NONE'),
                'divergences': [{'severity': 'HIGH'}] if narrative.get('conviction') == 'HIGH' else [] # Mock divergence for backtest testing
            })
        
        # 2. Replay loop over symbols
        for symbol in self.symbols:
            # 1m OHLC isolated to this specific date
            data = self.market_provider.get_historical_bars(symbol, date_str, interval="1m")
            if data.empty:
                print(f"  ⚠️ No 1m data found for {symbol} on {date_str}. Skipping.")
                continue
                
            print(f"\n▶️ REPLAYING: {symbol} ({len(data)} bars)")
            
            # 3. Bar-by-bar evaluation 
            for name, detector in self.registry.get_all().items():
                try:
                    # Some detectors expect exactly these kwargs, some don't.
                    signals = detector.detect_signals(symbol, data)
                    
                    # RUN ALPHA'S KILL SHOTS
                    # This applies the Trap Matrix Danger Zones and Narrative Divergence rules
                    inst_context.symbol = symbol
                    current_price = data['Close'].iloc[-1] if not data.empty else 0
                    valid_signals = self.signal_generator._apply_holistic_kill_shots(
                        symbol, current_price, inst_context, signals
                    )
                    
                    all_signals.extend(valid_signals)
                    
                    # Convert to trades for the VALID signals only
                    for signal in valid_signals:
                        entry_idx = _find_bar_idx(data, signal.timestamp)
                        if entry_idx is not None:
                            trade = detector.simulate_trade(signal, data, entry_idx)
                            
                            # Attach Narrative context AND Divergence to the trade for reporting
                            if hasattr(inst_context, 'narrative'):
                                trade._narrative_thesis = inst_context.narrative.thesis
                                trade._narrative_conviction = inst_context.narrative.conviction
                            else:
                                trade._narrative_thesis = "No narrative available."
                                trade._narrative_conviction = "NONE"
                                
                            trade._divergence_score = getattr(signal, 'divergence_score', 0)
                            trade._is_paper_trade = getattr(signal, 'is_paper_trade', False)
                            
                            all_trades.append(trade)
                            
                except Exception as e:
                    import traceback
                    print(f"  ❌ {name} detector failed on {symbol}: {e}")
                    traceback.print_exc()
                    
        # RUN MISSION WALLET HOOK
        from live_monitoring.core.mission_wallet import MissionWallet
        wallet = MissionWallet()
        net_pnl = sum([t.pnl_pct for t in all_trades])
        donation_usd = wallet.record(date_str, net_pnl, len(all_trades))
                    
        # 4. Compile results structure identical to DailyBacktestResult
        return self._compile_daily_results(date_str, market_ctx, all_signals, all_trades, donation_usd)
        
    def _compile_daily_results(self, date_str: str, market_ctx: Dict, signals: List[Signal], trades: List[TradeResult], donation_usd: float = 0.0) -> Dict[str, Any]:
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
            "mission_wallet_donation_usd": donation_usd,
            "trades": [
                {
                    "symbol": t.signal.symbol,
                    "direction": t.signal.direction,
                    "entry_price": t.signal.entry_price,
                    "exit_price": t.exit_price,
                    "pnl_pct": t.pnl_pct,
                    "outcome": t.outcome,
                    "narrative_conviction": getattr(t, '_narrative_conviction', 'NONE'),
                    "narrative_thesis": getattr(t, '_narrative_thesis', ''),
                    "divergence_score": getattr(t, '_divergence_score', 0),
                    "is_paper_trade": getattr(t, '_is_paper_trade', False)
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
