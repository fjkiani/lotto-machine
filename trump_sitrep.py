#!/usr/bin/env python3
"""
🎯 TRUMP SITREP - SITUATION REPORT

ONE COMMAND to answer:
- What's happening NOW?
- What's UPCOMING?
- What does it MEAN?
- HOW do we EXPLOIT it?

Usage:
    python3 trump_sitrep.py              # Full situation report
    python3 trump_sitrep.py --pulse      # Just current activity
    python3 trump_sitrep.py --calendar   # Just upcoming events
    python3 trump_sitrep.py --exploit    # Just trading signals
    python3 trump_sitrep.py --brief      # Executive summary only
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Add paths
base_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_path)
sys.path.insert(0, os.path.join(base_path, 'live_monitoring', 'agents'))

from live_monitoring.agents.trump_pulse import TrumpPulse
from live_monitoring.agents.trump_calendar import TrumpCalendar
from live_monitoring.agents.trump_exploiter import TrumpExploiter
from live_monitoring.agents.trump_news_monitor import TrumpNewsMonitor
from live_monitoring.agents.fed_watch_monitor import FedWatchMonitor
from live_monitoring.agents.fed_officials_monitor import FedOfficialsMonitor

logging.basicConfig(level=logging.WARNING)  # Suppress info logs for clean output


def print_header():
    """Print report header."""
    print("\n")
    print("╔═══════════════════════════════════════════════════════════════════════════╗")
    print("║                                                                           ║")
    print("║          🎯 TRUMP INTELLIGENCE SITUATION REPORT (SITREP)                  ║")
    print("║                                                                           ║")
    print("╚═══════════════════════════════════════════════════════════════════════════╝")
    print(f"\n  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("  Classification: ALPHA EYES ONLY 🔥")
    print("\n" + "═" * 75)


def print_executive_summary(pulse, calendar, exploit):
    """Print executive summary."""
    situation = pulse.get_current_situation()
    cal_report = calendar.get_upcoming_events()
    exp_report = exploit.get_exploit_signals()
    
    print("\n")
    print("╔═══════════════════════════════════════════════════════════════════════════╗")
    print("║  📋 EXECUTIVE SUMMARY                                                     ║")
    print("╚═══════════════════════════════════════════════════════════════════════════╝")
    
    # Current situation
    sentiment_emoji = "📈" if situation.overall_sentiment == "BULLISH" else "📉" if situation.overall_sentiment == "BEARISH" else "➡️"
    print(f"\n  {sentiment_emoji} CURRENT TRUMP SENTIMENT: {situation.overall_sentiment} ({situation.sentiment_score:+.2f})")
    print(f"     Activity: {situation.total_statements_24h} statements in 24h")
    if situation.hot_topics:
        print(f"     Hot Topics: {', '.join(situation.hot_topics[:3])}")
    
    # Calendar risk
    risk_emoji = {"LOW": "🟢", "NORMAL": "🟡", "ELEVATED": "🟠", "HIGH": "🔴"}.get(cal_report.risk_level, "❓")
    print(f"\n  {risk_emoji} CALENDAR RISK: {cal_report.risk_level} | VOLATILITY: {cal_report.volatility_outlook}")
    if cal_report.next_major_event:
        print(f"     Next Major: {cal_report.next_major_event.title} ({cal_report.next_major_event.date.strftime('%m/%d')})")
    
    # Trading stance
    stance_emoji = {"AGGRESSIVE": "🚀", "NEUTRAL": "✋", "CAUTIOUS": "⚠️", "DEFENSIVE": "🛡️"}.get(exp_report.overall_stance, "❓")
    print(f"\n  {stance_emoji} RECOMMENDED STANCE: {exp_report.overall_stance}")
    print(f"     Cash Level: {exp_report.recommended_cash_pct:.0f}%")
    
    # Top trade
    if exp_report.top_trade:
        action_emoji = {"BUY": "🟢", "SELL": "🔴", "SHORT": "🔴", "FADE": "🔄", "WATCH": "👀"}.get(exp_report.top_trade.action, "❓")
        print(f"\n  {action_emoji} TOP TRADE: {exp_report.top_trade.action} {exp_report.top_trade.symbol}")
        print(f"     Confidence: {exp_report.top_trade.confidence:.0f}%")
        print(f"     Reason: {exp_report.top_trade.reason[:70]}...")
    
    print("\n" + "═" * 75)


def run_full_sitrep():
    """Run full situation report."""
    print_header()
    
    # Initialize modules
    pulse = TrumpPulse()
    calendar = TrumpCalendar()
    exploiter = TrumpExploiter()
    news_monitor = TrumpNewsMonitor()
    fed_monitor = FedWatchMonitor()
    
    # Executive summary
    print_executive_summary(pulse, calendar, exploiter)
    
    # Detailed sections
    print("\n")
    print("═" * 75)
    print("  SECTION 1: CURRENT ACTIVITY (What's happening NOW?)")
    print("═" * 75)
    pulse.print_situation()
    
    print("\n")
    print("═" * 75)
    print("  SECTION 2: EXPLOITABLE NEWS (What can we profit from?)")
    print("═" * 75)
    news_monitor.print_exploit_report()
    
    print("\n")
    print("═" * 75)
    print("  SECTION 3: UPCOMING EVENTS (What's coming?)")
    print("═" * 75)
    calendar.print_calendar()
    
    print("\n")
    print("═" * 75)
    print("  SECTION 4: FED WATCH (Rate Cut/Hike Probabilities)")
    print("═" * 75)
    fed_monitor.print_fed_dashboard()
    
    print("\n")
    print("═" * 75)
    print("  SECTION 5: TRADING SIGNALS (How do we exploit?)")
    print("═" * 75)
    exploiter.print_exploit_report()
    
    # Footer
    print("\n")
    print("╔═══════════════════════════════════════════════════════════════════════════╗")
    print("║  ⚠️  DISCLAIMER                                                           ║")
    print("╠═══════════════════════════════════════════════════════════════════════════╣")
    print("║  This is intelligence for educational purposes. Trade at your own risk.  ║")
    print("║  Size positions appropriately. Trump can surprise everyone.              ║")
    print("║                                                                           ║")
    print("║  \"Trade the pattern, not the panic. He wrote the playbook.\" 🎯           ║")
    print("╚═══════════════════════════════════════════════════════════════════════════╝")
    print("\n")


def run_brief_sitrep():
    """Run brief executive summary only."""
    print_header()
    
    pulse = TrumpPulse()
    calendar = TrumpCalendar()
    exploiter = TrumpExploiter()
    
    print_executive_summary(pulse, calendar, exploiter)
    print("\n")


def run_pulse_only():
    """Run pulse section only."""
    print_header()
    pulse = TrumpPulse()
    pulse.print_situation()
    print("\n")


def run_calendar_only():
    """Run calendar section only."""
    print_header()
    calendar = TrumpCalendar()
    calendar.print_calendar()
    print("\n")


def run_exploit_only():
    """Run exploit section only."""
    print_header()
    exploiter = TrumpExploiter()
    exploiter.print_exploit_report()
    print("\n")


def run_news_only():
    """Run news monitor section only."""
    print_header()
    news_monitor = TrumpNewsMonitor()
    news_monitor.print_exploit_report()
    print("\n")


def run_fed_only():
    """Run Fed Watch section only."""
    print_header()
    fed_monitor = FedWatchMonitor()
    fed_monitor.print_fed_dashboard()
    print("\n")


def run_fed_full():
    """Run full Fed intelligence (watch + officials)."""
    print_header()
    
    print("\n═══════════════════════════════════════════════════════════════════════════")
    print("  🏦 FED RATE PROBABILITIES (CME FedWatch)")
    print("═══════════════════════════════════════════════════════════════════════════")
    fed_watch = FedWatchMonitor()
    fed_watch.print_fed_dashboard()
    
    print("\n═══════════════════════════════════════════════════════════════════════════")
    print("  🎤 FED OFFICIALS COMMENTS (Who Said What?)")
    print("═══════════════════════════════════════════════════════════════════════════")
    fed_officials = FedOfficialsMonitor()
    report = fed_officials.get_report()
    fed_officials.print_fed_officials_report(report)
    
    print("\n")


def main():
    parser = argparse.ArgumentParser(description="Trump Intelligence Situation Report")
    parser.add_argument("--pulse", action="store_true", help="Current activity only")
    parser.add_argument("--calendar", action="store_true", help="Upcoming events only")
    parser.add_argument("--exploit", action="store_true", help="Trading signals only")
    parser.add_argument("--news", action="store_true", help="Exploitable news search only")
    parser.add_argument("--fed", action="store_true", help="Fed Watch rate probabilities only")
    parser.add_argument("--fed-full", action="store_true", help="Full Fed intelligence (watch + officials)")
    parser.add_argument("--brief", action="store_true", help="Executive summary only")
    
    args = parser.parse_args()
    
    if args.pulse:
        run_pulse_only()
    elif args.calendar:
        run_calendar_only()
    elif args.exploit:
        run_exploit_only()
    elif args.news:
        run_news_only()
    elif args.fed:
        run_fed_only()
    elif getattr(args, 'fed_full', False):
        run_fed_full()
    elif args.brief:
        run_brief_sitrep()
    else:
        run_full_sitrep()


if __name__ == "__main__":
    main()

