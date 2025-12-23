#!/usr/bin/env python3
"""
🩺 ALPHA INTELLIGENCE HEALTH CHECK CLI

Quick diagnostic tool to check system health and checker status.
"""

import os
import sys
import argparse
from datetime import datetime

# Add paths
base_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_path)

from live_monitoring.orchestrator.checker_health import CheckerHealthRegistry, CheckerStatus

def format_table_row(name, status, alerts, last_run, win_rate):
    """Format a single table row."""
    status_emoji = {
        CheckerStatus.HEALTHY: "✅",
        CheckerStatus.WARNING: "⚠️",
        CheckerStatus.ERROR: "❌",
        CheckerStatus.DISABLED: "⏸️",
        CheckerStatus.NOT_APPLICABLE: "⏸️"
    }.get(status, "❓")
    
    wr_str = f"{win_rate:.1f}%" if win_rate else "N/A"
    
    return f"│ {name:<20} │ {status_emoji:<6} │ {alerts:<8} │ {last_run:<12} │ {wr_str:<15} │"

def print_health_check(checker_name=None, detailed=False, update_winrates=False):
    """Print health check report."""
    registry = CheckerHealthRegistry()
    health = registry.get_health_summary()
    
    # Update win rates if requested
    if update_winrates:
        print("🔄 Updating win rates from backtest results...")
        try:
            from backtesting.simulation.unified_backtest_runner import UnifiedBacktestRunner
            from datetime import datetime, timedelta
            
            # Run backtest for last 7 days
            today = datetime.now()
            results = {}
            
            for i in range(7):
                date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
                try:
                    runner = UnifiedBacktestRunner()
                    result = runner.run_all(date)
                    # Aggregate results
                    for detector_name, detector_result in result.items():
                        if detector_name not in results:
                            results[detector_name] = {'wins': 0, 'losses': 0, 'total': 0}
                        
                        for trade in detector_result.trades:
                            results[detector_name]['total'] += 1
                            if trade.outcome == 'WIN':
                                results[detector_name]['wins'] += 1
                            elif trade.outcome == 'LOSS':
                                results[detector_name]['losses'] += 1
                except Exception as e:
                    print(f"   ⚠️  Could not backtest {date}: {e}")
                    continue
            
            # Update registry with win rates
            for detector_name, stats in results.items():
                if stats['total'] > 0:
                    win_rate = stats['wins'] / stats['total'] * 100
                    # Map detector names to checker names
                    checker_map = {
                        'selloff_rally': 'selloff_rally',
                        'gap': 'premarket_gap',
                        'options_flow': 'options_flow',
                    }
                    checker_name = checker_map.get(detector_name)
                    if checker_name:
                        registry.update_win_rate(checker_name, win_rate, stats['total'])
            
            print("✅ Win rates updated!")
        except Exception as e:
            print(f"❌ Failed to update win rates: {e}")
            import traceback
            traceback.print_exc()
    
    # Filter by checker if specified
    if checker_name:
        if checker_name not in health:
            print(f"❌ Checker '{checker_name}' not found!")
            print(f"Available checkers: {', '.join(health.keys())}")
            return
        health = {checker_name: health[checker_name]}
    
    # Print header
    print("=" * 80)
    print("🩺 ALPHA INTELLIGENCE HEALTH CHECK")
    print("=" * 80)
    print()
    
    # Print table
    print("CHECKER STATUS (Last 24 Hours)")
    print("┌" + "─" * 20 + "┬" + "─" * 6 + "┬" + "─" * 8 + "┬" + "─" * 12 + "┬" + "─" * 15 + "┐")
    print("│ Checker           │ Status │ Alerts  │ Last Run    │ Win Rate        │")
    print("├" + "─" * 20 + "┼" + "─" * 6 + "┼" + "─" * 8 + "┼" + "─" * 12 + "┼" + "─" * 15 + "┤")
    
    warnings = []
    errors = []
    
    for name, h in sorted(health.items()):
        time_ago = registry.format_time_ago(h.last_run)
        win_rate_str = f"{h.win_rate_7d:.1f}%" if h.win_rate_7d else "N/A"
        if h.win_rate_7d and h.total_trades_7d:
            win_rate_str += f" ({h.total_trades_7d})"
        
        print(format_table_row(
            h.display_name[:20],
            h.status,
            str(h.alerts_24h),
            time_ago[:12],
            win_rate_str[:15]
        ))
        
        if h.status == CheckerStatus.WARNING:
            warnings.append(f"• {h.display_name}: Hasn't run in {time_ago}")
        elif h.status == CheckerStatus.ERROR:
            errors.append(f"• {h.display_name}: ERROR - {h.last_error}")
    
    print("└" + "─" * 20 + "┴" + "─" * 6 + "┴" + "─" * 8 + "┴" + "─" * 12 + "┴" + "─" * 15 + "┘")
    print()
    
    # Print warnings/errors
    if warnings or errors:
        if errors:
            print("❌ ERRORS:")
            for error in errors:
                print(f"   {error}")
            print()
        
        if warnings:
            print("⚠️  WARNINGS:")
            for warning in warnings:
                print(f"   {warning}")
            print()
    
    # Overall status
    has_errors = any(h.status == CheckerStatus.ERROR for h in health.values())
    has_warnings = any(h.status == CheckerStatus.WARNING for h in health.values())
    
    if has_errors:
        status = "❌ UNHEALTHY"
    elif has_warnings:
        status = "⚠️  WARNING"
    else:
        status = "✅ HEALTHY"
    
    print(f"OVERALL SYSTEM STATUS: {status}")
    print()
    
    # Aggregate metrics
    total_signals = sum(h.alerts_24h for h in health.values())
    total_trades = sum(h.total_trades_7d for h in health.values() if h.total_trades_7d)
    
    if total_trades > 0:
        total_wins = sum(
            int(h.win_rate_7d * h.total_trades_7d / 100) 
            for h in health.values() 
            if h.win_rate_7d and h.total_trades_7d
        )
        overall_wr = total_wins / total_trades * 100 if total_trades > 0 else 0
        
        print("📊 AGGREGATE METRICS (Last 7 Days):")
        print(f"• Total Signals: {total_signals}")
        print(f"• Total Trades: {total_trades}")
        print(f"• Overall Win Rate: {overall_wr:.1f}%")
        print()
    
    # DP Learning stats
    dp_stats = registry.get_dp_learning_stats()
    if dp_stats and dp_stats.get('total_interactions', 0) > 0:
        print("🔒 DARK POOL LEARNING STATS:")
        print(f"• Bounce Rate: {dp_stats['bounce_rate']:.1f}%")
        print(f"• Total Interactions: {dp_stats['total_interactions']}")
        print(f"• Bounces: {dp_stats['bounces']}")
        print(f"• Breaks: {dp_stats['breaks']}")
        print()
    
    # Detailed view
    if detailed and checker_name:
        h = health[checker_name]
        print(f"📋 DETAILED INFO: {h.display_name}")
        print(f"• Name: {h.name}")
        print(f"• Status: {h.status.value}")
        print(f"• Last Run: {registry.format_time_ago(h.last_run)}")
        print(f"• Last Success: {registry.format_time_ago(h.last_success)}")
        print(f"• Alerts Today: {h.alerts_today}")
        print(f"• Alerts 24h: {h.alerts_24h}")
        print(f"• Expected Interval: {h.expected_interval}s")
        print(f"• Run Conditions: {h.run_conditions}")
        if h.last_error:
            print(f"• Last Error: {h.last_error}")
        print()

def main():
    parser = argparse.ArgumentParser(description='Check Alpha Intelligence system health')
    parser.add_argument('--checker', type=str, help='Check specific checker')
    parser.add_argument('--detailed', action='store_true', help='Show detailed information')
    parser.add_argument('--update-winrates', action='store_true', help='Update win rates from backtest')
    
    args = parser.parse_args()
    
    print_health_check(
        checker_name=args.checker,
        detailed=args.detailed,
        update_winrates=args.update_winrates
    )

if __name__ == '__main__':
    main()

