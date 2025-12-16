"""
📊 SIGNAL REPORT GENERATOR
Generates production-ready signal analysis reports
"""

from typing import List
from ..data.alerts_loader import SignalAlert
from ..analysis.signal_analyzer import SignalSummary

class SignalReportGenerator:
    """Generates formatted signal analysis reports"""
    
    @staticmethod
    def generate_report(summary: SignalSummary) -> str:
        """Generate a comprehensive signal analysis report"""
        
        report = []
        report.append("=" * 80)
        report.append(f"📊 PRODUCTION SIGNAL ANALYSIS: {summary.date}")
        report.append("=" * 80)
        report.append("")
        
        # Overview
        report.append("📈 OVERVIEW:")
        report.append("-" * 80)
        report.append(f"  Total Signals: {summary.total_signals}")
        report.append(f"  Synthesis Signals: {summary.synthesis_signals}")
        report.append(f"  Narrative Brain: {summary.narrative_brain_signals}")
        report.append(f"  DP Alerts: {summary.dp_alerts}")
        report.append(f"  High Quality (≥70%): {summary.high_quality_signals}")
        if summary.avg_confluence > 0:
            report.append(f"  Avg Confluence: {summary.avg_confluence:.1f}%")
        report.append("")
        
        # Signal Types Breakdown
        if summary.signal_types:
            report.append("📋 SIGNAL TYPES:")
            report.append("-" * 80)
            for sig_type, count in sorted(summary.signal_types.items(), key=lambda x: x[1], reverse=True):
                report.append(f"  {sig_type:20s}: {count:3d}")
            report.append("")
        
        # Symbols
        if summary.symbols:
            report.append("🎯 SYMBOLS:")
            report.append("-" * 80)
            for symbol, count in sorted(summary.symbols.items(), key=lambda x: x[1], reverse=True):
                report.append(f"  {symbol:6s}: {count:3d} signals")
            report.append("")
        
        # Timing Analysis
        if summary.signals_by_hour:
            report.append("⏰ TIMING ANALYSIS:")
            report.append("-" * 80)
            peak_hours = sorted(summary.signals_by_hour.items(), key=lambda x: x[1], reverse=True)[:5]
            for hour, count in peak_hours:
                report.append(f"  {hour:02d}:00 - {hour+1:02d}:00: {count:3d} signals")
            report.append("")
        
        # Key Signals
        key_signals = SignalReportGenerator._get_key_signals(summary.signals)
        if key_signals:
            report.append("🎯 KEY SIGNALS (High Quality):")
            report.append("-" * 80)
            for i, signal in enumerate(key_signals[:10], 1):
                time_str = signal.timestamp.strftime('%H:%M:%S')
                conf_str = f"{signal.confluence_score:.0f}%" if signal.confluence_score else "N/A"
                dir_str = signal.direction or "N/A"
                report.append(f"  {i:2d}. {time_str} | {signal.alert_type:15s} | {signal.symbol:6s} | {conf_str:6s} | {dir_str:5s} | {signal.title[:50]}")
            
            if len(key_signals) > 10:
                report.append(f"  ... and {len(key_signals) - 10} more key signals")
            report.append("")
        
        # Tradeable Signals
        tradeable = SignalReportGenerator._get_tradeable_signals(summary.signals)
        if tradeable:
            report.append("💰 TRADEABLE SIGNALS (Complete Setup):")
            report.append("-" * 80)
            for i, signal in enumerate(tradeable[:10], 1):
                time_str = signal.timestamp.strftime('%H:%M:%S')
                rr_str = f"{signal.risk_reward:.1f}:1" if signal.risk_reward else "N/A"
                report.append(f"  {i:2d}. {time_str} | {signal.symbol:6s} | {signal.direction:5s} | "
                            f"Entry: ${signal.entry_price:.2f} | Stop: ${signal.stop_loss:.2f} | "
                            f"Target: ${signal.take_profit:.2f} | R/R: {rr_str}")
            
            if len(tradeable) > 10:
                report.append(f"  ... and {len(tradeable) - 10} more tradeable signals")
            report.append("")
        
        # Analysis
        report.append("💡 ANALYSIS:")
        report.append("-" * 80)
        
        if summary.total_signals == 0:
            report.append("  ⚠️  No signals generated today")
        else:
            # Signal quality
            if summary.avg_confluence >= 70:
                report.append(f"  ✅ High average confluence ({summary.avg_confluence:.1f}%) - Quality signals")
            elif summary.avg_confluence >= 50:
                report.append(f"  ⚠️  Moderate average confluence ({summary.avg_confluence:.1f}%) - Mixed quality")
            else:
                report.append(f"  ⚠️  Low average confluence ({summary.avg_confluence:.1f}%) - Review thresholds")
            
            # Signal distribution
            if summary.synthesis_signals > 0:
                report.append(f"  ✅ Synthesis active: {summary.synthesis_signals} unified signals")
            if summary.narrative_brain_signals > 0:
                report.append(f"  ✅ Narrative Brain active: {summary.narrative_brain_signals} high-quality signals")
            
            # Spam check
            if summary.dp_alerts > 50:
                report.append(f"  ⚠️  High DP alert count ({summary.dp_alerts}) - Check unified mode suppression")
            elif summary.dp_alerts > 0 and summary.synthesis_signals == 0:
                report.append(f"  ⚠️  DP alerts sent but no synthesis - Unified mode may not be working")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)
    
    @staticmethod
    def _get_key_signals(signals: List[SignalAlert]) -> List[SignalAlert]:
        """Get high-quality signals"""
        key = []
        for signal in signals:
            if signal.alert_type in ['synthesis', 'narrative_brain']:
                key.append(signal)
            elif signal.confluence_score and signal.confluence_score >= 70:
                key.append(signal)
        return sorted(key, key=lambda x: x.timestamp)
    
    @staticmethod
    def _get_tradeable_signals(signals: List[SignalAlert]) -> List[SignalAlert]:
        """Get signals with complete trade setup"""
        tradeable = []
        for signal in signals:
            if signal.entry_price and signal.stop_loss and signal.take_profit:
                tradeable.append(signal)
        return sorted(tradeable, key=lambda x: x.timestamp)


