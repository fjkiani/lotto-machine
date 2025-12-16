"""
📅 ECONOMIC CALENDAR TOOL
Access to economic events and predictions
"""

import logging
from typing import Dict, Any, List
from datetime import datetime
from .base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class EconomicTool(BaseTool):
    """
    Economic Calendar Tool
    
    Provides:
    - Today's economic events
    - Upcoming high-impact events
    - Event impact analysis
    """
    
    def __init__(self):
        """Initialize Economic tool"""
        try:
            from live_monitoring.agents.economic import EconomicIntelligenceEngine
            from live_monitoring.agents.economic.calendar import EconomicCalendar
            self.econ_engine = EconomicIntelligenceEngine()
            self.calendar = EconomicCalendar()
            logger.info("✅ Economic Tool initialized")
        except Exception as e:
            logger.warning(f"⚠️ Economic Tool init failed: {e}")
            self.econ_engine = None
            self.calendar = None
    
    @property
    def name(self) -> str:
        return "economic"
    
    @property
    def description(self) -> str:
        return "Economic events, calendar, and impact analysis"
    
    @property
    def capabilities(self) -> List[str]:
        return [
            "get_today_events - Today's economic events",
            "get_upcoming - Upcoming high-impact events",
            "get_impact - Event impact analysis"
        ]
    
    @property
    def keywords(self) -> List[str]:
        return [
            "economic", "calendar", "event", "data", "cpi",
            "gdp", "jobs", "nfp", "ppi", "retail", "pce",
            "ism", "unemployment", "claims"
        ]
    
    def execute(self, params: Dict[str, Any]) -> ToolResult:
        """Execute economic query"""
        action = params.get("action", "today")
        
        try:
            if action == "today":
                return self._get_today_events()
            elif action == "upcoming":
                return self._get_upcoming()
            else:
                return self._get_today_events()
                
        except Exception as e:
            logger.error(f"Economic Tool error: {e}")
            return ToolResult(
                success=False,
                data={},
                error=str(e)
            )
    
    def _get_today_events(self) -> ToolResult:
        """Get today's economic events"""
        events_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().isoformat(),
            "events": []
        }
        
        if self.calendar:
            try:
                events = self.calendar.get_today_events()
                events_data["events"] = events if events else []
            except Exception as e:
                logger.debug(f"Calendar error: {e}")
        
        # Add market impact assessment
        high_impact = len([e for e in events_data["events"] if e.get("importance") == "HIGH"])
        events_data["high_impact_count"] = high_impact
        events_data["risk_level"] = "HIGH" if high_impact >= 2 else "MEDIUM" if high_impact == 1 else "LOW"
        
        return ToolResult(
            success=True,
            data=events_data
        )
    
    def _get_upcoming(self) -> ToolResult:
        """Get upcoming high-impact events"""
        events_data = {
            "timestamp": datetime.now().isoformat(),
            "events": []
        }
        
        if self.calendar:
            try:
                events = self.calendar.get_upcoming_events(days=7)
                events_data["events"] = [e for e in events if e.get("importance") == "HIGH"][:5]
            except Exception as e:
                logger.debug(f"Upcoming events error: {e}")
        
        return ToolResult(
            success=True,
            data=events_data
        )
    
    def format_response(self, result: ToolResult) -> str:
        """Format result for Discord display"""
        if not result.success:
            return f"❌ Error: {result.error}"
        
        data = result.data
        
        lines = ["📅 **Economic Calendar**\n"]
        
        # Risk level
        if data.get("risk_level"):
            risk_emoji = "🔴" if data["risk_level"] == "HIGH" else "🟡" if data["risk_level"] == "MEDIUM" else "🟢"
            lines.append(f"{risk_emoji} **Event Risk:** {data['risk_level']}")
        
        # Events
        events = data.get("events", [])
        if events:
            lines.append("\n**Events:**")
            for event in events[:5]:
                name = event.get("name", "Unknown Event")
                time = event.get("time", "TBD")
                importance = event.get("importance", "MEDIUM")
                imp_emoji = "🔴" if importance == "HIGH" else "🟡" if importance == "MEDIUM" else "🟢"
                lines.append(f"  {imp_emoji} {time} - {name}")
        else:
            lines.append("\n📭 No major economic events today")
        
        return "\n".join(lines)



