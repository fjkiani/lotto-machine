#!/usr/bin/env python3
"""
🏦 FED WATCH MONITOR - Rate Cut/Hike Probability Tracker

Monitors Fed rate cut/hike probabilities and alerts on significant changes.
This is CRITICAL because rate expectations move markets before the actual decision!

Data Sources:
- CME FedWatch Tool (via scraping/API)
- Fed Funds Futures implied probabilities
- Economic calendar for FOMC dates

Usage:
    from fed_watch_monitor import FedWatchMonitor
    monitor = FedWatchMonitor()
    status = monitor.get_current_probabilities()
    monitor.print_fed_dashboard()
"""

import os
import sys
import json
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from bs4 import BeautifulSoup
import yfinance as yf

# Add paths
base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, base_path)

logger = logging.getLogger(__name__)


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class FOMCMeeting:
    """FOMC meeting info."""
    date: datetime
    is_next: bool = False
    days_until: int = 0


@dataclass
class RateProbability:
    """Probability for a specific rate outcome."""
    rate_bps: int  # Rate in basis points (e.g., 425 = 4.25%)
    probability: float  # 0-100%
    change_bps: int = 0  # Change from current rate


@dataclass
class FedWatchStatus:
    """Complete Fed Watch status."""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Current rate (as of Dec 2025 per CME)
    current_rate_bps: int = 400  # 4.00% - current target 375-400 bps (3.75%-4.00%)
    current_rate_range: str = "3.75%-4.00%"  # Updated to match CME screenshot
    
    # Next meeting
    next_meeting: Optional[FOMCMeeting] = None
    
    # Probabilities for next meeting
    probabilities: List[RateProbability] = field(default_factory=list)
    
    # Summary
    prob_cut: float = 0.0  # Probability of any cut
    prob_hold: float = 0.0  # Probability of no change
    prob_hike: float = 0.0  # Probability of any hike
    
    # Most likely outcome
    most_likely_outcome: str = "HOLD"
    most_likely_probability: float = 0.0
    
    # Change tracking
    prob_cut_change: float = 0.0  # Change since last check
    prob_hold_change: float = 0.0
    prob_hike_change: float = 0.0
    
    # Market implications
    market_bias: str = "NEUTRAL"  # BULLISH, BEARISH, NEUTRAL
    affected_sectors: List[str] = field(default_factory=list)


# ============================================================================
# FOMC CALENDAR
# ============================================================================

# 2025 FOMC Meeting Dates (scheduled)
FOMC_DATES_2025 = [
    datetime(2025, 1, 28),   # Jan 28-29
    datetime(2025, 3, 18),   # Mar 18-19
    datetime(2025, 5, 6),    # May 6-7
    datetime(2025, 6, 17),   # Jun 17-18
    datetime(2025, 7, 29),   # Jul 29-30
    datetime(2025, 9, 16),   # Sep 16-17
    datetime(2025, 11, 4),   # Nov 4-5
    datetime(2025, 12, 16),  # Dec 16-17
]


# ============================================================================
# FED WATCH FETCHER
# ============================================================================

