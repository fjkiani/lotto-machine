"""
📖 NARRATIVE RECAP COMPONENT
Recaps market narratives from last week and how they evolved
"""

import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class NarrativeEvolution:
    """How a narrative evolved over the week"""
    date: str
    narrative: str
    direction: str  # "BULLISH", "BEARISH", "NEUTRAL"
    conviction: str  # "HIGH", "MEDIUM", "LOW"
    key_points: List[str]


@dataclass
class NarrativeRecapResult:
    """Result of narrative recap"""
    week_start: str
    week_end: str
    daily_narratives: List[NarrativeEvolution]
    dominant_narrative: str
    narrative_shifts: List[str]
    key_insights: List[str]
    summary: str


class NarrativeRecap:
    """
    Recaps market narratives from last week.
    
    What it does:
    - Loads narrative logs from last week
    - Tracks how narratives evolved
    - Identifies dominant themes
    - Detects narrative shifts
    """
    
    def __init__(self, log_dir: str = "logs/narratives"):
        """
        Initialize narrative recap.
        
        Args:
            log_dir: Base directory for narrative logs
        """
        self.log_dir = Path(log_dir)
        
        # Initialize NarrativeMemory for context
        try:
            from live_monitoring.agents.narrative_brain.narrative_brain import NarrativeMemory
            self.memory = NarrativeMemory(db_path="data/narrative_memory.db")
        except Exception as e:
            logger.warning(f"⚠️  Could not initialize NarrativeMemory: {e}")
            self.memory = None
    
    def generate_recap(self, week_start: Optional[str] = None,
                      week_end: Optional[str] = None) -> NarrativeRecapResult:
        """
        Generate recap for last week's narratives.
        
        Args:
            week_start: Start date (YYYY-MM-DD), defaults to last Monday
            week_end: End date (YYYY-MM-DD), defaults to last Friday
        
        Returns:
            NarrativeRecapResult with analysis
        """
        # Calculate week dates
        today = datetime.now()
        last_friday = today - timedelta(days=(today.weekday() + 3) % 7)
        if last_friday > today:
            last_friday -= timedelta(days=7)
        
        last_monday = last_friday - timedelta(days=4)
        
        if week_start:
            week_start_date = datetime.strptime(week_start, '%Y-%m-%d')
        else:
            week_start_date = last_monday
        
        if week_end:
            week_end_date = datetime.strptime(week_end, '%Y-%m-%d')
        else:
            week_end_date = last_friday
        
        week_start_str = week_start_date.strftime('%Y-%m-%d')
        week_end_str = week_end_date.strftime('%Y-%m-%d')
        
        logger.info(f"📖 Generating narrative recap: {week_start_str} to {week_end_str}")
        
        # Load narratives
        daily_narratives = self._load_narratives(week_start_str, week_end_str)
        
        # Analyze narratives
        dominant_narrative = self._identify_dominant_narrative(daily_narratives)
        narrative_shifts = self._detect_shifts(daily_narratives)
        key_insights = self._extract_insights(daily_narratives)
        
        # Generate summary
        summary = self._generate_summary(
            daily_narratives, dominant_narrative, narrative_shifts, key_insights
        )
        
        return NarrativeRecapResult(
            week_start=week_start_str,
            week_end=week_end_str,
            daily_narratives=daily_narratives,
            dominant_narrative=dominant_narrative,
            narrative_shifts=narrative_shifts,
            key_insights=key_insights,
            summary=summary
        )
    
    def _load_narratives(self, week_start: str, week_end: str) -> List[NarrativeEvolution]:
        """Load narrative logs for the week"""
        narratives = []
        
        current_date = datetime.strptime(week_start, '%Y-%m-%d')
        end_date = datetime.strptime(week_end, '%Y-%m-%d')
        
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            date_dir = self.log_dir / date_str
            
            if date_dir.exists():
                # Look for final narrative files
                narrative_files = list(date_dir.glob("*_final_narrative.json"))
                
                for file_path in narrative_files:
                    try:
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                            
                            # Extract the ACTUAL narrative content from the right fields
                            # Priority: macro_narrative > sector_narrative > asset_narrative > cross_asset_narrative
                            narrative_text = ""
                            
                            # Try to get full narrative - combine all available narratives
                            narratives_parts = []
                            if data.get('macro_narrative'):
                                narratives_parts.append(f"**Macro:** {data['macro_narrative']}")
                            if data.get('sector_narrative'):
                                narratives_parts.append(f"**Sector:** {data['sector_narrative']}")
                            if data.get('asset_narrative'):
                                narratives_parts.append(f"**Asset:** {data['asset_narrative']}")
                            if data.get('cross_asset_narrative'):
                                narratives_parts.append(f"**Cross-Asset:** {data['cross_asset_narrative']}")
                            
                            if narratives_parts:
                                narrative_text = "\n\n".join(narratives_parts)
                            elif data.get('narrative'):
                                narrative_text = data.get('narrative', '')
                            
                            # If still empty, try to fetch from NarrativeMemory
                            if not narrative_text and self.memory:
                                chain = self.memory.get_narrative_chain(days=1)
                                for entry in chain:
                                    if entry['date'] == date_str:
                                        narrative_text = entry.get('narrative', '')
                                        break
                            
                            # Extract symbol from filename
                            symbol = file_path.stem.split('_')[0].upper()
                            
                            narratives.append(NarrativeEvolution(
                                date=f"{date_str} ({symbol})",
                                narrative=narrative_text,
                                direction=data.get('overall_direction', 'NEUTRAL'),
                                conviction=data.get('conviction', 'MEDIUM'),
                                key_points=self._extract_key_points(data)
                            ))
                    except Exception as e:
                        logger.warning(f"⚠️  Failed to load {file_path}: {e}")
            
            current_date += timedelta(days=1)
        
        logger.info(f"   Loaded {len(narratives)} narrative entries")
        return narratives
    
    def _extract_key_points(self, data: Dict) -> List[str]:
        """Extract key points from narrative data"""
        points = []
        
        # Check uncertainties FIRST for validation errors (divergences!)
        uncertainties = data.get('uncertainties', [])
        for unc in uncertainties:
            if isinstance(unc, str):
                if 'VALIDATION ERROR' in unc:
                    # Clean up and show as divergence
                    clean_error = unc.replace('VALIDATION ERROR: ', '⚠️ DIVERGENCE: ')
                    points.append(clean_error)
                elif 'OVERRIDE' in unc and 'Predicted' in unc:
                    # Extract the prediction vs reality
                    clean_override = unc.split(' - ')[-1] if ' - ' in unc else unc
                    points.append(f"⚠️ MISMATCH: {clean_override}")
        
        # Causal chain is important
        if data.get('causal_chain') and 'heuristic' not in data.get('causal_chain', '').lower():
            points.append(f"🔗 {data['causal_chain']}")
        
        # Risk environment
        if data.get('risk_environment') and data.get('risk_environment') != 'NEUTRAL':
            points.append(f"📊 Risk: {data['risk_environment']}")
        
        # Duration
        if data.get('duration'):
            points.append(f"⏱️ {data['duration']}")
        
        # Institutional reality (if has real data)
        inst_reality = data.get('institutional_reality', {})
        if isinstance(inst_reality, dict) and inst_reality.get('summary') and 'heuristic' not in inst_reality.get('summary', '').lower():
            points.append(f"🏦 {inst_reality.get('summary', '')[:120]}")
        
        # Explicit divergences field
        divergences = data.get('divergences', [])
        if divergences:
            for div in divergences[:2]:
                if isinstance(div, dict):
                    points.append(f"⚠️ Divergence: {div.get('description', str(div)[:100])}")
                elif isinstance(div, str):
                    points.append(f"⚠️ Divergence: {div[:100]}")
        
        return points[:5]  # Max 5 points
    
    def _identify_dominant_narrative(self, narratives: List[NarrativeEvolution]) -> str:
        """Identify the dominant narrative theme"""
        if not narratives:
            return "No narratives available"
        
        # Count directions
        direction_counts = {}
        for narrative in narratives:
            direction = narrative.direction
            direction_counts[direction] = direction_counts.get(direction, 0) + 1
        
        if direction_counts:
            dominant = max(direction_counts.items(), key=lambda x: x[1])
            return f"{dominant[0]} ({dominant[1]} days)"
        
        return "NEUTRAL"
    
    def _detect_shifts(self, narratives: List[NarrativeEvolution]) -> List[str]:
        """Detect narrative shifts during the week"""
        shifts = []
        
        if len(narratives) < 2:
            return shifts
        
        for i in range(1, len(narratives)):
            prev = narratives[i-1]
            curr = narratives[i]
            
            if prev.direction != curr.direction:
                shifts.append(
                    f"{prev.date} → {curr.date}: {prev.direction} → {curr.direction}"
                )
        
        return shifts
    
    def _extract_insights(self, narratives: List[NarrativeEvolution]) -> List[str]:
        """Extract key insights from narratives"""
        insights = []
        
        # High conviction narratives
        high_conviction = [n for n in narratives if n.conviction == "HIGH"]
        if high_conviction:
            insights.append(f"{len(high_conviction)} days with HIGH conviction narratives")
        
        # Direction consistency
        if narratives:
            directions = [n.direction for n in narratives]
            if len(set(directions)) == 1:
                insights.append(f"Consistent {directions[0]} narrative all week")
            else:
                insights.append(f"Narrative shifted: {directions[0]} → {directions[-1]}")
        
        return insights
    
    def _generate_summary(self, narratives: List[NarrativeEvolution],
                         dominant: str, shifts: List[str], insights: List[str]) -> str:
        """Generate human-readable summary"""
        if not narratives:
            return "No narrative data available for last week."
        
        summary = f"**Narrative Recap ({len(narratives)} days):**\n\n"
        summary += f"🎯 **Dominant Theme:** {dominant}\n\n"
        
        # Show actual narrative content for each day
        for narrative in narratives[:3]:  # Show up to 3 days (to avoid Discord length limit)
            summary += f"📅 **{narrative.date}** ({narrative.direction}, {narrative.conviction} conviction):\n"
            
            # Show FULL narrative text (not truncated snippets)
            narrative_text = narrative.narrative
            if narrative_text and len(narrative_text.strip()) > 10:  # Has real content
                # Show first 2-3 sentences for context, but keep it readable
                sentences = narrative_text.split('. ')
                if len(sentences) > 3:
                    # Take first 3 sentences
                    full_text = '. '.join(sentences[:3]) + '.'
                    if len(full_text) > 500:
                        full_text = full_text[:500] + '...'
                else:
                    # Show all if short
                    full_text = narrative_text
                    if len(full_text) > 500:
                        full_text = full_text[:500] + '...'
                
                summary += f"   {full_text}\n"
            else:
                # If no narrative text, try to extract from other fields
                summary += f"   *No detailed narrative available*\n"
            
            # Show key points (max 3 for space)
            if narrative.key_points:
                summary += f"   💡 Key Points:\n"
                for point in narrative.key_points[:3]:  # Top 3 points
                    if point and len(point) < 200:
                        summary += f"      • {point}\n"
            
            summary += "\n"
        
        if shifts:
            summary += f"🔄 **Narrative Shifts ({len(shifts)}):**\n"
            for shift in shifts[:3]:
                summary += f"   • {shift}\n"
            summary += "\n"
        
        if insights:
            summary += f"💡 **Key Insights:**\n"
            for insight in insights:
                summary += f"   • {insight}\n"
        
        return summary

