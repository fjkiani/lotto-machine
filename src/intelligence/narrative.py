"""
Narrative Engine
LLM-powered narrative extraction and synthesis

Implements Alpha's blueprint:
- Batch recent events, anomalies, and flow details into LLM prompt every 2-5min
- LLM summarizes "Why" (e.g., 'Regional bank panic hit after Zions news')
- LLM clusters events ("multiple regional banks flagged in the news")
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import asyncio
import json

logger = logging.getLogger(__name__)

class NarrativeEngine:
    """
    LLM-powered narrative engine for market intelligence
    
    Features:
    - Batch processing of events and anomalies
    - LLM-powered "why" analysis
    - Event clustering and pattern recognition
    - Narrative synthesis for actionable insights
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # LLM configuration
        self.llm_provider = config.get('llm_provider', 'gemini')
        self.llm_model = config.get('llm_model', 'gemini-1.5-flash')
        self.batch_interval = config.get('batch_interval_minutes', 3)  # Every 3 minutes
        
        # Narrative templates
        self.prompt_templates = {
            'market_analysis': self._get_market_analysis_prompt(),
            'anomaly_explanation': self._get_anomaly_explanation_prompt(),
            'event_clustering': self._get_event_clustering_prompt()
        }
        
        logger.info("NarrativeEngine initialized - ready for LLM-powered analysis")
    
    async def initialize(self):
        """Initialize narrative engine"""
        try:
            # Test LLM connection
            await self._test_llm_connection()
            logger.info("NarrativeEngine initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing NarrativeEngine: {e}")
    
    async def cleanup(self):
        """Cleanup resources"""
        pass
    
    async def generate_narrative(self, events: List[Dict[str, Any]], 
                                 anomalies: List[Any], 
                                 time_window_minutes: int = 10) -> str:
        """
        Generate narrative from events and anomalies
        
        This is the core function that implements Alpha's blueprint:
        "Batch recent news, anomalous events, and flow details into an LLM prompt"
        """
        try:
            logger.info(f"Generating narrative for {len(events)} events and {len(anomalies)} anomalies")
            
            # Prepare data for LLM
            narrative_data = self._prepare_narrative_data(events, anomalies, time_window_minutes)
            
            # Generate different types of narratives
            narratives = {}
            
            # 1. Market Analysis Narrative
            narratives['market_analysis'] = await self._generate_market_analysis(narrative_data)
            
            # 2. Anomaly Explanation
            narratives['anomaly_explanation'] = await self._generate_anomaly_explanation(narrative_data)
            
            # 3. Event Clustering
            narratives['event_clustering'] = await self._generate_event_clustering(narrative_data)
            
            # 4. Synthesis
            narratives['synthesis'] = await self._synthesize_narratives(narratives)
            
            return narratives['synthesis']
            
        except Exception as e:
            logger.error(f"Error generating narrative: {e}")
            return "Narrative generation failed."
    
    def _prepare_narrative_data(self, events: List[Dict[str, Any]], 
                                anomalies: List[Any], 
                                time_window_minutes: int) -> Dict[str, Any]:
        """Prepare data for LLM analysis"""
        try:
            # Filter events by time window
            cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)
            
            recent_events = [
                event for event in events
                if datetime.fromisoformat(event.get('timestamp', '')) >= cutoff_time
            ]
            
            recent_anomalies = [
                anomaly for anomaly in anomalies
                if anomaly.timestamp >= cutoff_time
            ]
            
            # Categorize events
            news_events = [e for e in recent_events if e.get('type') == 'news']
            trade_events = [e for e in recent_events if e.get('type') == 'trade']
            options_events = [e for e in recent_events if e.get('type') == 'options']
            social_events = [e for e in recent_events if e.get('type') == 'social']
            
            # Categorize anomalies
            anomaly_types = {}
            for anomaly in recent_anomalies:
                anomaly_type = anomaly.anomaly_type
                if anomaly_type not in anomaly_types:
                    anomaly_types[anomaly_type] = []
                anomaly_types[anomaly_type].append(anomaly)
            
            return {
                'time_window_minutes': time_window_minutes,
                'total_events': len(recent_events),
                'total_anomalies': len(recent_anomalies),
                'news_events': news_events,
                'trade_events': trade_events,
                'options_events': options_events,
                'social_events': social_events,
                'anomaly_types': anomaly_types,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error preparing narrative data: {e}")
            return {}
    
    async def _generate_market_analysis(self, data: Dict[str, Any]) -> str:
        """Generate market analysis narrative"""
        try:
            prompt = self.prompt_templates['market_analysis'].format(
                news_count=len(data.get('news_events', [])),
                trade_count=len(data.get('trade_events', [])),
                options_count=len(data.get('options_events', [])),
                social_count=len(data.get('social_events', [])),
                anomaly_count=data.get('total_anomalies', 0),
                time_window=data.get('time_window_minutes', 10)
            )
            
            # Add recent events to prompt
            recent_events_text = self._format_events_for_prompt(data)
            prompt += f"\n\nRecent Events:\n{recent_events_text}"
            
            # Call LLM
            response = await self._call_llm(prompt)
            return response
            
        except Exception as e:
            logger.error(f"Error generating market analysis: {e}")
            return "Market analysis generation failed."
    
    async def _generate_anomaly_explanation(self, data: Dict[str, Any]) -> str:
        """Generate anomaly explanation narrative"""
        try:
            prompt = self.prompt_templates['anomaly_explanation'].format(
                anomaly_count=data.get('total_anomalies', 0),
                anomaly_types=list(data.get('anomaly_types', {}).keys())
            )
            
            # Add anomaly details to prompt
            anomaly_text = self._format_anomalies_for_prompt(data)
            prompt += f"\n\nAnomaly Details:\n{anomaly_text}"
            
            # Call LLM
            response = await self._call_llm(prompt)
            return response
            
        except Exception as e:
            logger.error(f"Error generating anomaly explanation: {e}")
            return "Anomaly explanation generation failed."
    
    async def _generate_event_clustering(self, data: Dict[str, Any]) -> str:
        """Generate event clustering narrative"""
        try:
            prompt = self.prompt_templates['event_clustering'].format(
                total_events=data.get('total_events', 0),
                time_window=data.get('time_window_minutes', 10)
            )
            
            # Add all events to prompt
            events_text = self._format_all_events_for_prompt(data)
            prompt += f"\n\nAll Events:\n{events_text}"
            
            # Call LLM
            response = await self._call_llm(prompt)
            return response
            
        except Exception as e:
            logger.error(f"Error generating event clustering: {e}")
            return "Event clustering generation failed."
    
    async def _synthesize_narratives(self, narratives: Dict[str, str]) -> str:
        """Synthesize all narratives into final summary"""
        try:
            synthesis_prompt = f"""
            Synthesize the following market intelligence narratives into a coherent summary:

            Market Analysis:
            {narratives.get('market_analysis', 'N/A')}

            Anomaly Explanation:
            {narratives.get('anomaly_explanation', 'N/A')}

            Event Clustering:
            {narratives.get('event_clustering', 'N/A')}

            Provide a concise summary that answers:
            1. What happened in the market?
            2. Why did it happen? (key drivers/catalysts)
            3. What are the implications?
            4. What should traders watch for?

            Format as a clear, actionable narrative suitable for traders.
            """
            
            response = await self._call_llm(synthesis_prompt)
            return response
            
        except Exception as e:
            logger.error(f"Error synthesizing narratives: {e}")
            return "Narrative synthesis failed."
    
    def _format_events_for_prompt(self, data: Dict[str, Any]) -> str:
        """Format events for LLM prompt"""
        try:
            events_text = []
            
            # News events
            for event in data.get('news_events', [])[:5]:  # Top 5
                events_text.append(f"NEWS: {event.get('text', '')[:100]}...")
            
            # Trade events
            for event in data.get('trade_events', [])[:5]:  # Top 5
                events_text.append(f"TRADE: {event.get('text', '')[:100]}...")
            
            # Options events
            for event in data.get('options_events', [])[:5]:  # Top 5
                events_text.append(f"OPTIONS: {event.get('text', '')[:100]}...")
            
            return "\n".join(events_text)
            
        except Exception as e:
            logger.error(f"Error formatting events: {e}")
            return ""
    
    def _format_anomalies_for_prompt(self, data: Dict[str, Any]) -> str:
        """Format anomalies for LLM prompt"""
        try:
            anomaly_text = []
            
            for anomaly_type, anomalies in data.get('anomaly_types', {}).items():
                count = len(anomalies)
                avg_severity = sum(a.severity for a in anomalies) / count if count > 0 else 0
                
                anomaly_text.append(f"{anomaly_type.upper()}: {count} instances, avg severity {avg_severity:.2f}")
            
            return "\n".join(anomaly_text)
            
        except Exception as e:
            logger.error(f"Error formatting anomalies: {e}")
            return ""
    
    def _format_all_events_for_prompt(self, data: Dict[str, Any]) -> str:
        """Format all events for LLM prompt"""
        try:
            all_events = []
            
            # Combine all event types
            for event_type in ['news_events', 'trade_events', 'options_events', 'social_events']:
                for event in data.get(event_type, []):
                    all_events.append({
                        'type': event_type.replace('_events', ''),
                        'ticker': event.get('ticker', 'MARKET'),
                        'text': event.get('text', ''),
                        'timestamp': event.get('timestamp', '')
                    })
            
            # Sort by timestamp
            all_events.sort(key=lambda x: x.get('timestamp', ''))
            
            # Format for prompt
            events_text = []
            for event in all_events[-20:]:  # Last 20 events
                events_text.append(f"{event['type'].upper()} ({event['ticker']}): {event['text'][:80]}...")
            
            return "\n".join(events_text)
            
        except Exception as e:
            logger.error(f"Error formatting all events: {e}")
            return ""
    
    async def _call_llm(self, prompt: str) -> str:
        """Call LLM with prompt"""
        try:
            # Use existing LLM infrastructure
            try:
                from src.data.llm_api import query_llm
            except ImportError:
                # Fallback for demo
                return f"LLM call simulated: {prompt[:100]}..."
            
            # Note: query_llm might not be async, adjust as needed
            response = query_llm(
                prompt=prompt,
                provider=self.llm_provider,
                model=self.llm_model
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return f"LLM call failed: {str(e)}"
    
    async def _test_llm_connection(self):
        """Test LLM connection"""
        try:
            test_prompt = "Test connection. Respond with 'OK'."
            response = await self._call_llm(test_prompt)
            logger.debug(f"LLM test response: {response[:50]}...")
        except Exception as e:
            logger.warning(f"LLM connection test failed: {e}")
    
    def _get_market_analysis_prompt(self) -> str:
        """Get market analysis prompt template"""
        return """
        Analyze the following market activity and provide insights:

        Activity Summary:
        - News Events: {news_count}
        - Trade Events: {trade_count}
        - Options Events: {options_count}
        - Social Events: {social_count}
        - Anomalies Detected: {anomaly_count}
        - Time Window: {time_window} minutes

        Provide analysis covering:
        1. Overall market sentiment and direction
        2. Key themes and patterns
        3. Notable events or developments
        4. Potential implications for traders

        Be concise and actionable.
        """
    
    def _get_anomaly_explanation_prompt(self) -> str:
        """Get anomaly explanation prompt template"""
        return """
        Explain the following market anomalies:

        Anomaly Summary:
        - Total Anomalies: {anomaly_count}
        - Anomaly Types: {anomaly_types}

        For each anomaly type, explain:
        1. What it indicates about market activity
        2. Potential causes or drivers
        3. Significance for traders
        4. Historical context if relevant

        Focus on actionable insights for trading decisions.
        """
    
    def _get_event_clustering_prompt(self) -> str:
        """Get event clustering prompt template"""
        return """
        Analyze and cluster the following market events:

        Event Summary:
        - Total Events: {total_events}
        - Time Window: {time_window} minutes

        Identify:
        1. Related events that form patterns
        2. Clusters of activity around specific themes
        3. Temporal relationships between events
        4. Potential cause-and-effect relationships

        Group events by:
        - Thematic clusters (e.g., "banking sector", "tech earnings")
        - Temporal clusters (events happening close in time)
        - Causal clusters (events that may have influenced each other)

        Provide clear groupings with explanations.
        """
