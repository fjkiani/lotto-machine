"""
🔥 SQUEEZE DETECTOR REPORT GENERATOR
Generates formatted reports for squeeze detector backtests
"""

from dataclasses import dataclass
from typing import Dict, List
from ..analysis.performance import PerformanceMetrics
from ..simulation.trade_simulator import Trade


@dataclass
class SqueezeMetrics:
    """Squeeze-specific metrics"""
    avg_squeeze_score: float
    avg_si_pct: float
    avg_borrow_fee: float
    avg_ftd_spike: float
    trades_by_score_range: Dict[str, int]
    win_rate_by_score_range: Dict[str, float]


class SqueezeReportGenerator:
    """Generates reports for squeeze detector backtests"""
    
    @staticmethod
    def calculate_squeeze_metrics(trades: List[Trade]) -> SqueezeMetrics:
        """Calculate squeeze-specific metrics from trades"""
        if not trades:
            return SqueezeMetrics(
                avg_squeeze_score=0.0,
                avg_si_pct=0.0,
                avg_borrow_fee=0.0,
                avg_ftd_spike=0.0,
                trades_by_score_range={},
                win_rate_by_score_range={}
            )
        
        # Extract squeeze scores from alert_confluence (we stored score there)
        scores = [t.alert_confluence for t in trades]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        # Group by score range
        trades_by_range = {"70-74": 0, "75-79": 0, "80-100": 0}
        wins_by_range = {"70-74": 0, "75-79": 0, "80-100": 0}
        
        for trade in trades:
            score = trade.alert_confluence
            if score >= 80:
                range_key = "80-100"
            elif score >= 75:
                range_key = "75-79"
            else:
                range_key = "70-74"
            
            trades_by_range[range_key] += 1
            if trade.outcome == "WIN":
                wins_by_range[range_key] += 1
        
        # Calculate win rates by range
        win_rate_by_range = {}
        for range_key in trades_by_range.keys():
            count = trades_by_range[range_key]
            wins = wins_by_range[range_key]
            win_rate_by_range[range_key] = (wins / count * 100) if count > 0 else 0
        
        return SqueezeMetrics(
            avg_squeeze_score=avg_score,
            avg_si_pct=0.0,  # Not stored in Trade, would need to enhance
            avg_borrow_fee=0.0,  # Not stored in Trade, would need to enhance
            avg_ftd_spike=0.0,  # Not stored in Trade, would need to enhance
            trades_by_score_range=trades_by_range,
            win_rate_by_score_range=win_rate_by_range
        )
    
    @staticmethod
    def generate_report(metrics: PerformanceMetrics, squeeze_metrics: SqueezeMetrics,
                       date_range: str = "", symbols: List[str] = None) -> str:
        """
        Generate formatted backtest report.
        
        Args:
            metrics: Performance metrics
            squeeze_metrics: Squeeze-specific metrics
            date_range: Date range string (e.g., "2025-12-01 to 2025-12-15")
            symbols: List of symbols tested
        
        Returns:
            Formatted report string
        """
        report = []
        report.append("\n" + "="*70)
        report.append("🔥 SQUEEZE DETECTOR BACKTEST RESULTS")
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
        report.append(f"   Total P&L:        {metrics.total_pnl:.2f}%")
        report.append("")
        
        # Risk metrics
        report.append("📈 RISK METRICS")
        report.append("-"*70)
        report.append(f"   Avg Win:          {metrics.avg_win:.2f}%")
        report.append(f"   Avg Loss:         {metrics.avg_loss:.2f}%")
        report.append(f"   Profit Factor:    {metrics.profit_factor:.2f}")
        report.append(f"   Max Drawdown:     {metrics.max_drawdown:.2f}%")
        report.append(f"   Sharpe Ratio:     {metrics.sharpe_ratio:.2f}")
        report.append("")
        
        # Squeeze-specific metrics
        report.append("🔥 SQUEEZE METRICS")
        report.append("-"*70)
        report.append(f"   Avg Squeeze Score: {squeeze_metrics.avg_squeeze_score:.1f}/100")
        report.append("")
        
        # Performance by score range
        if squeeze_metrics.trades_by_score_range:
            report.append("📊 PERFORMANCE BY SCORE RANGE")
            report.append("-"*70)
            for range_key in sorted(squeeze_metrics.trades_by_score_range.keys()):
                count = squeeze_metrics.trades_by_score_range[range_key]
                win_rate = squeeze_metrics.win_rate_by_score_range.get(range_key, 0)
                report.append(f"   {range_key}: {count} trades, {win_rate:.1f}% win rate")
            report.append("")
        
        # Validation criteria
        report.append("✅ VALIDATION CRITERIA")
        report.append("-"*70)
        
        criteria = [
            ("Win Rate >55%", metrics.win_rate >= 55),
            ("Avg R/R >2.0", metrics.avg_win / abs(metrics.avg_loss) >= 2.0 if metrics.avg_loss < 0 else False),
            ("Max DD <10%", metrics.max_drawdown < 10),
            ("Sharpe >1.5", metrics.sharpe_ratio >= 1.5),
            ("Profit Factor >1.8", metrics.profit_factor >= 1.8),
            ("Min 10 Trades", metrics.total_trades >= 10),
        ]
        
        passed = sum(1 for _, check in criteria if check)
        total = len(criteria)
        
        for name, check in criteria:
            status = "✅ PASS" if check else "❌ FAIL"
            report.append(f"   {status}: {name}")
        
        report.append("")
        report.append(f"   RESULT: {passed}/{total} criteria passed")
        
        if passed == total:
            report.append("   🎉 BACKTEST PASSED - READY FOR PAPER TRADING!")
        elif passed >= total * 0.8:
            report.append("   ⚠️  BACKTEST MOSTLY PASSED - REVIEW NEEDED")
        else:
            report.append("   ❌ BACKTEST FAILED - TUNE THRESHOLDS")
        
        report.append("="*70)
        
        return "\n".join(report)
    
    @staticmethod
    def save_report(report: str, filename: str = None):
        """Save report to file"""
        from datetime import datetime
        
        if filename is None:
            filename = f"backtest_squeeze_{datetime.now().strftime('%Y%m%d')}.txt"
        
        with open(filename, 'w') as f:
            f.write(report)
        
        return filename


