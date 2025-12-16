"""
📊 PERFORMANCE ANALYZER
Calculates performance metrics from trades
"""

from dataclasses import dataclass
from typing import List
from ..simulation.trade_simulator import Trade

@dataclass
class PerformanceMetrics:
    """Performance metrics for a backtest"""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_pnl_per_trade: float
    total_pnl: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    trades: List[Trade]

class PerformanceAnalyzer:
    """Analyzes trade performance"""
    
    @staticmethod
    def analyze(trades: List[Trade]) -> PerformanceMetrics:
        """Calculate performance metrics from trades"""
        if not trades:
            return PerformanceMetrics(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                avg_pnl_per_trade=0.0,
                total_pnl=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                profit_factor=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                trades=[]
            )
        
        wins = [t for t in trades if t.outcome == 'WIN']
        losses = [t for t in trades if t.outcome == 'LOSS']
        
        total_pnl = sum(t.pnl_pct for t in trades)
        avg_pnl = total_pnl / len(trades) if trades else 0
        
        avg_win = sum(t.pnl_pct for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.pnl_pct for t in losses) / len(losses) if losses else 0
        
        # Profit factor
        total_wins = sum(t.pnl_pct for t in wins) if wins else 0
        total_losses = abs(sum(t.pnl_pct for t in losses)) if losses else 0
        profit_factor = total_wins / total_losses if total_losses > 0 else (float('inf') if total_wins > 0 else 0)
        
        # Max drawdown (simplified - cumulative P&L)
        cumulative_pnl = 0
        peak = 0
        max_dd = 0
        for trade in trades:
            cumulative_pnl += trade.pnl_pct
            if cumulative_pnl > peak:
                peak = cumulative_pnl
            drawdown = peak - cumulative_pnl
            if drawdown > max_dd:
                max_dd = drawdown
        
        # Sharpe ratio (simplified - using P&L std dev)
        if len(trades) > 1:
            pnl_values = [t.pnl_pct for t in trades]
            import statistics
            std_dev = statistics.stdev(pnl_values) if len(pnl_values) > 1 else 0
            sharpe = (avg_pnl / std_dev) if std_dev > 0 else 0
        else:
            sharpe = 0
        
        return PerformanceMetrics(
            total_trades=len(trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate=(len(wins) / len(trades) * 100) if trades else 0,
            avg_pnl_per_trade=avg_pnl,
            total_pnl=total_pnl,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            max_drawdown=max_dd,
            sharpe_ratio=sharpe,
            trades=trades
        )
    
    @staticmethod
    def compare(current_metrics: PerformanceMetrics, narrative_metrics: PerformanceMetrics) -> dict:
        """Compare two performance metrics"""
        return {
            'win_rate_diff': narrative_metrics.win_rate - current_metrics.win_rate,
            'total_pnl_diff': narrative_metrics.total_pnl - current_metrics.total_pnl,
            'trade_reduction': current_metrics.total_trades - narrative_metrics.total_trades,
            'trade_reduction_pct': ((current_metrics.total_trades - narrative_metrics.total_trades) / current_metrics.total_trades * 100) if current_metrics.total_trades > 0 else 0,
            'avg_pnl_diff': narrative_metrics.avg_pnl_per_trade - current_metrics.avg_pnl_per_trade
        }



