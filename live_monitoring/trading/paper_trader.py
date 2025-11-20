#!/usr/bin/env python3
"""
PAPER TRADER - ALPACA INTEGRATION
==================================
Executes paper trades based on live signals using Alpaca's Paper Trading API.

Features:
- Real-time order execution (market/limit orders)
- Position tracking
- P&L calculation
- Trade logging
- Risk management integration

Author: Alpha's AI Hedge Fund
Date: 2024-10-18
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
import logging
from dataclasses import dataclass
import json

# Add paths
sys.path.append(str(Path(__file__).parent.parent / 'core'))

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderType
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    logging.warning("Alpaca SDK not installed. Run: pip install alpaca-py")

from signal_generator import LiveSignal

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Represents an executed trade"""
    timestamp: datetime
    symbol: str
    action: str  # BUY or SELL
    quantity: int
    entry_price: float
    stop_loss: float
    take_profit: float
    signal_type: str
    confidence: float
    order_id: Optional[str] = None
    status: str = "PENDING"  # PENDING, FILLED, PARTIAL, REJECTED, CANCELLED
    fill_price: Optional[float] = None
    fill_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None


class PaperTrader:
    """
    Executes paper trades via Alpaca Paper Trading API
    """
    def __init__(self, 
                 api_key: Optional[str] = None,
                 secret_key: Optional[str] = None,
                 base_url: str = "https://paper-api.alpaca.markets",
                 initial_capital: float = 100000.0,
                 max_position_size_pct: float = 0.02):
        """
        Initialize Paper Trader
        
        Args:
            api_key: Alpaca API key (or set ALPACA_API_KEY env var)
            secret_key: Alpaca secret key (or set ALPACA_SECRET_KEY env var)
            base_url: Alpaca API base URL (paper trading by default)
            initial_capital: Starting capital
            max_position_size_pct: Max % of capital per trade (default 2%)
        """
        # Get credentials from env if not provided
        self.api_key = api_key or os.getenv('ALPACA_API_KEY')
        self.secret_key = secret_key or os.getenv('ALPACA_SECRET_KEY')
        
        if not self.api_key or not self.secret_key:
            logger.warning("⚠️ Alpaca credentials not found!")
            logger.warning("   Set ALPACA_API_KEY and ALPACA_SECRET_KEY env vars")
            logger.warning("   Or pass api_key and secret_key to PaperTrader()")
            self.client = None
        elif not ALPACA_AVAILABLE:
            logger.error("❌ Alpaca SDK not installed!")
            self.client = None
        else:
            try:
                self.client = TradingClient(self.api_key, self.secret_key, paper=True)
                logger.info("✅ Alpaca Paper Trading connected")
                
                # Get account info
                account = self.client.get_account()
                logger.info(f"   Account: {account.account_number}")
                logger.info(f"   Buying Power: ${float(account.buying_power):,.2f}")
                logger.info(f"   Cash: ${float(account.cash):,.2f}")
                logger.info(f"   Portfolio Value: ${float(account.portfolio_value):,.2f}")
            except Exception as e:
                logger.error(f"❌ Failed to connect to Alpaca: {e}")
                self.client = None
        
        self.initial_capital = initial_capital
        self.max_position_size_pct = max_position_size_pct
        
        # Track trades
        self.trades: List[Trade] = []
        self.open_positions: Dict[str, Trade] = {}
        
        # Create logs directory
        self.log_dir = Path("logs/paper_trading")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"📊 Paper Trader initialized")
        logger.info(f"   Initial Capital: ${initial_capital:,.2f}")
        logger.info(f"   Max Position Size: {max_position_size_pct:.1%}")
    
    def is_connected(self) -> bool:
        """Check if connected to Alpaca"""
        return self.client is not None
    
    def execute_signal(self, signal: LiveSignal) -> Optional[Trade]:
        """
        Execute a trade based on a live signal
        
        Args:
            signal: LiveSignal object
        
        Returns:
            Trade object if successful, None otherwise
        """
        if not self.is_connected():
            logger.warning(f"⚠️ Cannot execute {signal.action} {signal.symbol} - Not connected to Alpaca")
            return None
        
        if not signal.is_actionable:
            logger.info(f"⚪ Skipping {signal.symbol} - Signal not actionable")
            return None
        
        # Check if we already have a position
        if signal.symbol in self.open_positions:
            logger.info(f"⚪ Skipping {signal.symbol} - Position already open")
            return None
        
        try:
            # Get current account info
            account = self.client.get_account()
            buying_power = float(account.buying_power)
            
            # Calculate position size
            position_value = buying_power * signal.position_size_pct
            quantity = int(position_value / signal.entry_price)
            
            if quantity <= 0:
                logger.warning(f"⚠️ Position size too small for {signal.symbol} (quantity: {quantity})")
                return None
            
            # Create order
            order_side = OrderSide.BUY if signal.action == "BUY" else OrderSide.SELL
            
            # Use market order for simplicity (can switch to limit orders)
            order_data = MarketOrderRequest(
                symbol=signal.symbol,
                qty=quantity,
                side=order_side,
                time_in_force=TimeInForce.DAY
            )
            
            # Submit order
            order = self.client.submit_order(order_data)
            
            # Create trade record
            trade = Trade(
                timestamp=datetime.now(),
                symbol=signal.symbol,
                action=signal.action,
                quantity=quantity,
                entry_price=signal.entry_price,
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                signal_type=signal.signal_type,
                confidence=signal.confidence,
                order_id=str(order.id),
                status="PENDING"
            )
            
            self.trades.append(trade)
            self.open_positions[signal.symbol] = trade
            
            logger.info(f"✅ ORDER SUBMITTED: {signal.action} {quantity} {signal.symbol} @ ${signal.entry_price:.2f}")
            logger.info(f"   Order ID: {order.id}")
            logger.info(f"   Stop Loss: ${signal.stop_loss:.2f} | Take Profit: ${signal.take_profit:.2f}")
            logger.info(f"   Signal Type: {signal.signal_type} | Confidence: {signal.confidence:.0f}%")
            
            # Log to file
            self._log_trade(trade, "ORDER_SUBMITTED")
            
            return trade
            
        except Exception as e:
            logger.error(f"❌ Failed to execute {signal.action} {signal.symbol}: {e}")
            return None
    
    def update_positions(self):
        """
        Update open positions with current prices and check stop loss / take profit
        """
        if not self.is_connected():
            return
        
        if not self.open_positions:
            return
        
        try:
            # Get all open orders
            orders = self.client.get_orders()
            
            # Get all positions
            positions = self.client.get_all_positions()
            
            for symbol, trade in list(self.open_positions.items()):
                # Check if order filled
                if trade.status == "PENDING":
                    matching_orders = [o for o in orders if str(o.id) == trade.order_id]
                    if matching_orders:
                        order = matching_orders[0]
                        if order.status == "filled":
                            trade.status = "FILLED"
                            trade.fill_price = float(order.filled_avg_price)
                            trade.fill_time = order.filled_at
                            logger.info(f"✅ ORDER FILLED: {trade.symbol} @ ${trade.fill_price:.2f}")
                            self._log_trade(trade, "ORDER_FILLED")
                
                # Check current position
                matching_positions = [p for p in positions if p.symbol == symbol]
                if matching_positions:
                    position = matching_positions[0]
                    current_price = float(position.current_price)
                    unrealized_pl = float(position.unrealized_pl)
                    unrealized_plpc = float(position.unrealized_plpc)
                    
                    logger.debug(f"📊 {symbol}: ${current_price:.2f} | P/L: ${unrealized_pl:.2f} ({unrealized_plpc:+.2%})")
                    
                    # Check stop loss
                    if trade.action == "BUY" and current_price <= trade.stop_loss:
                        logger.warning(f"🛑 STOP LOSS HIT: {symbol} @ ${current_price:.2f}")
                        self._close_position(trade, current_price, "STOP_LOSS")
                    elif trade.action == "SELL" and current_price >= trade.stop_loss:
                        logger.warning(f"🛑 STOP LOSS HIT: {symbol} @ ${current_price:.2f}")
                        self._close_position(trade, current_price, "STOP_LOSS")
                    
                    # Check take profit
                    elif trade.action == "BUY" and current_price >= trade.take_profit:
                        logger.info(f"🎯 TAKE PROFIT HIT: {symbol} @ ${current_price:.2f}")
                        self._close_position(trade, current_price, "TAKE_PROFIT")
                    elif trade.action == "SELL" and current_price <= trade.take_profit:
                        logger.info(f"🎯 TAKE PROFIT HIT: {symbol} @ ${current_price:.2f}")
                        self._close_position(trade, current_price, "TAKE_PROFIT")
        
        except Exception as e:
            logger.error(f"❌ Error updating positions: {e}")
    
    def _close_position(self, trade: Trade, exit_price: float, reason: str):
        """
        Close a position
        
        Args:
            trade: Trade to close
            exit_price: Exit price
            reason: Reason for closing (STOP_LOSS, TAKE_PROFIT, MANUAL)
        """
        try:
            # Close position via Alpaca
            self.client.close_position(trade.symbol)
            
            # Update trade record
            trade.exit_price = exit_price
            trade.exit_time = datetime.now()
            
            # Calculate P&L
            if trade.action == "BUY":
                trade.pnl = (exit_price - trade.fill_price) * trade.quantity
                trade.pnl_pct = (exit_price / trade.fill_price - 1) * 100
            else:  # SELL
                trade.pnl = (trade.fill_price - exit_price) * trade.quantity
                trade.pnl_pct = (trade.fill_price / exit_price - 1) * 100
            
            # Remove from open positions
            del self.open_positions[trade.symbol]
            
            logger.info(f"{'✅' if trade.pnl > 0 else '❌'} POSITION CLOSED: {trade.symbol} ({reason})")
            logger.info(f"   Entry: ${trade.fill_price:.2f} | Exit: ${exit_price:.2f}")
            logger.info(f"   P&L: ${trade.pnl:+.2f} ({trade.pnl_pct:+.2f}%)")
            
            self._log_trade(trade, f"POSITION_CLOSED_{reason}")
            
        except Exception as e:
            logger.error(f"❌ Failed to close position {trade.symbol}: {e}")
    
    def _log_trade(self, trade: Trade, event: str):
        """Log trade to file"""
        log_file = self.log_dir / f"trades_{datetime.now().strftime('%Y%m%d')}.jsonl"
        
        log_entry = {
            "timestamp": trade.timestamp.isoformat(),
            "event": event,
            "symbol": trade.symbol,
            "action": trade.action,
            "quantity": trade.quantity,
            "entry_price": trade.entry_price,
            "fill_price": trade.fill_price,
            "exit_price": trade.exit_price,
            "stop_loss": trade.stop_loss,
            "take_profit": trade.take_profit,
            "signal_type": trade.signal_type,
            "confidence": trade.confidence,
            "order_id": trade.order_id,
            "status": trade.status,
            "pnl": trade.pnl,
            "pnl_pct": trade.pnl_pct
        }
        
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    def get_summary(self) -> Dict[str, Any]:
        """Get trading summary"""
        closed_trades = [t for t in self.trades if t.exit_price is not None]
        
        if not closed_trades:
            return {
                "total_trades": len(self.trades),
                "open_positions": len(self.open_positions),
                "closed_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0
            }
        
        wins = [t for t in closed_trades if t.pnl > 0]
        losses = [t for t in closed_trades if t.pnl <= 0]
        
        total_pnl = sum(t.pnl for t in closed_trades)
        win_rate = len(wins) / len(closed_trades) if closed_trades else 0.0
        avg_win = sum(t.pnl for t in wins) / len(wins) if wins else 0.0
        avg_loss = sum(t.pnl for t in losses) / len(losses) if losses else 0.0
        
        return {
            "total_trades": len(self.trades),
            "open_positions": len(self.open_positions),
            "closed_trades": len(closed_trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate * 100,
            "total_pnl": total_pnl,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "largest_win": max((t.pnl for t in wins), default=0.0),
            "largest_loss": min((t.pnl for t in losses), default=0.0)
        }


if __name__ == "__main__":
    # Test connection
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
    
    trader = PaperTrader()
    
    if trader.is_connected():
        print("\n✅ Successfully connected to Alpaca Paper Trading!")
        print("\n📊 Account Summary:")
        summary = trader.get_summary()
        for key, value in summary.items():
            print(f"   {key}: {value}")
    else:
        print("\n❌ Not connected to Alpaca")
        print("\n📋 Setup Instructions:")
        print("   1. Sign up for Alpaca: https://alpaca.markets/")
        print("   2. Get your Paper Trading API keys")
        print("   3. Set environment variables:")
        print("      export ALPACA_API_KEY='your_api_key'")
        print("      export ALPACA_SECRET_KEY='your_secret_key'")
        print("   4. Install Alpaca SDK:")
        print("      pip install alpaca-py")

