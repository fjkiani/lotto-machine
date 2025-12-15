#!/usr/bin/env python3
"""
TRUMP CALENDAR - "What's UPCOMING?"

This module answers: What Trump-related events are coming up?
Returns: Scheduled events, deadlines, and potential catalysts.

Usage:
    from trump_calendar import TrumpCalendar
    calendar = TrumpCalendar()
    upcoming = calendar.get_upcoming_events()
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

# Add paths
base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, base_path)

logger = logging.getLogger(__name__)


@dataclass
class TrumpEvent:
    """A scheduled or anticipated Trump event."""
    date: datetime
    title: str
    event_type: str  # SPEECH, RALLY, INTERVIEW, DEADLINE, POLICY, LEGAL, MEETING
    description: str
    
    # Market impact assessment
    market_impact: str  # HIGH, MEDIUM, LOW
    likely_direction: str  # BULLISH, BEARISH, VOLATILE, UNKNOWN
    affected_sectors: List[str] = field(default_factory=list)
    affected_symbols: List[str] = field(default_factory=list)
    
    # Trading strategy
    pre_event_strategy: str = ""
    post_event_strategy: str = ""
    
    # Source and confidence
    source: str = "manual"
    confidence: float = 0.5


@dataclass
class TrumpCalendarReport:
    """Full calendar report."""
    as_of: datetime = field(default_factory=datetime.now)
    
    # Events by timeframe
    today: List[TrumpEvent] = field(default_factory=list)
    this_week: List[TrumpEvent] = field(default_factory=list)
    upcoming: List[TrumpEvent] = field(default_factory=list)
    
    # Key dates
    next_major_event: Optional[TrumpEvent] = None
    nearest_deadline: Optional[TrumpEvent] = None
    
    # Summary
    risk_level: str = "NORMAL"  # LOW, NORMAL, ELEVATED, HIGH
    volatility_outlook: str = "NORMAL"  # LOW, NORMAL, HIGH, EXTREME


class TrumpCalendar:
    """
    Trump event calendar and deadline tracker.
    Answers: "What's UPCOMING?"
    """
    
    def __init__(self):
        self.events = self._load_known_events()
        logger.info(f"📅 TrumpCalendar initialized with {len(self.events)} events")
    
    def _load_known_events(self) -> List[TrumpEvent]:
        """
        Load known Trump events.
        In production, this would pull from:
        - Official White House calendar
        - Campaign schedules
        - Court dates
        - Economic calendar
        """
        now = datetime.now()
        
        # Known/anticipated events (update these regularly)
        events = [
            # Policy deadlines
            TrumpEvent(
                date=datetime(2025, 1, 20, 12, 0),
                title="Inauguration Day",
                event_type="POLICY",
                description="Trump's second inauguration. Expect executive order announcements.",
                market_impact="HIGH",
                likely_direction="VOLATILE",
                affected_sectors=["all"],
                affected_symbols=["SPY", "QQQ", "DIA"],
                pre_event_strategy="Reduce exposure, hold cash, buy volatility",
                post_event_strategy="Watch for sector rotation based on policy announcements",
                source="official",
                confidence=1.0
            ),
            TrumpEvent(
                date=datetime(2025, 1, 20, 14, 0),
                title="Day 1 Executive Orders Expected",
                event_type="POLICY",
                description="Expected EOs on: immigration, energy, tariffs, deregulation",
                market_impact="HIGH",
                likely_direction="VOLATILE",
                affected_sectors=["energy", "defense", "manufacturing", "tech"],
                affected_symbols=["XLE", "XLI", "ITA", "SPY"],
                pre_event_strategy="Position in expected beneficiaries (energy, defense)",
                post_event_strategy="Trade the reaction based on specific EOs",
                source="anticipated",
                confidence=0.85
            ),
            
            # Tariff deadlines
            TrumpEvent(
                date=datetime(2025, 2, 1, 0, 0),
                title="Mexico/Canada Tariff Deadline",
                event_type="DEADLINE",
                description="25% tariff deadline on Mexico and Canada unless border security improves",
                market_impact="HIGH",
                likely_direction="BEARISH",
                affected_sectors=["auto", "manufacturing", "retail"],
                affected_symbols=["F", "GM", "EWW", "EWC", "SPY"],
                pre_event_strategy="PLAYBOOK: Calculated Bluff - expect delay. Position for relief rally.",
                post_event_strategy="If implemented: short affected sectors. If delayed: buy the dip.",
                source="trump_statement",
                confidence=0.75
            ),
            TrumpEvent(
                date=datetime(2025, 2, 15, 0, 0),
                title="China Trade Review",
                event_type="DEADLINE",
                description="Expected review of Phase 1 trade deal and potential new tariff announcements",
                market_impact="HIGH",
                likely_direction="VOLATILE",
                affected_sectors=["tech", "manufacturing", "retail"],
                affected_symbols=["FXI", "KWEB", "BABA", "SPY", "QQQ"],
                pre_event_strategy="Hedge China exposure, buy volatility",
                post_event_strategy="Trade the direction once announced",
                source="anticipated",
                confidence=0.6
            ),
            
            # BRICS
            TrumpEvent(
                date=datetime(2025, 1, 15, 0, 0),
                title="BRICS Currency Tariff Threat Deadline",
                event_type="DEADLINE",
                description="100% tariff threat if BRICS proceeds with new currency",
                market_impact="MEDIUM",
                likely_direction="BEARISH",
                affected_sectors=["emerging_markets", "commodities"],
                affected_symbols=["EEM", "FXI", "EWZ", "GLD", "UUP"],
                pre_event_strategy="PLAYBOOK: Calculated Bluff - likely posturing. Monitor for real action.",
                post_event_strategy="If implemented: major EM selloff. If nothing: relief rally.",
                source="trump_statement",
                confidence=0.5
            ),
            
            # Regular events
            TrumpEvent(
                date=now.replace(hour=9, minute=0, second=0) + timedelta(days=1),
                title="Potential Morning Tweet Storm",
                event_type="SPEECH",
                description="Trump often posts on Truth Social in early morning hours",
                market_impact="MEDIUM",
                likely_direction="UNKNOWN",
                affected_sectors=["varies"],
                affected_symbols=["SPY"],
                pre_event_strategy="Monitor Truth Social / news feeds",
                post_event_strategy="React based on content",
                source="pattern",
                confidence=0.4
            ),
            
            # Economic intersections
            TrumpEvent(
                date=datetime(2025, 1, 29, 14, 0),
                title="Fed Interest Rate Decision",
                event_type="POLICY",
                description="FOMC meeting - watch for Trump comments on Fed policy",
                market_impact="HIGH",
                likely_direction="VOLATILE",
                affected_sectors=["financials", "real_estate", "tech"],
                affected_symbols=["XLF", "QQQ", "TLT", "SPY"],
                pre_event_strategy="Expect Trump to comment regardless of decision",
                post_event_strategy="Double volatility if Trump criticizes Fed",
                source="economic_calendar",
                confidence=1.0
            ),
        ]
        
        return events
    
    def get_upcoming_events(self, days: int = 30) -> TrumpCalendarReport:
        """
        Get upcoming Trump events.
        
        Args:
            days: Look ahead period
        
        Returns:
            TrumpCalendarReport with events by timeframe
        """
        now = datetime.now()
        end_date = now + timedelta(days=days)
        
        report = TrumpCalendarReport()
        
        # Filter events by timeframe
        today_end = now.replace(hour=23, minute=59, second=59)
        week_end = now + timedelta(days=7)
        
        for event in self.events:
            if event.date < now:
                continue  # Skip past events
            if event.date > end_date:
                continue  # Skip too far in future
            
            if event.date <= today_end:
                report.today.append(event)
            elif event.date <= week_end:
                report.this_week.append(event)
            else:
                report.upcoming.append(event)
        
        # Sort by date
        report.today.sort(key=lambda x: x.date)
        report.this_week.sort(key=lambda x: x.date)
        report.upcoming.sort(key=lambda x: x.date)
        
        # Find key events
        all_events = report.today + report.this_week + report.upcoming
        
        high_impact = [e for e in all_events if e.market_impact == "HIGH"]
        if high_impact:
            report.next_major_event = high_impact[0]
        
        deadlines = [e for e in all_events if e.event_type == "DEADLINE"]
        if deadlines:
            report.nearest_deadline = deadlines[0]
        
        # Assess risk level
        high_impact_this_week = len([e for e in report.today + report.this_week if e.market_impact == "HIGH"])
        
        if high_impact_this_week >= 3:
            report.risk_level = "HIGH"
            report.volatility_outlook = "EXTREME"
        elif high_impact_this_week >= 2:
            report.risk_level = "ELEVATED"
            report.volatility_outlook = "HIGH"
        elif high_impact_this_week >= 1:
            report.risk_level = "NORMAL"
            report.volatility_outlook = "HIGH"
        else:
            report.risk_level = "LOW"
            report.volatility_outlook = "NORMAL"
        
        return report
    
    def print_calendar(self, report: Optional[TrumpCalendarReport] = None):
        """Print formatted calendar report."""
        if report is None:
            report = self.get_upcoming_events()
        
        print("\n" + "=" * 70)
        print("╔══════════════════════════════════════════════════════════════════════╗")
        print("║              📅 TRUMP CALENDAR - UPCOMING EVENTS                      ║")
        print("╚══════════════════════════════════════════════════════════════════════╝")
        print(f"  As of: {report.as_of.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        # Risk level
        risk_emoji = {"LOW": "🟢", "NORMAL": "🟡", "ELEVATED": "🟠", "HIGH": "🔴"}.get(report.risk_level, "❓")
        print(f"\n{risk_emoji} RISK LEVEL: {report.risk_level} | VOLATILITY: {report.volatility_outlook}")
        
        # Today
        print(f"\n📌 TODAY ({len(report.today)} events):")
        if report.today:
            for event in report.today:
                self._print_event(event, indent=3)
        else:
            print("   No events scheduled")
        
        # This week
        print(f"\n📆 THIS WEEK ({len(report.this_week)} events):")
        if report.this_week:
            for event in report.this_week[:5]:
                self._print_event(event, indent=3)
        else:
            print("   No events scheduled")
        
        # Upcoming
        print(f"\n🔮 UPCOMING ({len(report.upcoming)} events):")
        if report.upcoming:
            for event in report.upcoming[:5]:
                self._print_event(event, indent=3)
        else:
            print("   No events scheduled")
        
        # Key events
        if report.next_major_event:
            print(f"\n⚠️  NEXT MAJOR EVENT:")
            self._print_event(report.next_major_event, indent=3, detailed=True)
        
        if report.nearest_deadline:
            print(f"\n⏰ NEAREST DEADLINE:")
            self._print_event(report.nearest_deadline, indent=3, detailed=True)
        
        print("\n" + "=" * 70)
    
    def _print_event(self, event: TrumpEvent, indent: int = 0, detailed: bool = False):
        """Print a single event."""
        pad = " " * indent
        
        impact_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(event.market_impact, "⚪")
        direction_emoji = {"BULLISH": "📈", "BEARISH": "📉", "VOLATILE": "📊", "UNKNOWN": "❓"}.get(event.likely_direction, "❓")
        
        print(f"{pad}{impact_emoji} {event.date.strftime('%m/%d %H:%M')} - {event.title}")
        print(f"{pad}   Type: {event.event_type} | Direction: {direction_emoji} {event.likely_direction}")
        
        if detailed:
            print(f"{pad}   {event.description}")
            if event.affected_symbols:
                print(f"{pad}   Symbols: {', '.join(event.affected_symbols[:5])}")
            if event.pre_event_strategy:
                print(f"{pad}   PRE:  {event.pre_event_strategy}")
            if event.post_event_strategy:
                print(f"{pad}   POST: {event.post_event_strategy}")


def main():
    """Demo the Trump Calendar."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    calendar = TrumpCalendar()
    report = calendar.get_upcoming_events()
    calendar.print_calendar(report)


if __name__ == "__main__":
    main()





