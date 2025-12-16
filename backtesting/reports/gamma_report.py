"""
🎲 GAMMA TRACKER REPORT GENERATOR
Generates formatted reports for gamma tracker backtests
"""

from dataclasses import dataclass
from typing import Dict, List
from ..analysis.performance import PerformanceMetrics
from ..simulation.trade_simulator import Trade


@dataclass
class GammaMetrics:
    """Gamma-specific metrics"""
    avg_gamma_score: float
    avg_pc_ratio: float
    avg_max_pain_distance: float
    trades_by_direction: Dict[str, int]
    win_rate_by_direction: Dict[str, float]


class GammaReportGenerator:
    """Generates reports for gamma tracker backtests"""
    
    @staticmethod
    def calculate_gamma_metrics(trades: List[Trade]) -> GammaMetrics:
        """Calculate gamma-specific metrics from trades"""
        if not trades:
            return GammaMetrics(
                avg_gamma_score=0.0,
                avg_pc_ratio=0.0,
                avg_max_pain_distance=0.0,
                trades_by_direction={},
                win_rate_by_direction={}
            )
        
        # Extract gamma scores from alert_confluence (we stored score there)
        scores = [t.alert_confluence for t in trades]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        # Group by direction
        trades_by_dir = {"UP": 0, "DOWN": 0}
        wins_by_dir = {"UP": 0, "DOWN": 0}
        
        for trade in trades:
            # Direction is LONG for UP signals, SHORT for DOWN signals
            # We can infer from trade direction
            if trade.direction == "LONG":
                dir_key = "UP"
            else:
                dir_key = "DOWN"
            
            trades_by_dir[dir_key] += 1
            if trade.outcome == "WIN":
                wins_by_dir[dir_key] += 1
        
        # Calculate win rates by direction
        win_rate_by_dir = {}
        for dir_key in trades_by_dir.keys():
            count = trades_by_dir[dir_key]
            wins = wins_by_dir[dir_key]
            win_rate_by_dir[dir_key] = (wins / count * 100) if count > 0 else 0
        
        return GammaMetrics(
            avg_gamma_score=avg_score,
            avg_pc_ratio=0.0,  # Not stored in Trade, would need to enhance
            avg_max_pain_distance=0.0,  # Not stored in Trade, would need to enhance
            trades_by_direction=trades_by_dir,
            win_rate_by_direction=win_rate_by_dir
        )
    
    @staticmethod
    def generate_report(metrics: PerformanceMetrics, gamma_metrics: GammaMetrics,
                       date_range: str = "", symbols: List[str] = None) -> str:
        """
        Generate formatted backtest report.
        
        Args:
            metrics: Performance metrics
            gamma_metrics: Gamma-specific metrics
            date_range: Date range string (e.g., "2025-12-01 to 2025-12-15")
            symbols: List of symbols tested
        
        Returns:
            Formatted report string
        """
        report = []
        report.append("\n" + "="*70)
        report.append("🎲 GAMMA TRACKER BACKTEST RESULTS")
        report.append("="*70)
        
        if date_range:
            report.append(f"   Date Range: {date_range}")
        if symbols:
            report.append(f"   Symbols: {', '.join(symbols)}")
        report.append("")
        
        # Overall performance
        report.append("📊 OVERALL PERFORMANCE")
        report.append("-"*70)
        report.append(f"   Total Trades:     {metrics.total_trades}")
        report.append(f"   Winning Trades:   {metrics.winning_trades} ({metrics.win_rate:.1f}%)")
        report.append(f"   Losing Trades:    {metrics.losing_trades}")
        report.append(f"   Total P&L:        {metrics.total_pnl:+.2f}%")
        report.append(f"   Avg Win:          {metrics.avg_win:+.2f}%")
        report.append(f"   Avg Loss:         {metrics.avg_loss:+.2f}%")
        report.append(f"   Profit Factor:    {metrics.profit_factor:.2f}")
        report.append(f"   Max Drawdown:     {metrics.max_drawdown:.2f}%")
        report.append(f"   Sharpe Ratio:     {metrics.sharpe_ratio:.2f}")
        report.append("")
        
        # Gamma-specific metrics
        report.append("🎲 GAMMA-SPECIFIC METRICS")
        report.append("-"*70)
        report.append(f"   Avg Gamma Score:  {gamma_metrics.avg_gamma_score:.1f}/100")
        report.append(f"   Trades by Direction:")
        for direction, count in gamma_metrics.trades_by_direction.items():
            win_rate = gamma_metrics.win_rate_by_direction.get(direction, 0)
            report.append(f"      {direction}: {count} trades ({win_rate:.1f}% win rate)")
        report.append("")
        
        # Validation criteria
        report.append("🎯 VALIDATION CRITERIA")
        report.append("-"*70)
        
        win_rate = metrics.win_rate
        profit_factor = metrics.profit_factor
        avg_rr = metrics.avg_win / abs(metrics.avg_loss) if metrics.avg_loss != 0 else 0
        
        criteria = [
            ("Win Rate >55%", win_rate > 55, f"{win_rate:.1f}%"),
            ("Profit Factor >1.5", profit_factor > 1.5, f"{profit_factor:.2f}"),
            ("Avg R/R >2.0", avg_rr > 2.0, f"{avg_rr:.2f}:1"),
            ("Min 5 Trades", metrics.total_trades >= 5, f"{metrics.total_trades} trades"),
        ]
        
        passed = 0
        for name, condition, value in criteria:
            status = "✅ PASS" if condition else "❌ FAIL"
            report.append(f"   {status}: {name} ({value})")
            if condition:
                passed += 1
        
        report.append("")
        report.append(f"📊 Result: {passed}/{len(criteria)} criteria passed")
        
        if passed == len(criteria):
            report.append("🎉 BACKTEST PASSED - GAMMA TRACKER READY FOR PRODUCTION!")
        else:
            report.append("⚠️ BACKTEST FAILED - TUNE THRESHOLDS")
        
        report.append("="*70)
        
        return "\n".join(report)


