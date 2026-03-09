import os
import json
from datetime import datetime
from typing import Dict, Any

class ReplayReporter:
    """
    Handles JSON export of backtest/replay results, decoupling reporting 
    logic from engine execution logic.
    """
    
    def __init__(self, output_dir: str = None):
        if not output_dir:
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.output_dir = os.path.join(base_path, "backtesting", "reports")
        else:
            self.output_dir = output_dir
            
        os.makedirs(self.output_dir, exist_ok=True)
        
    def save_session_replay(self, date_str: str, results: Dict[str, Any]) -> str:
        """
        Saves the results of a single session replay. 
        Format: session_replay_YYYYMMDD.json
        """
        date_formatted = date_str.replace("-", "")
        filename = f"session_replay_{date_formatted}.json"
        filepath = os.path.join(self.output_dir, filename)
        
        output = {
            "timestamp_generated": datetime.now().isoformat(),
            "session_date": date_str,
            "market_context": {
                "vix": results.get("vix", 20.0),
                "trend": results.get("market_direction", "UNKNOWN")
            },
            "performance": {
                "total_signals": results.get("total_signals", 0),
                "total_trades": results.get("total_trades", 0),
                "total_wins": results.get("total_wins", 0),
                "total_losses": results.get("total_losses", 0),
                "win_rate": results.get("win_rate", 0),
                "total_pnl": results.get("total_pnl", 0)
            },
            "trade_log": results.get("trades", [])
        }
        
        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2, default=str)
            
        print(f"\n💾 Session Replay saved to: {filepath}")
        return filepath
        
    def print_summary(self, results: Dict[str, Any]):
        """
        Prints a concise console summary.
        """
        print("\n📈 REPLAY SUMMARY")
        print("-" * 40)
        print(f"Signals Evaluated : {results.get('total_signals', 0)}")
        print(f"Trades Executed   : {results.get('total_trades', 0)}")
        print(f"Win Rate          : {results.get('win_rate', 0):.1f}%")
        print(f"Net P&L           : {results.get('total_pnl', 0):+.2f}%")
        
        trades = results.get('trades', [])
        if trades:
            print("\n🔍 TOP 5 TRADES:")
            # Sort by PnL descending
            sorted_trades = sorted(trades, key=lambda x: x['pnl_pct'], reverse=True)
            for t in sorted_trades[:5]:
                emoji = "✅" if t['outcome'] == 'WIN' else "❌"
                print(f"  {emoji} {t['symbol']} {t['direction']} at {t['entry_price']:.2f} -> {t['pnl_pct']:+.2f}%")
