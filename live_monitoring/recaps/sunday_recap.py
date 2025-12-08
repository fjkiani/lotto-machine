"""
📊 SUNDAY RECAP ORCHESTRATOR
Main orchestrator for Sunday market preparation recap
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass

from .components.dp_levels_recap import DPLevelsRecap, DPLevelsRecapResult
from .components.macro_recap import MacroRecap, MacroRecapResult
from .components.narrative_recap import NarrativeRecap, NarrativeRecapResult
from .components.signal_recap import SignalRecap, SignalRecapResult
from .components.week_prep import WeekPrep, WeekPrepResult

logger = logging.getLogger(__name__)


@dataclass
class SundayRecapResult:
    """Complete Sunday recap result"""
    timestamp: str
    week_start: str
    week_end: str
    dp_levels: DPLevelsRecapResult
    macro: MacroRecapResult
    narrative: NarrativeRecapResult
    signals: SignalRecapResult
    week_prep: WeekPrepResult
    formatted_message: str


class SundayRecap:
    """
    Sunday Recap Orchestrator
    
    Generates comprehensive Sunday recap by combining:
    - DP Levels Recap
    - Macro Recap
    - Narrative Recap
    - Signal Recap
    - Week Prep
    """
    
    def __init__(self):
        """Initialize Sunday recap"""
        self.dp_recap = DPLevelsRecap()
        self.macro_recap = MacroRecap()
        self.narrative_recap = NarrativeRecap()
        self.signal_recap = SignalRecap()
        self.week_prep = WeekPrep()
    
    def generate_recap(self, week_start: Optional[str] = None,
                      week_end: Optional[str] = None) -> Optional[SundayRecapResult]:
        """
        Generate complete Sunday recap.
        
        Args:
            week_start: Start date (YYYY-MM-DD), defaults to last Monday
            week_end: End date (YYYY-MM-DD), defaults to last Friday
        
        Returns:
            SundayRecapResult with all components, or None if no meaningful content
        """
        logger.info("📊 Generating Sunday Recap...")
        
        # Generate all components
        dp_result = self.dp_recap.generate_recap(week_start, week_end)
        macro_result = self.macro_recap.generate_recap(week_start, week_end)
        narrative_result = self.narrative_recap.generate_recap(week_start, week_end)
        signal_result = self.signal_recap.generate_recap(week_start, week_end)
        prep_result = self.week_prep.generate_prep()
        
        # Check if we have meaningful content
        has_content = (
            len(dp_result.levels_that_played) > 0 or
            len(macro_result.events) > 0 or
            len(narrative_result.daily_narratives) > 0 or
            signal_result.total_signals > 0 or
            len(prep_result.upcoming_events) > 0
        )
        
        if not has_content:
            logger.warning("⚠️  No meaningful content found - skipping recap")
            return None
        
        # Format for Discord
        formatted_message = self._format_for_discord(
            dp_result, macro_result, narrative_result, signal_result, prep_result
        )
        
        return SundayRecapResult(
            timestamp=datetime.now().isoformat(),
            week_start=dp_result.week_start,
            week_end=dp_result.week_end,
            dp_levels=dp_result,
            macro=macro_result,
            narrative=narrative_result,
            signals=signal_result,
            week_prep=prep_result,
            formatted_message=formatted_message
        )
    
    def _format_for_discord(self, dp: DPLevelsRecapResult, macro: MacroRecapResult,
                           narrative: NarrativeRecapResult, signals: SignalRecapResult,
                           prep: WeekPrepResult) -> str:
        """Format recap for Discord"""
        message = "📊 **SUNDAY MARKET RECAP**\n"
        message += f"*Week of {dp.week_start} to {dp.week_end}*\n"
        message += "=" * 50 + "\n\n"
        
        # DP Levels
        message += dp.summary + "\n\n"
        
        # Macro
        message += macro.summary + "\n\n"
        
        # Narrative
        message += narrative.summary + "\n\n"
        
        # Signals
        message += signals.summary + "\n\n"
        
        # Week Prep
        message += "🎯 **PREPARATION FOR NEXT WEEK:**\n"
        message += prep.summary + "\n\n"
        
        message += "=" * 50 + "\n"
        message += "✅ *Recap generated at " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "*"
        
        return message


def generate_sunday_recap(week_start: Optional[str] = None,
                         week_end: Optional[str] = None) -> str:
    """
    Convenience function to generate Sunday recap.
    
    Args:
        week_start: Start date (YYYY-MM-DD), defaults to last Monday
        week_end: End date (YYYY-MM-DD), defaults to last Friday
    
    Returns:
        Formatted Discord message
    """
    recap = SundayRecap()
    result = recap.generate_recap(week_start, week_end)
    return result.formatted_message

