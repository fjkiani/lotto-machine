"""
💰 TRADE CALCULATOR TOOL
Calculate trade setups with entry, stop, target
"""

import logging
from typing import Dict, Any, List
from datetime import datetime
from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class TradeCalculatorTool(BaseTool):
    """
    Trade Calculator Tool
    
    Provides:
    - Full trade setup calculation
    - Risk/reward analysis
    - Position sizing
    """
    
    @property
    def name(self) -> str:
        return "trade_calculator"
    
    @property
    def description(self) -> str:
        return "Calculate trade setups with entry, stop, target"
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "calculate_setup - Full trade setup",
            "risk_reward - Risk/reward calculation",
            "position_size - Position sizing"
        ]
    
    @property
    def keywords(self) -> List[str]:
        return [
            "trade", "setup", "entry", "stop", "target",
            "risk", "reward", "position", "size", "shares",
            "long", "short", "buy", "sell"
        ]
    
    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Execute trade calculator query"""
        symbol = params.get("symbol", "SPY").upper()
        direction = params.get("direction", "LONG").upper()
        entry = params.get("entry", None)
        
        try:
            return self._calculate_setup(symbol, direction, entry)
        except Exception as e:
            logger.error(f"Trade Calculator error: {e}")
            return ToolResult(
                success=False,
                data={},
                error=str(e)
            )
    
    def _calculate_setup(self, symbol: str, direction: str, entry: float = None) -> ToolResult:
        """Calculate full trade setup"""
        setup_data = {
            "symbol": symbol,
            "direction": direction,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='5d', interval='1h')
            
            if hist.empty:
                return ToolResult(
                    success=False,
                    data={},
                    error="Could not fetch price data"
                )
            
            current_price = float(hist['Close'].iloc[-1])
            
            # Use provided entry or current price
            entry_price = entry if entry else current_price
            
            # Calculate ATR for stop/target
            high_low = hist['High'] - hist['Low']
            atr = float(high_low.rolling(14).mean().iloc[-1])
            
            # Calculate stop and target based on direction
            if direction == "LONG":
                stop_loss = entry_price - (atr * 1.5)
                take_profit = entry_price + (atr * 2.5)
            else:  # SHORT
                stop_loss = entry_price + (atr * 1.5)
                take_profit = entry_price - (atr * 2.5)
            
            # Risk/Reward
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
            rr_ratio = reward / risk if risk > 0 else 0
            
            setup_data.update({
                "current_price": current_price,
                "entry": round(entry_price, 2),
                "stop_loss": round(stop_loss, 2),
                "take_profit": round(take_profit, 2),
                "risk_pct": round((risk / entry_price) * 100, 2),
                "reward_pct": round((reward / entry_price) * 100, 2),
                "risk_reward_ratio": round(rr_ratio, 2),
                "atr": round(atr, 2),
                "hold_time": "15-60 min" if atr < 1 else "1-4 hours"
            })
            
            # Position sizing (assuming $10,000 capital, 2% risk)
            capital = 10000
            risk_amount = capital * 0.02
            shares = int(risk_amount / risk) if risk > 0 else 0
            setup_data["suggested_shares"] = shares
            setup_data["position_value"] = round(shares * entry_price, 2)
            
        except Exception as e:
            logger.error(f"Setup calculation error: {e}")
            return ToolResult(
                success=False,
                data={},
                error=str(e)
            )
        
        return ToolResult(
            success=True,
            data=setup_data
        )
    
    def format_response(self, result: ToolResult) -> str:
        """Format result for Discord display"""
        if not result.success:
            return f"❌ Error: {result.error}"
        
        data = result.data
        symbol = data.get("symbol", "SPY")
        direction = data.get("direction", "LONG")
        
        dir_emoji = "📈" if direction == "LONG" else "📉"
        
        lines = [f"🎯 **{symbol} {direction} Setup** {dir_emoji}\n"]
        
        lines.append(f"💰 **Entry:** ${data.get('entry', 0):.2f}")
        lines.append(f"🛑 **Stop Loss:** ${data.get('stop_loss', 0):.2f} ({data.get('risk_pct', 0):.2f}% risk)")
        lines.append(f"🎯 **Target:** ${data.get('take_profit', 0):.2f} ({data.get('reward_pct', 0):.2f}% reward)")
        lines.append(f"⚖️ **R/R Ratio:** {data.get('risk_reward_ratio', 0):.1f}:1")
        lines.append(f"⏱️ **Hold Time:** {data.get('hold_time', 'TBD')}")
        
        if data.get("suggested_shares"):
            lines.append(f"\n📊 **Position Size:** {data['suggested_shares']} shares (${data['position_value']:,.2f})")
            lines.append(f"*Based on $10K capital, 2% risk*")
        
        return "\n".join(lines)


