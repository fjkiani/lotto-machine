"""
Intelligence Synthesizer
Creates narrative synthesis from correlated intelligence

This is where we answer: "What REALLY happened in the market today?"
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import asyncio

logger = logging.getLogger(__name__)

class IntelligenceSynthesizer:
    """
    Synthesizes intelligence into coherent narrative
    
    Creates the story of:
    - What happened (the facts)
    - Why it happened (the catalysts)
    - Who moved it (the players)
    - What it means (the implications)
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.use_llm = config.get('use_llm_synthesis', True)
        
        logger.info("IntelligenceSynthesizer initialized")
    
    async def synthesize_intelligence(self, intelligence_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synthesize all intelligence into coherent narrative
        """
        try:
            logger.info("Starting intelligence synthesis...")
            
            correlations = intelligence_data.get('correlations', {})
            
            # Build synthesis structure
            synthesis = {
                'narrative': await self._generate_narrative(intelligence_data, correlations),
                'key_facts': await self._extract_key_facts(intelligence_data),
                'catalysts': await self._identify_catalysts(intelligence_data, correlations),
                'players': await self._identify_players(intelligence_data),
                'implications': await self._analyze_implications(intelligence_data, correlations),
                'confidence_level': self._determine_confidence_level(correlations),
                'actionable_insights': await self._generate_actionable_insights(intelligence_data, correlations),
                'timeline_summary': await self._summarize_timeline(correlations.get('timeline', [])),
                'timestamp': datetime.now()
            }
            
            logger.info(f"Synthesis complete - confidence: {synthesis['confidence_level']}")
            
            return synthesis
            
        except Exception as e:
            logger.error(f"Error synthesizing intelligence: {e}")
            return {}
    
    async def _generate_narrative(self, data: Dict[str, Any], 
                                  correlations: Dict[str, Any]) -> str:
        """
        Generate the main narrative - what REALLY happened
        """
        try:
            # This would ideally use an LLM for narrative generation
            # For now, construct from patterns
            
            patterns = correlations.get('patterns', [])
            confirmations = correlations.get('confirmations', [])
            conflicts = correlations.get('conflicts', [])
            
            narrative_parts = []
            
            # Opening: What happened
            narrative_parts.append(self._generate_opening(data, patterns))
            
            # Plot Twist: Why it happened
            narrative_parts.append(self._generate_plot_twist(data, correlations))
            
            # Flow Analysis: Who moved it
            narrative_parts.append(self._generate_flow_analysis(data, patterns))
            
            # Conclusion: What it means
            narrative_parts.append(self._generate_conclusion(data, correlations))
            
            return "\n\n".join(narrative_parts)
            
        except Exception as e:
            logger.error(f"Error generating narrative: {e}")
            return "Narrative generation failed."
    
    def _generate_opening(self, data: Dict[str, Any], patterns: List[Dict]) -> str:
        """Generate opening: What happened"""
        try:
            # Analyze market sentiment
            news_count = len(data.get('news', {}).get('articles', []))
            block_count = len(data.get('block_trades', {}).get('block_trades', []))
            options_count = len(data.get('options', {}).get('options_flows', []))
            
            opening = f"**Market Overview:**\n\n"
            opening += f"Analyzed {news_count} news sources, {block_count} block trades, "
            opening += f"and {options_count} options flows. "
            
            if patterns:
                opening += f"Detected {len(patterns)} significant patterns across multiple data sources."
            else:
                opening += "Market showed relatively normal activity patterns."
            
            return opening
            
        except Exception as e:
            logger.error(f"Error generating opening: {e}")
            return ""
    
    def _generate_plot_twist(self, data: Dict[str, Any], 
                            correlations: Dict[str, Any]) -> str:
        """Generate plot twist: Why it happened (catalysts)"""
        try:
            patterns = correlations.get('patterns', [])
            
            if not patterns:
                return "**The Catalyst:** No major catalysts identified in this period."
            
            plot_twist = "**The Catalyst:**\n\n"
            
            # Find news-price correlations
            news_patterns = [p for p in patterns if p.get('type') == 'block_trade_news_correlation']
            
            if news_patterns:
                plot_twist += f"Detected {len(news_patterns)} instances where significant trades "
                plot_twist += "coincided with news events, suggesting institutional reaction to breaking information."
            
            return plot_twist
            
        except Exception as e:
            logger.error(f"Error generating plot twist: {e}")
            return ""
    
    def _generate_flow_analysis(self, data: Dict[str, Any], 
                                patterns: List[Dict]) -> str:
        """Generate flow analysis: Who moved it"""
        try:
            blocks = data.get('block_trades', {}).get('block_trades', [])
            options = data.get('options', {}).get('options_flows', [])
            dark_pool = data.get('dark_pool', {}).get('dark_pool_data', {})
            
            flow_analysis = "**Money Flow:**\n\n"
            
            if blocks:
                flow_analysis += f"- {len(blocks)} block trades detected, suggesting institutional activity\n"
            
            if options:
                flow_analysis += f"- {len(options)} unusual options flows identified\n"
            
            if dark_pool:
                flow_analysis += f"- Dark pool activity monitored across multiple venues\n"
            
            return flow_analysis
            
        except Exception as e:
            logger.error(f"Error generating flow analysis: {e}")
            return ""
    
    def _generate_conclusion(self, data: Dict[str, Any], 
                            correlations: Dict[str, Any]) -> str:
        """Generate conclusion: What it means"""
        try:
            confidence = correlations.get('confidence_score', 0.5)
            
            conclusion = "**What It Means:**\n\n"
            
            if confidence >= 0.7:
                conclusion += "High confidence in the intelligence gathered. Multiple sources confirm "
                conclusion += "the identified patterns. This represents a significant market signal "
                conclusion += "worthy of immediate attention."
            elif confidence >= 0.4:
                conclusion += "Moderate confidence. Some patterns detected but require additional "
                conclusion += "confirmation. Monitor these developments closely for validation."
            else:
                conclusion += "Low confidence. Data sources show mixed signals or insufficient "
                conclusion += "correlation. Continue monitoring but avoid premature action."
            
            return conclusion
            
        except Exception as e:
            logger.error(f"Error generating conclusion: {e}")
            return ""
    
    async def _extract_key_facts(self, data: Dict[str, Any]) -> List[str]:
        """Extract key factual points"""
        try:
            facts = []
            
            # Extract from news
            news_articles = data.get('news', {}).get('articles', [])[:5]
            for article in news_articles:
                if article.get('headline'):
                    facts.append(f"News: {article['headline']}")
            
            # Extract from blocks
            blocks = data.get('block_trades', {}).get('block_trades', [])[:3]
            for block in blocks:
                if block.get('ticker'):
                    facts.append(f"Block: {block['ticker']} - ${block.get('value', 0):,.0f}")
            
            return facts
            
        except Exception as e:
            logger.error(f"Error extracting key facts: {e}")
            return []
    
    async def _identify_catalysts(self, data: Dict[str, Any], 
                                  correlations: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify key catalysts"""
        try:
            catalysts = []
            
            patterns = correlations.get('patterns', [])
            
            for pattern in patterns:
                if pattern.get('type') == 'block_trade_news_correlation':
                    catalysts.append({
                        'type': 'news_event',
                        'description': 'News-driven institutional activity',
                        'confidence': 'high' if len(pattern.get('related_news', [])) > 1 else 'medium'
                    })
            
            return catalysts
            
        except Exception as e:
            logger.error(f"Error identifying catalysts: {e}")
            return []
    
    async def _identify_players(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify key market players"""
        try:
            players = []
            
            # Identify from block trades
            blocks = data.get('block_trades', {}).get('block_trades', [])
            if blocks:
                players.append({
                    'type': 'institutional',
                    'activity_level': 'high' if len(blocks) > 10 else 'moderate',
                    'description': f'{len(blocks)} block trades detected'
                })
            
            # Identify from social sentiment
            social = data.get('social', {}).get('social_data', {})
            if social.get('reddit', {}).get('posts'):
                players.append({
                    'type': 'retail',
                    'activity_level': 'high',
                    'description': 'Active retail discussion detected'
                })
            
            return players
            
        except Exception as e:
            logger.error(f"Error identifying players: {e}")
            return []
    
    async def _analyze_implications(self, data: Dict[str, Any], 
                                   correlations: Dict[str, Any]) -> List[str]:
        """Analyze implications"""
        try:
            implications = []
            
            confidence = correlations.get('confidence_score', 0.5)
            
            if confidence >= 0.7:
                implications.append("High-probability setup for continued momentum")
                implications.append("Multiple sources confirm directional bias")
            
            patterns = correlations.get('patterns', [])
            if len(patterns) > 5:
                implications.append("Elevated market activity suggests major move in progress")
            
            return implications
            
        except Exception as e:
            logger.error(f"Error analyzing implications: {e}")
            return []
    
    def _determine_confidence_level(self, correlations: Dict[str, Any]) -> str:
        """Determine overall confidence level"""
        try:
            score = correlations.get('confidence_score', 0.5)
            
            if score >= 0.8:
                return "VERY HIGH"
            elif score >= 0.6:
                return "HIGH"
            elif score >= 0.4:
                return "MEDIUM"
            else:
                return "LOW"
                
        except Exception as e:
            logger.error(f"Error determining confidence: {e}")
            return "UNKNOWN"
    
    async def _generate_actionable_insights(self, data: Dict[str, Any], 
                                           correlations: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate actionable trading insights"""
        try:
            insights = []
            
            confidence = correlations.get('confidence_score', 0.5)
            patterns = correlations.get('patterns', [])
            
            if confidence >= 0.7 and patterns:
                insights.append({
                    'action': 'MONITOR',
                    'priority': 'HIGH',
                    'description': 'High-confidence patterns detected - prepare for potential entry'
                })
            
            if len(patterns) > 10:
                insights.append({
                    'action': 'ALERT',
                    'priority': 'CRITICAL',
                    'description': 'Elevated activity levels - major move possible'
                })
            
            return insights
            
        except Exception as e:
            logger.error(f"Error generating insights: {e}")
            return []
    
    async def _summarize_timeline(self, timeline: List[Dict[str, Any]]) -> str:
        """Summarize the event timeline"""
        try:
            if not timeline:
                return "No significant timeline events detected."
            
            summary = f"Timeline: {len(timeline)} events tracked. "
            
            # Count event types
            event_types = {}
            for event in timeline:
                event_type = event.get('type', 'unknown')
                event_types[event_type] = event_types.get(event_type, 0) + 1
            
            summary += "Distribution: " + ", ".join([f"{k}: {v}" for k, v in event_types.items()])
            
            return summary
            
        except Exception as e:
            logger.error(f"Error summarizing timeline: {e}")
            return ""



