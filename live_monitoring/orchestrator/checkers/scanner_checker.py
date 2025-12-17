"""
Scanner Checker - Scans market for new opportunities.

Extracted from unified_monitor.py for modularity.

This checker scans the broader market for high-potential tickers
based on short interest, dark pool activity, and options activity.
"""

import logging
from datetime import datetime
from typing import List, Optional, Set

from .base_checker import BaseChecker, CheckerAlert

logger = logging.getLogger(__name__)


class ScannerChecker(BaseChecker):
    """
    Scans market for new opportunities.
    
    Responsibilities:
    - Run market scan for high-score opportunities
    - Filter out already-alerted symbols
    - Generate alerts for top opportunities
    - Run squeeze detector on top opportunities
    """
    
    def __init__(
        self,
        alert_manager,
        opportunity_scanner=None,
        squeeze_detector=None,
        unified_mode=False
    ):
        """
        Initialize Scanner checker.
        
        Args:
            alert_manager: AlertManager instance for deduplication
            opportunity_scanner: OpportunityScanner instance
            squeeze_detector: SqueezeDetector instance (optional, for squeeze candidates)
            unified_mode: If True, suppresses individual alerts
        """
        super().__init__(alert_manager, unified_mode)
        self.opportunity_scanner = opportunity_scanner
        self.squeeze_detector = squeeze_detector
        
        # State management
        self.scanned_today: Set[str] = set()
    
    @property
    def name(self) -> str:
        """Return checker name for identification."""
        return "scanner_checker"

    def check(self) -> List[CheckerAlert]:
        """
        Scan market for new opportunities.
        
        Returns:
            List of CheckerAlert objects (empty if no opportunities)
        """
        if not self.opportunity_scanner:
            return []
        
        logger.info("🔍 Scanning for NEW OPPORTUNITIES...")
        
        try:
            # Get today's date for tracking
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Run market scan (lowered threshold from 50 to 45 to catch more opportunities)
            opportunities = self.opportunity_scanner.scan_market(min_score=45, max_results=10)
            
            if not opportunities:
                logger.info("   📊 No high-score opportunities found")
                return []
            
            alerts = []
            
            # Filter out already-alerted symbols today
            new_opportunities = [
                opp for opp in opportunities 
                if f"{today}:{opp.symbol}" not in self.scanned_today
            ]
            
            if not new_opportunities:
                logger.info("   📊 All opportunities already alerted today")
                return []
            
            # Send alerts for top 5 new opportunities
            for opp in new_opportunities[:5]:
                # Mark as alerted
                self.scanned_today.add(f"{today}:{opp.symbol}")
                
                alert = self._create_opportunity_alert(opp)
                if alert:
                    alerts.append(alert)
                    logger.info(f"   🔍 Opportunity alert sent for {opp.symbol} (Score: {opp.score:.0f})")
            
            # Also run squeeze detector on top opportunities
            if self.squeeze_detector:
                squeeze_opportunities = self.opportunity_scanner.scan_with_squeeze_detector(
                    self.squeeze_detector, 
                    min_score=55
                )
                
                for opp in squeeze_opportunities[:3]:
                    if f"{today}:SQUEEZE:{opp.symbol}" in self.scanned_today:
                        continue
                    
                    self.scanned_today.add(f"{today}:SQUEEZE:{opp.symbol}")
                    
                    alert = self._create_squeeze_candidate_alert(opp)
                    if alert:
                        alerts.append(alert)
                        logger.info(f"   🔥 Squeeze candidate alert sent for {opp.symbol}!")
            
            # Clean up old entries (older than today)
            self.scanned_today = {k for k in self.scanned_today if k.startswith(today)}
            
            return alerts
            
        except Exception as e:
            logger.error(f"   ❌ Opportunity scanner error: {e}")
            return []
    
    def _create_opportunity_alert(self, opp) -> Optional[CheckerAlert]:
        """Create a CheckerAlert from an opportunity."""
        score_color = 3066993 if opp.score >= 70 else 16776960  # Green if high, yellow otherwise
        
        embed = {
            "title": f"🔍 NEW OPPORTUNITY: {opp.symbol}",
            "color": score_color,
            "description": f"**Score: {opp.score:.0f}/100** | Found via market scan",
            "fields": [],
            "footer": {"text": f"Exploitation Phase 3 • Opportunity Scanner"},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add short interest if available
        if hasattr(opp, 'short_interest') and opp.short_interest and opp.short_interest > 0:
            embed["fields"].append({
                "name": "📊 Short Interest",
                "value": f"{opp.short_interest:.1f}%",
                "inline": True
            })
        
        # Add DP activity if available
        if hasattr(opp, 'dp_activity') and opp.dp_activity and opp.dp_activity > 0:
            embed["fields"].append({
                "name": "🔒 DP Levels",
                "value": f"{opp.dp_activity:.0f}",
                "inline": True
            })
        
        # Add squeeze score if available
        if hasattr(opp, 'squeeze_score') and opp.squeeze_score and opp.squeeze_score > 0:
            embed["fields"].append({
                "name": "🔥 Squeeze Score",
                "value": f"{opp.squeeze_score:.0f}/100",
                "inline": True
            })
        
        # Add reasons
        if hasattr(opp, 'reasons') and opp.reasons:
            embed["fields"].append({
                "name": "📝 Reasons",
                "value": "\n".join([f"• {r}" for r in opp.reasons[:5]]),
                "inline": False
            })
        
        # Suggest action based on score
        if opp.score >= 70:
            action = "⚡ **HIGH PRIORITY** - Add to watchlist for squeeze/gamma analysis"
        elif opp.score >= 60:
            action = "📈 **MEDIUM PRIORITY** - Monitor for entry setup"
        else:
            action = "👀 **LOW PRIORITY** - Keep on radar"
        
        embed["fields"].append({
            "name": "💡 Suggested Action",
            "value": action,
            "inline": False
        })
        
        content = f"🔍 **NEW OPPORTUNITY** | {opp.symbol} Score: {opp.score:.0f}/100"
        
        return CheckerAlert(
            embed=embed,
            content=content,
            alert_type="opportunity_scan",
            source="scanner_checker",
            symbol=opp.symbol
        )
    
    def _create_squeeze_candidate_alert(self, opp) -> Optional[CheckerAlert]:
        """Create a CheckerAlert for a squeeze candidate."""
        embed = {
            "title": f"🔥 SQUEEZE CANDIDATE: {opp.symbol}",
            "color": 15548997,  # Red for squeeze
            "description": f"**Squeeze Score: {opp.squeeze_score:.0f}/100** | SI: {opp.short_interest:.1f}%",
            "fields": [
                {"name": "📊 Short Interest", "value": f"{opp.short_interest:.1f}%", "inline": True},
                {"name": "🔥 Squeeze Score", "value": f"{opp.squeeze_score:.0f}/100", "inline": True},
            ],
            "footer": {"text": "Opportunity Scanner + Squeeze Detector"},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if hasattr(opp, 'reasons') and opp.reasons:
            embed["fields"].append({
                "name": "📝 Reasons",
                "value": "\n".join([f"• {r}" for r in opp.reasons[:3]]),
                "inline": False
            })
        
        content = f"🔥 **SQUEEZE CANDIDATE** | {opp.symbol} Score: {opp.squeeze_score:.0f}/100 | SI: {opp.short_interest:.1f}%"
        
        return CheckerAlert(
            embed=embed,
            content=content,
            alert_type="squeeze_candidate",
            source="scanner_checker",
            symbol=opp.symbol
        )