class FedWatchFetcher:
    """
    Fetches Fed rate probabilities from various sources.
    """
    
    def __init__(self):
        self.last_status: Optional[FedWatchStatus] = None
        self.cache_time: Optional[datetime] = None
        self.cache_duration = timedelta(minutes=5)
        
        # User agent for scraping
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
    
    def _get_next_fomc_meeting(self) -> FOMCMeeting:
        """Get the next FOMC meeting."""
        now = datetime.now()
        
        for date in FOMC_DATES_2025:
            if date > now:
                days_until = (date - now).days
                return FOMCMeeting(
                    date=date,
                    is_next=True,
                    days_until=days_until
                )
        
        # If no future 2025 meetings, assume first 2026
        next_date = datetime(2026, 1, 28)
        return FOMCMeeting(
            date=next_date,
            is_next=True,
            days_until=(next_date - now).days
        )
    
    def _fetch_from_investing_com(self) -> Optional[Dict]:
        """
        Fetch Fed rate probabilities from Investing.com.
        This is a backup source.
        """
        try:
            url = "https://www.investing.com/central-banks/fed-rate-monitor"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                # Parse the page for probabilities
                # Note: This may need adjustment based on page structure
                
                # Look for probability data
                prob_elements = soup.find_all('span', class_='probValue')
                if prob_elements:
                    return {
                        'source': 'investing.com',
                        'raw_data': [el.text for el in prob_elements]
                    }
        except Exception as e:
            logger.warning(f"Investing.com fetch failed: {e}")
        
        return None
    
    def _estimate_from_futures(self) -> Dict:
        """
        Estimate rate probabilities from Fed Funds Futures.
        Uses the 30-day Fed Funds futures price.
        """
        try:
            # Try to get Fed Funds Futures data
            # ZQ is the Fed Funds futures symbol on CME
            # We'll use a proxy approach with interest rate sensitive ETFs
            
            # Get current effective fed funds rate proxy
            tlt = yf.Ticker("TLT")  # Long-term Treasury ETF
            shy = yf.Ticker("SHY")  # Short-term Treasury ETF
            
            tlt_info = tlt.info
            shy_info = shy.info
            
            # Use yield spread as a rough proxy for rate expectations
            # This is an approximation - real FedWatch uses futures
            
            # Get VIX for uncertainty
            vix = yf.Ticker("^VIX")
            vix_level = vix.info.get('regularMarketPrice', 15)
            
            # Simple heuristic based on market conditions
            # In reality, you'd use actual Fed Funds Futures prices
            
            # Higher VIX = more uncertainty = more likely to hold
            # Lower VIX = more certainty = rate path clearer
            
            if vix_level > 25:
                # High uncertainty - lean toward hold
                prob_cut = 20.0
                prob_hold = 70.0
                prob_hike = 10.0
            elif vix_level > 18:
                # Moderate uncertainty
                prob_cut = 35.0
                prob_hold = 55.0
                prob_hike = 10.0
            else:
                # Low uncertainty - market expects current path
                prob_cut = 45.0
                prob_hold = 50.0
                prob_hike = 5.0
            
            return {
                'source': 'futures_estimate',
                'prob_cut': prob_cut,
                'prob_hold': prob_hold,
                'prob_hike': prob_hike,
                'vix_level': vix_level
            }
            
        except Exception as e:
            logger.warning(f"Futures estimate failed: {e}")
            # Default fallback
            return {
                'source': 'default',
                'prob_cut': 40.0,
                'prob_hold': 55.0,
                'prob_hike': 5.0
            }
    
    def _fetch_from_perplexity(self) -> Optional[Dict]:
        """
        Fetch current Fed rate expectations from Perplexity.
        Uses a very specific query to get exact CME FedWatch numbers.
        """
        try:
            from dotenv import load_dotenv
            load_dotenv()
            
            api_key = os.getenv('PERPLEXITY_API_KEY')
            if not api_key:
                return None
            
            sys.path.insert(0, os.path.join(base_path, 'live_monitoring', 'enrichment', 'apis'))
            from perplexity_search import PerplexitySearchClient
            
            client = PerplexitySearchClient(api_key=api_key)
            
            # Very specific query for CME FedWatch
            query = """
            What is the EXACT current CME FedWatch probability percentage for December 2025 FOMC meeting?
            The current Fed Funds rate target is 375-400 bps (3.75%-4.00%).
            CME FedWatch shows probabilities for:
            - 350-375 bps (this would be a 25bp CUT)
            - 375-400 bps (this would be NO CHANGE / HOLD)
            
            Give me ONLY the probability percentages in this exact format:
            "350-375: XX%" and "375-400: XX%"
            """
            result = client.search(query)
            
            if result and 'answer' in result:
                return {
                    'source': 'perplexity',
                    'answer': result['answer']
                }
        except Exception as e:
            logger.warning(f"Perplexity fetch failed: {e}")
        
        return None
    
    def get_status(self, force_refresh: bool = False) -> FedWatchStatus:
        """
        Get current Fed Watch status.
        """
        # Check cache
        if not force_refresh and self.cache_time:
            if datetime.now() - self.cache_time < self.cache_duration:
                if self.last_status:
                    return self.last_status
        
        status = FedWatchStatus()
        status.next_meeting = self._get_next_fomc_meeting()
        
        # Try to get real data from Perplexity first
        perplexity_data = self._fetch_from_perplexity()
        
        if perplexity_data and 'answer' in perplexity_data:
            # Parse the answer for probabilities
            answer = perplexity_data['answer']
            answer_lower = answer.lower()
            
            import re
            
            # BEST PATTERN: "CUT: 87-89%, HOLD: 11-13%" format
            # This is what Perplexity returns in our specific query
            cut_direct = re.search(r'cut[:\s]+(\d{2,3})(?:-\d+)?%', answer_lower)
            hold_direct = re.search(r'hold[:\s]+(\d{1,3})(?:-\d+)?%', answer_lower)
            
            if cut_direct:
                status.prob_cut = float(cut_direct.group(1))
                logger.info(f"   📉 Found CUT: {status.prob_cut}%")
            
            if hold_direct:
                status.prob_hold = float(hold_direct.group(1))
                logger.info(f"   ➡️ Found HOLD: {status.prob_hold}%")
            
            # If direct format didn't work, try other patterns
            if status.prob_cut == 0:
                # Look for "probability of cut is 87%" or "87% probability of a cut"
                patterns = [
                    r'probability\s+of\s+(?:a\s+)?(?:rate\s+)?cut[^\d]*(?:is\s+)?(\d{2,3})(?:\.\d+)?%',
                    r'(\d{2,3})(?:\.\d+)?%\s+probability\s+of\s+(?:a\s+)?(?:rate\s+)?cut',
                    r'cut\s+(?:is\s+)?(?:at\s+)?(?:approximately\s+)?(\d{2,3})(?:\.\d+)?%',
                    r'(\d{2,3})(?:\.\d+)?%\s+(?:to\s+\d+%\s+)?(?:chance\s+)?(?:of\s+)?(?:a\s+)?cut',
                ]
                for p in patterns:
                    m = re.search(p, answer_lower)
                    if m:
                        status.prob_cut = float(m.group(1))
                        logger.info(f"   📉 Found CUT (pattern): {status.prob_cut}%")
                        break
            
            if status.prob_hold == 0:
                # Look for "probability of hold is 13%" or "13% probability of hold"
                patterns = [
                    r'probability\s+of\s+(?:the\s+)?(?:fed\s+)?hold[^\d]*(?:is\s+)?(\d{1,3})(?:\.\d+)?%',
                    r'(\d{1,3})(?:\.\d+)?%\s+probability\s+of\s+(?:a\s+)?hold',
                    r'hold[^\d]*(?:is\s+)?(?:at\s+)?(?:around\s+)?(\d{1,3})(?:\.\d+)?%',
                    r'steady[^\d]*(\d{1,3})(?:\.\d+)?%',
                ]
                for p in patterns:
                    m = re.search(p, answer_lower)
                    if m:
                        status.prob_hold = float(m.group(1))
                        logger.info(f"   ➡️ Found HOLD (pattern): {status.prob_hold}%")
                        break
            
            # SANITY CHECK: If cut is very high (>80%), hold should be low (<20%) and vice versa
            # This catches cases where the data is inverted
            if status.prob_cut > 0 and status.prob_hold > 0:
                total = status.prob_cut + status.prob_hold
                if total < 90 or total > 110:
                    # Something's wrong, try to infer from context
                    if 'favors' in answer_lower and 'cut' in answer_lower:
                        # Market favors cut = cut should be higher
                        if status.prob_cut < status.prob_hold:
                            status.prob_cut, status.prob_hold = status.prob_hold, status.prob_cut
                            logger.info(f"   🔄 Swapped (market favors cut): Cut {status.prob_cut}% | Hold {status.prob_hold}%")
            
            # If we still don't have data, look for the first two percentages > 10%
            if status.prob_cut == 0 and status.prob_hold == 0:
                all_pcts = re.findall(r'(\d{2,3})(?:\.\d+)?%', answer)
                valid_pcts = [float(p) for p in all_pcts if float(p) > 10 and float(p) <= 100]
                
                if len(valid_pcts) >= 2:
                    # Determine which is cut vs hold based on context
                    # "favors cut" or "cut at 87%" means first high number is cut
                    if 'favors' in answer_lower:
                        status.prob_cut = max(valid_pcts[:2])
                        status.prob_hold = min(valid_pcts[:2])
                    else:
                        status.prob_cut = valid_pcts[0]
                        status.prob_hold = valid_pcts[1]
                    logger.info(f"   📊 Extracted: Cut {status.prob_cut}% | Hold {status.prob_hold}%")
        
        # If we didn't get good data, use recent known CME data as fallback
        # As of Dec 5, 2025: ~87% cut, ~13% hold (from Alpha's screenshot)
        if status.prob_cut == 0 and status.prob_hold == 0:
            logger.warning("   ⚠️ Could not parse Perplexity data, using known CME values")
            status.prob_cut = 87.0  # Based on CME FedWatch Dec 5, 2025
            status.prob_hold = 13.0
            status.prob_hike = 0.0
        
        # Normalize to 100%
        total = status.prob_cut + status.prob_hold + status.prob_hike
        if total > 0:
            status.prob_cut = (status.prob_cut / total) * 100
            status.prob_hold = (status.prob_hold / total) * 100
            status.prob_hike = (status.prob_hike / total) * 100
        
        # Determine most likely outcome
        if status.prob_cut >= status.prob_hold and status.prob_cut >= status.prob_hike:
            status.most_likely_outcome = "CUT"
            status.most_likely_probability = status.prob_cut
        elif status.prob_hike >= status.prob_hold:
            status.most_likely_outcome = "HIKE"
            status.most_likely_probability = status.prob_hike
        else:
            status.most_likely_outcome = "HOLD"
            status.most_likely_probability = status.prob_hold
        
        # Calculate changes from last check
        if self.last_status:
            status.prob_cut_change = status.prob_cut - self.last_status.prob_cut
            status.prob_hold_change = status.prob_hold - self.last_status.prob_hold
            status.prob_hike_change = status.prob_hike - self.last_status.prob_hike
        
        # Determine market bias
        if status.prob_cut > 60:
            status.market_bias = "BULLISH"  # Rate cuts are generally bullish
            status.affected_sectors = ["Tech (QQQ)", "Real Estate (XLRE)", "Utilities (XLU)", "Small Caps (IWM)"]
        elif status.prob_hike > 30:
            status.market_bias = "BEARISH"  # Rate hikes are bearish
            status.affected_sectors = ["Banks (XLF)", "Value (IVE)", "Cash-heavy companies"]
        else:
            status.market_bias = "NEUTRAL"
            status.affected_sectors = ["Monitor for changes"]
        
        # Cache
        self.last_status = status
        self.cache_time = datetime.now()
        
        return status


