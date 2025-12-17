"""
📱 REDDIT SIGNAL REPORT GENERATOR
Generates production-ready Reddit signal analysis reports

Author: Alpha's AI Hedge Fund
Date: 2025-12-17
"""

from typing import List
from ..analysis.reddit_signal_analyzer import RedditSignal, RedditSignalSummary


class RedditSignalReportGenerator:
    """Generates formatted Reddit signal reports"""
    
    @staticmethod
    def generate_report(summary: RedditSignalSummary) -> str:
        """
        Generate a comprehensive Reddit signal analysis report.
        
        Args:
            summary: RedditSignalSummary object
            
        Returns:
            Formatted report string
        """
        report = []
        report.append("=" * 80)
        report.append(f"📱 REDDIT SIGNAL ANALYSIS: {summary.date}")
        report.append("=" * 80)
        report.append("")
        
        # Overview
        report.append("📊 OVERVIEW:")
        report.append("-" * 80)
        report.append(f"  Total Signals: {summary.total_signals}")
        report.append(f"  Unique Symbols: {len(summary.symbols)}")
        report.append(f"  Avg Strength: {summary.avg_strength:.1f}%")
        report.append("")
        
        # Action Breakdown
        report.append("🎯 ACTION BREAKDOWN:")
        report.append("-" * 80)
        report.append(f"  🟢 LONG (Take Position):        {summary.long_signals:3d}")
        report.append(f"  🟡 WATCH (Monitor for Entry):   {summary.watch_signals:3d}")
        report.append(f"  🔴 AVOID (Pump/Dump Risk):      {summary.avoid_signals:3d}")
        report.append("")
        
        # Signal Types
        if summary.signal_types:
            report.append("📋 SIGNAL TYPES:")
            report.append("-" * 80)
            for sig_type, count in sorted(summary.signal_types.items(), key=lambda x: x[1], reverse=True):
                report.append(f"  {sig_type:25s}: {count:3d}")
            report.append("")
        
        # Top Symbols
        if summary.symbols:
            report.append("📈 TOP SYMBOLS:")
            report.append("-" * 80)
            top_symbols = sorted(summary.symbols.items(), key=lambda x: x[1], reverse=True)[:10]
            for symbol, count in top_symbols:
                report.append(f"  {symbol:6s}: {count:3d} signals")
            report.append("")
        
        # High-Quality Signals (LONG)
        long_signals = [s for s in summary.signals if s.action == 'LONG']
        if long_signals:
            report.append("🟢 LONG SIGNALS (High Conviction):")
            report.append("-" * 80)
            for i, signal in enumerate(sorted(long_signals, key=lambda x: x.strength, reverse=True)[:10], 1):
                time_str = signal.timestamp.strftime('%H:%M')
                report.append(f"  {i:2d}. {time_str} | {signal.symbol:6s} | ${signal.entry_price:7.2f} | "
                            f"{signal.signal_type:20s} | Strength: {signal.strength:.0f}%")
                
                # Show performance if validated
                if signal.validated and signal.return_1d is not None:
                    ret_str = f"{signal.return_1d:+.2f}%"
                    outcome_str = "✅ WIN" if signal.return_1d > 0 else "❌ LOSS"
                    report.append(f"       Performance (1d): {ret_str} {outcome_str}")
            
            if len(long_signals) > 10:
                report.append(f"  ... and {len(long_signals) - 10} more LONG signals")
            report.append("")
        
        # Watch Signals
        watch_signals = [s for s in summary.signals if 'WATCH' in s.action]
        if watch_signals:
            report.append("🟡 WATCH SIGNALS (Monitor for Entry):")
            report.append("-" * 80)
            for i, signal in enumerate(sorted(watch_signals, key=lambda x: x.strength, reverse=True)[:10], 1):
                time_str = signal.timestamp.strftime('%H:%M')
                report.append(f"  {i:2d}. {time_str} | {signal.symbol:6s} | ${signal.entry_price:7.2f} | "
                            f"{signal.signal_type:20s} | Strength: {signal.strength:.0f}%")
            
            if len(watch_signals) > 10:
                report.append(f"  ... and {len(watch_signals) - 10} more WATCH signals")
            report.append("")
        
        # Avoid Signals
        avoid_signals = [s for s in summary.signals if s.action == 'AVOID']
        if avoid_signals:
            report.append("🔴 AVOID SIGNALS (Pump/Dump Risk):")
            report.append("-" * 80)
            for i, signal in enumerate(sorted(avoid_signals, key=lambda x: x.strength, reverse=True)[:10], 1):
                time_str = signal.timestamp.strftime('%H:%M')
                report.append(f"  {i:2d}. {time_str} | {signal.symbol:6s} | ${signal.entry_price:7.2f} | "
                            f"{signal.signal_type:20s} | Strength: {signal.strength:.0f}%")
            
            if len(avoid_signals) > 10:
                report.append(f"  ... and {len(avoid_signals) - 10} more AVOID signals")
            report.append("")
        
        # Performance (if validated)
        if summary.validated_signals > 0:
            report.append("📊 PERFORMANCE (Validated Signals):")
            report.append("-" * 80)
            report.append(f"  Validated Signals: {summary.validated_signals}/{summary.total_signals}")
            
            if summary.win_rate_1d is not None:
                report.append(f"  1-Day Win Rate: {summary.win_rate_1d:.1f}%")
            if summary.avg_return_1d is not None:
                report.append(f"  1-Day Avg Return: {summary.avg_return_1d:+.2f}%")
            
            if summary.win_rate_3d is not None:
                report.append(f"  3-Day Win Rate: {summary.win_rate_3d:.1f}%")
            if summary.avg_return_3d is not None:
                report.append(f"  3-Day Avg Return: {summary.avg_return_3d:+.2f}%")
            report.append("")
        
        # Analysis & Recommendations
        report.append("💡 ANALYSIS:")
        report.append("-" * 80)
        
        if summary.total_signals == 0:
            report.append("  ⚠️  No Reddit signals today - Quiet social sentiment")
        else:
            # Signal quality
            if summary.long_signals > 0:
                report.append(f"  ✅ {summary.long_signals} high-conviction LONG signal(s) - Consider entries")
            else:
                report.append("  ⚠️  No high-conviction LONG signals - Wait for better setups")
            
            # Watch signals
            if summary.watch_signals > 0:
                report.append(f"  🟡 {summary.watch_signals} WATCH signal(s) - Monitor for entry opportunities")
            
            # Avoid signals
            if summary.avoid_signals > summary.long_signals:
                report.append(f"  🔴 High AVOID count ({summary.avoid_signals}) - Pump/dump risk elevated")
            
            # Performance validation
            if summary.validated_signals > 0:
                if summary.win_rate_1d and summary.win_rate_1d > 55:
                    report.append(f"  ✅ Good 1d win rate ({summary.win_rate_1d:.1f}%) - Strategy working")
                elif summary.win_rate_1d and summary.win_rate_1d < 45:
                    report.append(f"  ⚠️  Low 1d win rate ({summary.win_rate_1d:.1f}%) - Review signal criteria")
            else:
                report.append("  ⏳ No performance data yet - Signals too recent to validate")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)

