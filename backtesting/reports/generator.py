"""
📊 REPORT GENERATOR
Generates formatted backtest reports
"""

from typing import List
from ..analysis.performance import PerformanceMetrics
from ..simulation.trade_simulator import Trade

class ReportGenerator:
    """Generates formatted backtest reports"""
    
    @staticmethod
    def generate_report(
        date: str,
        current_metrics: PerformanceMetrics,
        narrative_metrics: PerformanceMetrics,
        comparison: dict
    ) -> str:
        """Generate a formatted backtest report"""
        
        report = []
        report.append("=" * 70)
        report.append(f"🎯 BACKTEST REPORT: {date}")
        report.append("=" * 70)
        report.append("")
        
        # Current System
        report.append("📊 CURRENT SYSTEM (Always Sends):")
        report.append("-" * 70)
        report.append(f"  Total Trades: {current_metrics.total_trades}")
        report.append(f"  Winning Trades: {current_metrics.winning_trades}")
        report.append(f"  Losing Trades: {current_metrics.losing_trades}")
        report.append(f"  Win Rate: {current_metrics.win_rate:.1f}%")
        report.append(f"  Avg P&L per Trade: {current_metrics.avg_pnl_per_trade:+.2f}%")
        report.append(f"  Total P&L: {current_metrics.total_pnl:+.2f}%")
        if current_metrics.avg_win > 0:
            report.append(f"  Avg Win: {current_metrics.avg_win:+.2f}%")
        if current_metrics.avg_loss < 0:
            report.append(f"  Avg Loss: {current_metrics.avg_loss:+.2f}%")
        report.append(f"  Profit Factor: {current_metrics.profit_factor:.2f}")
        report.append(f"  Max Drawdown: {current_metrics.max_drawdown:.2f}%")
        report.append("")
        
        # Narrative Brain
        report.append("🧠 NARRATIVE BRAIN (Smart Filtering):")
        report.append("-" * 70)
        report.append(f"  Total Trades: {narrative_metrics.total_trades}")
        report.append(f"  Winning Trades: {narrative_metrics.winning_trades}")
        report.append(f"  Losing Trades: {narrative_metrics.losing_trades}")
        report.append(f"  Win Rate: {narrative_metrics.win_rate:.1f}%")
        report.append(f"  Avg P&L per Trade: {narrative_metrics.avg_pnl_per_trade:+.2f}%")
        report.append(f"  Total P&L: {narrative_metrics.total_pnl:+.2f}%")
        if narrative_metrics.avg_win > 0:
            report.append(f"  Avg Win: {narrative_metrics.avg_win:+.2f}%")
        if narrative_metrics.avg_loss < 0:
            report.append(f"  Avg Loss: {narrative_metrics.avg_loss:+.2f}%")
        report.append(f"  Profit Factor: {narrative_metrics.profit_factor:.2f}")
        report.append(f"  Max Drawdown: {narrative_metrics.max_drawdown:.2f}%")
        report.append("")
        
        # Comparison
        report.append("🎯 COMPARISON:")
        report.append("-" * 70)
        report.append(f"  Win Rate Change: {comparison['win_rate_diff']:+.1f}%")
        report.append(f"  Total P&L Change: {comparison['total_pnl_diff']:+.2f}%")
        report.append(f"  Trade Reduction: {comparison['trade_reduction']} trades ({comparison['trade_reduction_pct']:.1f}% fewer)")
        report.append(f"  Avg P&L Change: {comparison['avg_pnl_diff']:+.2f}%")
        report.append("")
        
        # Analysis
        report.append("💡 ANALYSIS:")
        report.append("-" * 70)
        if comparison['win_rate_diff'] > 5:
            report.append(f"  ✅ Narrative Brain IMPROVES win rate by {comparison['win_rate_diff']:.1f}%")
        elif comparison['win_rate_diff'] < -5:
            report.append(f"  ⚠️  Narrative Brain reduces win rate by {abs(comparison['win_rate_diff']):.1f}%")
        else:
            report.append(f"  ⚠️  Win rate similar ({comparison['win_rate_diff']:+.1f}%)")
        
        if comparison['total_pnl_diff'] > 0:
            report.append(f"  ✅ Narrative Brain improves P&L by {comparison['total_pnl_diff']:+.2f}%")
        elif comparison['total_pnl_diff'] < 0:
            report.append(f"  ⚠️  Narrative Brain reduces P&L by {abs(comparison['total_pnl_diff']):.2f}%")
        else:
            report.append(f"  ⚠️  P&L similar")
        
        if comparison['trade_reduction'] > 0:
            report.append(f"  ✅ Narrative Brain reduces spam by {comparison['trade_reduction']} trades ({comparison['trade_reduction_pct']:.1f}%)")
        
        report.append("")
        report.append("=" * 70)
        
        return "\n".join(report)
    
    @staticmethod
    def generate_trade_details(trades: List[Trade], limit: int = 10) -> str:
        """Generate detailed trade list"""
        if not trades:
            return "  No trades executed"
        
        details = []
        for i, trade in enumerate(trades[:limit]):
            result = "✅ WIN" if trade.outcome == 'WIN' else "❌ LOSS"
            details.append(
                f"  {i+1:2d}. {trade.entry_time.strftime('%H:%M')} | "
                f"{trade.symbol} {trade.direction:5} | "
                f"{result} | "
                f"P&L: {trade.pnl_pct:+.2f}% | "
                f"Conf: {trade.alert_confluence:.0f} | "
                f"Move: {trade.max_move_observed:.2f}%"
            )
        
        if len(trades) > limit:
            details.append(f"  ... and {len(trades) - limit} more trades")
        
        return "\n".join(details)