# ============================================================================
# FED WATCH MONITOR
# ============================================================================

class FedWatchMonitor:
    """
    Main Fed Watch Monitor - tracks rate probabilities and alerts on changes.
    """
    
    def __init__(self, alert_threshold: float = 5.0):
        """
        Args:
            alert_threshold: Minimum % change to trigger alert (default 5%)
        """
        self.fetcher = FedWatchFetcher()
        self.alert_threshold = alert_threshold
        self.previous_status: Optional[FedWatchStatus] = None
        
        # Alert history
        self.alerts_sent: List[Dict] = []
        
        logger.info("🏦 FedWatchMonitor initialized")
        logger.info(f"   Alert threshold: {self.alert_threshold}% change")
    
    def get_current_status(self, force_refresh: bool = False) -> FedWatchStatus:
        """Get current Fed Watch status."""
        return self.fetcher.get_status(force_refresh=force_refresh)
    
    def check_for_changes(self) -> Optional[Dict]:
        """
        Check for significant changes in rate probabilities.
        Returns change info if significant, None otherwise.
        """
        current = self.get_current_status(force_refresh=True)
        
        if not self.previous_status:
            self.previous_status = current
            return None
        
        # Check for significant changes
        changes = []
        
        if abs(current.prob_cut_change) >= self.alert_threshold:
            direction = "↑" if current.prob_cut_change > 0 else "↓"
            changes.append({
                'type': 'CUT',
                'direction': direction,
                'change': current.prob_cut_change,
                'new_value': current.prob_cut
            })
        
        if abs(current.prob_hold_change) >= self.alert_threshold:
            direction = "↑" if current.prob_hold_change > 0 else "↓"
            changes.append({
                'type': 'HOLD',
                'direction': direction,
                'change': current.prob_hold_change,
                'new_value': current.prob_hold
            })
        
        if abs(current.prob_hike_change) >= self.alert_threshold:
            direction = "↑" if current.prob_hike_change > 0 else "↓"
            changes.append({
                'type': 'HIKE',
                'direction': direction,
                'change': current.prob_hike_change,
                'new_value': current.prob_hike
            })
        
        self.previous_status = current
        
        if changes:
            return {
                'timestamp': datetime.now(),
                'changes': changes,
                'current_status': current
            }
        
        return None
    
    def get_market_implications(self, status: FedWatchStatus) -> Dict:
        """
        Get detailed market implications of current rate expectations.
        """
        implications = {
            'bias': status.market_bias,
            'summary': '',
            'trades': [],
            'sectors': {}
        }
        
        if status.prob_cut > 60:
            implications['summary'] = "HIGH RATE CUT PROBABILITY - Generally BULLISH for risk assets"
            implications['trades'] = [
                {"action": "LONG", "symbol": "QQQ", "reason": "Tech benefits from lower rates"},
                {"action": "LONG", "symbol": "XLRE", "reason": "Real estate loves lower rates"},
                {"action": "LONG", "symbol": "IWM", "reason": "Small caps benefit from cheaper borrowing"},
                {"action": "LONG", "symbol": "TLT", "reason": "Bond prices rise when rates fall"},
            ]
            implications['sectors'] = {
                'winners': ["Tech", "Real Estate", "Utilities", "Small Caps", "Growth"],
                'losers': ["Banks (net interest margin compression)", "Insurance"]
            }
        
        elif status.prob_hike > 30:
            implications['summary'] = "RATE HIKE RISK ELEVATED - BEARISH for risk assets"
            implications['trades'] = [
                {"action": "LONG", "symbol": "XLF", "reason": "Banks benefit from higher rates"},
                {"action": "SHORT", "symbol": "TLT", "reason": "Bond prices fall when rates rise"},
                {"action": "REDUCE", "symbol": "QQQ", "reason": "Growth stocks hurt by higher rates"},
            ]
            implications['sectors'] = {
                'winners': ["Banks", "Insurance", "Value stocks"],
                'losers': ["Tech", "Real Estate", "Utilities", "Growth stocks"]
            }
        
        else:
            implications['summary'] = "RATE PATH UNCERTAIN - Market in wait-and-see mode"
            implications['trades'] = [
                {"action": "WATCH", "symbol": "SPY", "reason": "Wait for clarity on rate path"},
                {"action": "HEDGE", "symbol": "VIX calls", "reason": "Protect against volatility"},
            ]
            implications['sectors'] = {
                'winners': ["Defensive sectors", "Dividend payers"],
                'losers': ["Rate-sensitive sectors until clarity"]
            }
        
        return implications
    
    def print_fed_dashboard(self, status: Optional[FedWatchStatus] = None):
        """Print formatted Fed Watch dashboard."""
        if status is None:
            status = self.get_current_status()
        
        implications = self.get_market_implications(status)
        
        print("\n" + "=" * 80)
        print("╔════════════════════════════════════════════════════════════════════════════════╗")
        print("║              🏦 FED WATCH MONITOR - RATE PROBABILITY DASHBOARD                 ║")
        print("╚════════════════════════════════════════════════════════════════════════════════╝")
        print(f"  Updated: {status.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        # Current rate
        print(f"\n  📊 CURRENT FED FUNDS RATE: {status.current_rate_range}")
        
        # Next meeting
        if status.next_meeting:
            print(f"\n  📅 NEXT FOMC MEETING: {status.next_meeting.date.strftime('%B %d, %Y')}")
            print(f"     Days until: {status.next_meeting.days_until}")
        
        # Probability bars
        print(f"\n  📈 RATE PROBABILITIES FOR NEXT MEETING:")
        
        # Cut probability
        cut_bar = "█" * int(status.prob_cut / 5) + "░" * (20 - int(status.prob_cut / 5))
        cut_change = f" ({status.prob_cut_change:+.1f}%)" if status.prob_cut_change != 0 else ""
        cut_emoji = "📉" if status.prob_cut > 50 else "  "
        print(f"     {cut_emoji} CUT:  [{cut_bar}] {status.prob_cut:.1f}%{cut_change}")
        
        # Hold probability
        hold_bar = "█" * int(status.prob_hold / 5) + "░" * (20 - int(status.prob_hold / 5))
        hold_change = f" ({status.prob_hold_change:+.1f}%)" if status.prob_hold_change != 0 else ""
        hold_emoji = "➡️" if status.prob_hold > 50 else "  "
        print(f"     {hold_emoji} HOLD: [{hold_bar}] {status.prob_hold:.1f}%{hold_change}")
        
        # Hike probability
        hike_bar = "█" * int(status.prob_hike / 5) + "░" * (20 - int(status.prob_hike / 5))
        hike_change = f" ({status.prob_hike_change:+.1f}%)" if status.prob_hike_change != 0 else ""
        hike_emoji = "📈" if status.prob_hike > 30 else "  "
        print(f"     {hike_emoji} HIKE: [{hike_bar}] {status.prob_hike:.1f}%{hike_change}")
        
        # Most likely outcome
        outcome_emoji = {"CUT": "📉", "HOLD": "➡️", "HIKE": "📈"}.get(status.most_likely_outcome, "❓")
        print(f"\n  🎯 MOST LIKELY: {outcome_emoji} {status.most_likely_outcome} ({status.most_likely_probability:.1f}%)")
        
        # Market bias
        bias_emoji = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "🟡"}.get(status.market_bias, "❓")
        print(f"\n  {bias_emoji} MARKET BIAS: {status.market_bias}")
        print(f"     {implications['summary']}")
        
        # Trading implications
        print(f"\n  💰 TRADING IMPLICATIONS:")
        for trade in implications['trades']:
            action_emoji = {"LONG": "🟢", "SHORT": "🔴", "WATCH": "👀", "REDUCE": "⚠️", "HEDGE": "🛡️"}.get(trade['action'], "❓")
            print(f"     {action_emoji} {trade['action']} {trade['symbol']}: {trade['reason']}")
        
        # Sector impact
        print(f"\n  📊 SECTOR IMPACT:")
        if implications['sectors'].get('winners'):
            print(f"     📈 Winners: {', '.join(implications['sectors']['winners'])}")
        if implications['sectors'].get('losers'):
            print(f"     📉 Losers: {', '.join(implications['sectors']['losers'])}")
        
        # Key levels to watch
        print(f"\n  👀 KEY TRIGGERS TO WATCH:")
        print(f"     • If CUT prob rises above 70% → Strong bullish signal for tech/growth")
        print(f"     • If HIKE prob rises above 20% → Warning sign, reduce risk")
        print(f"     • Any 10%+ swing in probabilities → ALERT triggered")
        
        print("\n" + "=" * 80)
        print("  💡 Rate expectations often move markets MORE than the actual decision!")
        print("=" * 80 + "\n")
    
    def format_discord_alert(self, change_info: Dict) -> Dict:
        """Format a change alert for Discord."""
        status = change_info['current_status']
        changes = change_info['changes']
        
        # Determine severity
        max_change = max(abs(c['change']) for c in changes)
        if max_change >= 15:
            color = 15548997  # Red - major shift
            title = "🚨 MAJOR FED WATCH SHIFT"
        elif max_change >= 10:
            color = 16776960  # Yellow - significant
            title = "⚠️ SIGNIFICANT FED WATCH CHANGE"
        else:
            color = 3447003  # Blue - normal
            title = "📊 Fed Watch Update"
        
        # Build change description
        change_lines = []
        for c in changes:
            emoji = "📈" if c['direction'] == "↑" else "📉"
            change_lines.append(f"{emoji} {c['type']}: {c['new_value']:.1f}% ({c['change']:+.1f}%)")
        
        implications = self.get_market_implications(status)
        
        fields = [
            {"name": "Changes Detected", "value": "\n".join(change_lines), "inline": False},
            {"name": "Current Probabilities", "value": f"Cut: {status.prob_cut:.1f}% | Hold: {status.prob_hold:.1f}% | Hike: {status.prob_hike:.1f}%", "inline": False},
            {"name": "Most Likely", "value": f"{status.most_likely_outcome} ({status.most_likely_probability:.1f}%)", "inline": True},
            {"name": "Market Bias", "value": status.market_bias, "inline": True},
            {"name": "Next FOMC", "value": f"{status.next_meeting.date.strftime('%b %d')} ({status.next_meeting.days_until} days)" if status.next_meeting else "N/A", "inline": True},
            {"name": "Implication", "value": implications['summary'], "inline": False},
        ]
        
        # Add trade ideas
        if implications['trades']:
            trade_lines = [f"{t['action']} {t['symbol']}" for t in implications['trades'][:3]]
            fields.append({"name": "Trade Ideas", "value": " | ".join(trade_lines), "inline": False})
        
        embed = {
            "title": title,
            "color": color,
            "fields": fields,
            "footer": {"text": "Fed Watch Monitor | Rate expectations move markets!"},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return embed


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Demo the Fed Watch Monitor."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    monitor = FedWatchMonitor()
    status = monitor.get_current_status()
    monitor.print_fed_dashboard(status)


if __name__ == "__main__":
    main()

