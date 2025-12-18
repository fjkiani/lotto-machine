"""
🔥 SAVAGE LLM AGENTS - Base Classes and Core Agents

Grounded in REAL data structures from the codebase.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import re

logger = logging.getLogger(__name__)

# Import savage LLM function
try:
    from src.data.llm_api import query_llm_savage
except ImportError:
    logger.error("Cannot import query_llm_savage - savage LLM not available")
    query_llm_savage = None


class SavageAgent:
    """Base class for all savage agents - GROUNDED IN REAL DATA"""
    
    def __init__(self, name: str, domain: str, redis_client=None):
        self.name = name
        self.domain = domain
        self.redis = redis_client
        self.memory_key = f"agent_memory:{name}"
        # Store last 10 interactions in Redis
        self.max_memory = 10
    
    def analyze(self, data: Dict, context: Dict = None) -> Dict:
        """
        Analyze data and return savage insights
        
        Args:
            data: Domain-specific data (ACTUAL data structures from backend)
            context: Additional context (market regime, other agent insights, etc.)
        
        Returns:
            Dict with:
                - insight: str - Savage analysis
                - confidence: float - 0-1
                - actionable: bool - Is this actionable?
                - warnings: List[str] - Any warnings
                - data_summary: Dict - Summary of input data (for debugging)
        """
        if not query_llm_savage:
            return {
                "insight": "Savage LLM not available - check query_llm_savage import",
                "confidence": 0.0,
                "actionable": False,
                "warnings": ["Savage LLM not available"],
                "data_summary": {},
                "timestamp": datetime.now().isoformat(),
                "agent": self.name
            }
        
        # Build prompt from ACTUAL data structures
        prompt = self._build_prompt(data, context)
        
        # Get memory context
        memory_context = self._get_memory_context()
        if memory_context:
            prompt += f"\n\nPREVIOUS CONTEXT:\n{memory_context}"
        
        # Call savage LLM
        try:
            response = query_llm_savage(prompt, level="chained_pro")
        except Exception as e:
            logger.error(f"Error calling savage LLM for {self.name}: {e}")
            return {
                "insight": f"Error analyzing data: {str(e)}",
                "confidence": 0.0,
                "actionable": False,
                "warnings": [f"LLM error: {str(e)}"],
                "data_summary": self._summarize_data(data),
                "timestamp": datetime.now().isoformat(),
                "agent": self.name
            }
        
        # Parse and return
        result = self._parse_response(response, data)
        
        # Store in memory
        self._store_in_memory(data, result)
        
        return result
    
    def _build_prompt(self, data: Dict, context: Dict = None) -> str:
        """Build domain-specific prompt from ACTUAL data structures"""
        raise NotImplementedError(f"{self.__class__.__name__} must implement _build_prompt")
    
    def _parse_response(self, response: Dict, original_data: Dict) -> Dict:
        """
        Parse LLM response into structured format
        
        Args:
            response: LLM response dict with 'response' key
            original_data: Original data for context
        
        Returns:
            Structured insight dict
        """
        raw_text = response.get('response', '') if isinstance(response, dict) else str(response)
        
        # Extract confidence from text (look for patterns like "75% confident")
        confidence = self._extract_confidence(raw_text)
        
        # Extract actionable flag
        actionable = self._is_actionable(raw_text)
        
        # Extract warnings
        warnings = self._extract_warnings(raw_text)
        
        return {
            "insight": raw_text,
            "confidence": confidence,
            "actionable": actionable,
            "warnings": warnings,
            "data_summary": self._summarize_data(original_data),
            "timestamp": datetime.now().isoformat(),
            "agent": self.name
        }
    
    def _extract_confidence(self, text: str) -> float:
        """Extract confidence score from LLM response"""
        # Look for patterns like "75% confident", "75 percent confident"
        percent_match = re.search(r'(\d+)%?\s+confident', text, re.IGNORECASE)
        if percent_match:
            return min(max(float(percent_match.group(1)) / 100.0, 0.0), 1.0)
        
        # Look for "high/medium/low confidence"
        if re.search(r'high\s+confidence', text, re.IGNORECASE):
            return 0.8
        elif re.search(r'medium\s+confidence', text, re.IGNORECASE):
            return 0.6
        elif re.search(r'low\s+confidence', text, re.IGNORECASE):
            return 0.4
        
        return 0.7  # Default
    
    def _is_actionable(self, text: str) -> bool:
        """Determine if insight is actionable"""
        actionable_keywords = ['take', 'enter', 'exit', 'buy', 'sell', 'long', 'short', 'action', 'recommend']
        return any(keyword in text.lower() for keyword in actionable_keywords)
    
    def _extract_warnings(self, text: str) -> List[str]:
        """Extract warnings from LLM response"""
        warnings = []
        warning_patterns = [
            r'warning[:\s]+([^\.]+)',
            r'risk[:\s]+([^\.]+)',
            r'caution[:\s]+([^\.]+)',
        ]
        for pattern in warning_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            warnings.extend(matches)
        return warnings[:3]  # Max 3 warnings
    
    def _summarize_data(self, data: Dict) -> Dict:
        """Create summary of input data for debugging"""
        return {
            "data_type": type(data).__name__ if hasattr(data, '__class__') else "dict",
            "keys": list(data.keys())[:10] if isinstance(data, dict) else [],
            "size": len(str(data))
        }
    
    def _get_memory_context(self) -> Optional[str]:
        """Get recent memory from Redis"""
        if not self.redis:
            return None
        
        try:
            memory_json = self.redis.lrange(self.memory_key, 0, self.max_memory - 1)
            if memory_json:
                memories = [json.loads(m) if isinstance(m, bytes) else json.loads(m) for m in memory_json]
                return "\n".join([f"- {m.get('summary', '')}" for m in memories])
        except Exception as e:
            logger.warning(f"Error getting memory for {self.name}: {e}")
        
        return None
    
    def _store_in_memory(self, data: Dict, result: Dict):
        """Store interaction in Redis memory"""
        if not self.redis:
            return
        
        try:
            memory_entry = {
                "timestamp": datetime.now().isoformat(),
                "summary": result.get('insight', '')[:200],  # First 200 chars
                "confidence": result.get('confidence', 0.0),
                "actionable": result.get('actionable', False)
            }
            self.redis.lpush(self.memory_key, json.dumps(memory_entry))
            self.redis.ltrim(self.memory_key, 0, self.max_memory - 1)  # Keep last 10
        except Exception as e:
            logger.warning(f"Error storing memory for {self.name}: {e}")


class MarketAgent(SavageAgent):
    """Market analysis agent - uses ACTUAL data structures"""
    
    def __init__(self, redis_client=None):
        super().__init__("Market Agent", "market", redis_client)
    
    def _build_prompt(self, data: Dict, context: Dict = None) -> str:
        """
        Build prompt from ACTUAL market data
        
        Expected data structure:
        {
            'price': float,
            'change': float,
            'change_percent': float,
            'volume': int,
            'high': float,
            'low': float,
            'open': float,
            'regime': str,  # From RegimeDetector
            'vix': float,
            'symbol': str
        }
        """
        price = data.get('price', 0)
        change_pct = data.get('change_percent', 0)
        volume = data.get('volume', 0)
        regime = data.get('regime', 'UNKNOWN')
        vix = data.get('vix', 0)
        symbol = data.get('symbol', 'UNKNOWN')
        
        # Get context from other sources
        context_str = ""
        if context:
            synthesis = context.get('synthesis_result')
            if synthesis:
                if isinstance(synthesis, dict):
                    conf = synthesis.get('confluence', {})
                    if conf:
                        score = conf.get('score', 0)
                        bias = conf.get('bias', 'NEUTRAL')
                        context_str += f"\nSignal Brain Synthesis: {score:.0f}% {bias}"
                    
                    rec = synthesis.get('recommendation')
                    if rec:
                        action = rec.get('action', 'WAIT')
                        entry = rec.get('entry_price', 0)
                        context_str += f"\nRecommendation: {action} @ ${entry:.2f}"
        
        prompt = f"""You are the Market Agent - a savage financial intelligence specialist.

CURRENT MARKET DATA ({symbol}):
- Price: ${price:.2f}
- Change: {change_pct:+.2f}%
- Volume: {volume:,}
- Regime: {regime}
- VIX: {vix:.2f}

ADDITIONAL CONTEXT:
{context_str or 'No additional context'}

YOUR MISSION:
Analyze this market data with brutal honesty. Tell me:
1. What's the market REALLY telling us right now?
2. Is this a trap or a real move?
3. What's the regime and why does it matter?
4. What should I be watching for next?

Be savage. Be honest. Challenge weak analysis. Connect dots others miss.
Reference specific numbers (${price:.2f}, {change_pct:+.2f}%, VIX {vix:.2f}) in your analysis."""
        
        return prompt


class SignalAgent(SavageAgent):
    """Signal analysis agent - uses ACTUAL LiveSignal objects"""
    
    def __init__(self, redis_client=None):
        super().__init__("Signal Agent", "signals", redis_client)
    
    def _build_prompt(self, data: Dict, context: Dict = None) -> str:
        """
        Build prompt from ACTUAL signal data
        
        Expected data structure:
        {
            'signals': List[LiveSignal],  # ACTUAL LiveSignal objects or dicts
            'synthesis': Optional[SynthesisResult],  # ACTUAL SynthesisResult or dict
        }
        """
        signals = data.get('signals', [])
        synthesis = data.get('synthesis')
        
        # Format signals using ACTUAL LiveSignal structure
        signals_text = ""
        for i, signal in enumerate(signals[:10], 1):  # Max 10 signals
            # Handle both dataclass and dict formats
            if hasattr(signal, 'symbol'):
                symbol = signal.symbol
                action = signal.action.value if hasattr(signal.action, 'value') else str(signal.action)
                confidence = signal.confidence
                signal_type = signal.signal_type.value if hasattr(signal.signal_type, 'value') else str(signal.signal_type)
                entry = signal.entry_price
                target = signal.target_price
                stop = signal.stop_price
                is_master = signal.is_master_signal
                rationale = signal.rationale[:100] if signal.rationale else "No rationale"
            else:
                # Dict format
                symbol = signal.get('symbol', 'UNKNOWN')
                action = signal.get('action', 'UNKNOWN')
                confidence = signal.get('confidence', 0.0)
                signal_type = signal.get('signal_type', 'UNKNOWN')
                entry = signal.get('entry_price', 0.0)
                target = signal.get('target_price', 0.0)
                stop = signal.get('stop_price', 0.0)
                is_master = signal.get('is_master_signal', False)
                rationale = signal.get('rationale', 'No rationale')[:100]
            
            master_badge = "🔥 MASTER" if is_master else ""
            signals_text += f"""
{i}. {master_badge} {symbol} {action} @ ${entry:.2f}
   Type: {signal_type}
   Confidence: {confidence:.0%}
   Target: ${target:.2f} | Stop: ${stop:.2f}
   Rationale: {rationale}
"""
        
        # Add synthesis context if available
        synthesis_text = ""
        if synthesis:
            if isinstance(synthesis, dict):
                conf = synthesis.get('confluence', {})
                if conf:
                    score = conf.get('score', 0)
                    bias = conf.get('bias', 'NEUTRAL')
                    synthesis_text = f"""
SIGNAL BRAIN SYNTHESIS:
- Confluence: {score:.0f}% {bias}
"""
                rec = synthesis.get('recommendation')
                if rec:
                    action = rec.get('action', 'WAIT')
                    synthesis_text += f"- Recommendation: {action}"
                
                thinking = synthesis.get('thinking', '')
                if thinking:
                    synthesis_text += f"\n- Thinking: {thinking[:200]}"
            else:
                # Dataclass format
                if hasattr(synthesis, 'confluence'):
                    synthesis_text = f"""
SIGNAL BRAIN SYNTHESIS:
- Confluence: {synthesis.confluence.score:.0f}% {synthesis.confluence.bias.value if hasattr(synthesis.confluence.bias, 'value') else synthesis.confluence.bias}
- Recommendation: {synthesis.recommendation.action if synthesis.recommendation else 'WAIT'}
- Thinking: {synthesis.thinking[:200] if synthesis.thinking else 'No thinking provided'}
"""
        
        prompt = f"""You are the Signal Agent - a savage signal intelligence specialist.

ACTIVE SIGNALS ({len(signals)} total):
{signals_text}

{synthesis_text}

YOUR MISSION:
Analyze these signals with brutal honesty. Tell me:
1. Which signal should I take and WHY? (Be specific - reference signal numbers)
2. Why did each signal get generated? (Explain the logic)
3. Are these signals still valid? (Check timestamps, price proximity)
4. Which signals should I IGNORE and why? (Challenge low-confidence signals)

Be savage. Challenge low-confidence signals. Identify conflicts. Be actionable.
Reference specific signals by number (e.g., "Signal #3 is the best because...")."""
        
        return prompt


class DarkPoolAgent(SavageAgent):
    """Dark pool analysis agent - uses ACTUAL DP data structures"""
    
    def __init__(self, redis_client=None):
        super().__init__("Dark Pool Agent", "darkpool", redis_client)
    
    def _build_prompt(self, data: Dict, context: Dict = None) -> str:
        """
        Build prompt from ACTUAL DP data
        
        Expected data structure:
        {
            'levels': List[Dict],  # DP levels with 'price', 'volume', 'type', 'strength'
            'prints': List[Dict],  # Recent prints
            'battlegrounds': List[Dict],  # Battleground levels
            'summary': Dict,  # DP summary with buying_pressure, dp_percent, etc.
            'symbol': str,
            'current_price': float
        }
        """
        levels = data.get('levels', [])
        prints = data.get('prints', [])
        battlegrounds = data.get('battlegrounds', [])
        summary = data.get('summary', {})
        symbol = data.get('symbol', 'UNKNOWN')
        current_price = data.get('current_price', 0.0)
        
        # Format levels
        levels_text = ""
        for level in levels[:10]:  # Top 10 levels
            price = level.get('price', 0)
            volume = level.get('volume', 0)
            level_type = level.get('type', 'UNKNOWN')
            strength = level.get('strength', 'MODERATE')
            distance_pct = ((current_price - price) / price * 100) if price > 0 else 0
            
            levels_text += f"  ${price:.2f} ({level_type}) - {volume:,} shares - {strength} - {distance_pct:+.2f}% away\n"
        
        # Format battlegrounds
        bg_text = ""
        for bg in battlegrounds[:5]:  # Top 5 battlegrounds
            price = bg.get('price', 0)
            volume = bg.get('volume', 0)
            distance_pct = ((current_price - price) / price * 100) if price > 0 else 0
            bg_text += f"  ${price:.2f} - {volume:,} shares - {distance_pct:+.2f}% away\n"
        
        # Summary metrics
        buying_pressure = summary.get('buying_pressure', 0)
        dp_percent = summary.get('dp_percent', 0)
        total_volume = summary.get('total_volume', 0)
        
        prompt = f"""You are the Dark Pool Agent - a savage institutional intelligence specialist.

DARK POOL DATA ({symbol}):
- Current Price: ${current_price:.2f}
- DP % of Total Volume: {dp_percent:.1f}%
- Total DP Volume: {total_volume:,}
- Buying Pressure: {buying_pressure:.0f}/100

KEY LEVELS ({len(levels)} identified):
{levels_text}

BATTLEGROUNDS ({len(battlegrounds)} identified):
{bg_text}

RECENT PRINTS: {len(prints)} prints in last period

YOUR MISSION:
Analyze this dark pool activity with brutal honesty. Tell me:
1. What are institutions REALLY doing? (Buying or selling?)
2. Is this battleground going to hold or break? (Reference specific levels)
3. Why is there so much DP volume here? (Explain the institutional logic)
4. What's the institutional positioning? (Are they accumulating or distributing?)

Be savage. Explain institutional moves. Predict outcomes. Challenge retail narratives.
Reference specific levels (e.g., "${levels[0].get('price', 0):.2f} with {levels[0].get('volume', 0):,} shares" if levels else "No levels available")."""
        
        return prompt


class GammaAgent(SavageAgent):
    """Gamma exposure analysis agent"""
    
    def __init__(self, redis_client=None):
        super().__init__("Gamma Agent", "gamma", redis_client)
    
    def _build_prompt(self, data: Dict, context: Dict = None) -> str:
        gamma_data = data.get('gamma_data', {})
        symbol = data.get('symbol', 'UNKNOWN')
        price = data.get('price', 0)
        
        regime = gamma_data.get('current_regime', 'UNKNOWN')
        flip_level = gamma_data.get('gamma_flip_level')
        total_gex = gamma_data.get('total_gex', 0)
        distance_to_flip = gamma_data.get('distance_to_flip_pct', 0)
        
        prompt = f"""You are the Gamma Agent - a savage gamma exposure specialist.

CURRENT GAMMA DATA FOR {symbol}:
- Price: ${price:.2f}
- Gamma Regime: {regime}
- Gamma Flip Level: ${flip_level:.2f if flip_level else 'N/A'}
- Total GEX: {total_gex:,.0f} shares
- Distance to Flip: {distance_to_flip:.2f}%

CONTEXT:
{context or 'No additional context'}

YOUR MISSION:
Analyze this gamma exposure with brutal honesty. Tell me:
1. What does this gamma regime REALLY mean for price action?
2. Is the flip level significant? Why or why not?
3. Should I trade WITH or AGAINST the gamma regime?
4. What's the risk if price breaks through the flip level?
5. What's the best entry strategy given this gamma setup?

Be savage. Explain dealer positioning. Predict price behavior. Challenge weak analysis."""
        
        return prompt


class SqueezeAgent(SavageAgent):
    """Short squeeze detection agent"""
    
    def __init__(self, redis_client=None):
        super().__init__("Squeeze Agent", "squeeze", redis_client)
    
    def _build_prompt(self, data: Dict, context: Dict = None) -> str:
        squeeze_signal = data.get('squeeze_signal', {})
        symbol = data.get('symbol', 'UNKNOWN')
        
        score = squeeze_signal.get('score', 0)
        si_pct = squeeze_signal.get('short_interest_pct', 0)
        borrow_fee = squeeze_signal.get('borrow_fee_pct', 0)
        ftd_spike = squeeze_signal.get('ftd_spike_ratio', 0)
        dp_buying = squeeze_signal.get('dp_buying_pressure', 0)
        entry = squeeze_signal.get('entry_price', 0)
        stop = squeeze_signal.get('stop_price', 0)
        target = squeeze_signal.get('target_price', 0)
        rr = squeeze_signal.get('risk_reward_ratio', 0)
        
        prompt = f"""You are the Squeeze Agent - a savage short squeeze specialist.

SQUEEZE SETUP FOR {symbol}:
- Score: {score:.0f}/100
- Short Interest: {si_pct:.1f}%
- Borrow Fee: {borrow_fee:.1f}%
- FTD Spike: {ftd_spike:.2f}x
- DP Buying Pressure: {dp_buying:.1%}
- Entry: ${entry:.2f}
- Stop: ${stop:.2f}
- Target: ${target:.2f}
- R/R: {rr:.1f}:1

CONTEXT:
{context or 'No additional context'}

YOUR MISSION:
Analyze this squeeze setup with brutal honesty. Tell me:
1. Is this a REAL squeeze or just high SI?
2. What's the catalyst that could trigger the squeeze?
3. Is the R/R worth the risk?
4. What are the warning signs I should watch for?
5. When should I exit if the squeeze doesn't materialize?

Be savage. Identify fake squeezes. Explain the mechanics. Predict outcomes."""
        
        return prompt


class OptionsAgent(SavageAgent):
    """Options flow analysis agent"""
    
    def __init__(self, redis_client=None):
        super().__init__("Options Agent", "options", redis_client)
    
    def _build_prompt(self, data: Dict, context: Dict = None) -> str:
        options_signal = data.get('options_signal', {})
        symbol = data.get('symbol', 'UNKNOWN')
        
        direction = options_signal.get('direction', 'UNKNOWN')
        score = options_signal.get('score', 0)
        pc_ratio = options_signal.get('put_call_ratio', 0)
        max_pain = options_signal.get('max_pain', 0)
        call_oi = options_signal.get('total_call_oi', 0)
        put_oi = options_signal.get('total_put_oi', 0)
        entry = options_signal.get('entry_price', 0)
        stop = options_signal.get('stop_price', 0)
        target = options_signal.get('target_price', 0)
        
        prompt = f"""You are the Options Agent - a savage options flow specialist.

OPTIONS FLOW FOR {symbol}:
- Direction: {direction}
- Score: {score:.0f}/100
- P/C Ratio: {pc_ratio:.2f}
- Max Pain: ${max_pain:.2f}
- Call OI: {call_oi:,}
- Put OI: {put_oi:,}
- Entry: ${entry:.2f}
- Stop: ${stop:.2f}
- Target: ${target:.2f}

CONTEXT:
{context or 'No additional context'}

YOUR MISSION:
Analyze this options flow with brutal honesty. Tell me:
1. What is the options market REALLY telling us?
2. Is max pain a magnet or a trap?
3. What's the gamma exposure at key strikes?
4. Is this institutional flow or retail FOMO?
5. What's the best strategy given this options setup?

Be savage. Decode institutional positioning. Predict pin behavior. Challenge weak signals."""
        
        return prompt


class RedditAgent(SavageAgent):
    """Reddit sentiment analysis agent"""
    
    def __init__(self, redis_client=None):
        super().__init__("Reddit Agent", "reddit", redis_client)
    
    def _build_prompt(self, data: Dict, context: Dict = None) -> str:
        reddit_data = data.get('reddit_data', {})
        symbol = data.get('symbol', 'UNKNOWN')
        
        mentions = reddit_data.get('mentions', 0)
        sentiment = reddit_data.get('sentiment', 'NEUTRAL')
        score = reddit_data.get('score', 0)
        signal_type = reddit_data.get('signal_type', 'NONE')
        
        prompt = f"""You are the Reddit Agent - a savage contrarian sentiment specialist.

REDDIT SENTIMENT FOR {symbol}:
- Mentions: {mentions}
- Sentiment: {sentiment}
- Score: {score:.0f}/100
- Signal Type: {signal_type}

CONTEXT:
{context or 'No additional context'}

YOUR MISSION:
Analyze this Reddit sentiment with brutal honesty. Tell me:
1. Is this genuine retail interest or a pump?
2. Should I FADE or FOLLOW this sentiment?
3. What's the contrarian play here?
4. Is this stealth accumulation or FOMO?
5. What's the risk of trading against retail?

Be savage. Identify pumps. Explain contrarian logic. Predict retail behavior."""
        
        return prompt


class MacroAgent(SavageAgent):
    """Macro analysis agent (Fed, Trump, Economic)"""
    
    def __init__(self, redis_client=None):
        super().__init__("Macro Agent", "macro", redis_client)
    
    def _build_prompt(self, data: Dict, context: Dict = None) -> str:
        fed_data = data.get('fed_data', {})
        trump_data = data.get('trump_data', {})
        econ_data = data.get('econ_data', {})
        
        fed_status = fed_data.get('status', 'UNKNOWN')
        trump_sentiment = trump_data.get('sentiment', 'NEUTRAL')
        econ_events = econ_data.get('upcoming_events', [])
        
        prompt = f"""You are the Macro Agent - a savage macro intelligence specialist.

MACRO INTELLIGENCE:
- Fed Status: {fed_status}
- Trump Sentiment: {trump_sentiment}
- Economic Events: {len(econ_events)} upcoming

FED DETAILS:
{fed_data.get('details', 'No Fed data')}

TRUMP DETAILS:
{trump_data.get('details', 'No Trump data')}

ECONOMIC DETAILS:
{econ_data.get('details', 'No economic data')}

CONTEXT:
{context or 'No additional context'}

YOUR MISSION:
Analyze this macro environment with brutal honesty. Tell me:
1. What's the REAL macro picture right now?
2. How will Fed policy affect markets?
3. What's Trump's impact on market sentiment?
4. What economic events should I watch?
5. What's the macro risk to my positions?

Be savage. Connect macro dots. Predict policy impacts. Challenge weak narratives."""
        
        return prompt


class NarrativeBrainAgent(SavageAgent):
    """Master agent that synthesizes ALL other agents - uses ACTUAL data structures"""
    
    def __init__(self, agents: List[SavageAgent], redis_client=None):
        super().__init__("Narrative Brain", "synthesis", redis_client)
        self.agents = agents
    
    def synthesize(self, all_data: Dict) -> Dict:
        """
        Synthesize insights from all agents into one narrative
        
        Args:
            all_data: Dict with ACTUAL data structures:
                {
                    'market': MarketData,
                    'signals': List[LiveSignal],
                    'synthesis_result': SynthesisResult,
                    'narrative_update': Optional[NarrativeUpdate],
                    'dp_data': Dict,
                    'gamma_data': Dict,
                    'institutional_context': InstitutionalContext,
                    'checker_alerts': List[CheckerAlert],
                    ...
                }
        
        Returns:
            Unified narrative with savage insights
        """
        # Get insights from all agents
        agent_insights = {}
        for agent in self.agents:
            agent_data = all_data.get(agent.domain, {})
            if agent_data:  # Only analyze if data exists
                try:
                    insight = agent.analyze(agent_data, context=all_data)
                    agent_insights[agent.name] = insight
                except Exception as e:
                    logger.error(f"Error in {agent.name}: {e}")
                    agent_insights[agent.name] = {
                        "insight": f"Error: {str(e)}",
                        "confidence": 0.0,
                        "actionable": False,
                        "warnings": [f"Agent error: {str(e)}"]
                    }
        
        # Build synthesis prompt with ACTUAL data
        prompt = self._build_synthesis_prompt(all_data, agent_insights)
        
        # Call savage LLM
        if not query_llm_savage:
            return {
                "narrative": "Savage LLM not available",
                "confidence": 0.0,
                "agent_insights": agent_insights,
                "timestamp": datetime.now().isoformat(),
                "data_sources": list(all_data.keys())
            }
        
        try:
            response = query_llm_savage(prompt, level="chained_pro")
        except Exception as e:
            logger.error(f"Error calling savage LLM for Narrative Brain: {e}")
            return {
                "narrative": f"Error synthesizing: {str(e)}",
                "confidence": 0.0,
                "agent_insights": agent_insights,
                "timestamp": datetime.now().isoformat(),
                "data_sources": list(all_data.keys())
            }
        
        # Calculate overall confidence from agent insights
        confidences = [insight.get('confidence', 0.5) for insight in agent_insights.values()]
        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.5
        
        return {
            "narrative": response.get('response', '') if isinstance(response, dict) else str(response),
            "confidence": overall_confidence,
            "agent_insights": agent_insights,
            "timestamp": datetime.now().isoformat(),
            "data_sources": list(all_data.keys())  # What data was used
        }
    
    def _build_prompt(self, data: Dict, context: Dict = None) -> str:
        """Not used - Narrative Brain uses synthesize() instead"""
        return ""
    
    def _build_synthesis_prompt(self, all_data: Dict, agent_insights: Dict) -> str:
        """Build synthesis prompt from ALL actual data structures"""
        
        # Format agent insights
        insights_text = ""
        for agent_name, insight in agent_insights.items():
            insights_text += f"""
{agent_name}:
{insight.get('insight', 'No insight')[:300]}...
Confidence: {insight.get('confidence', 0.0):.0%}
"""
        
        # Get key data summaries
        synthesis = all_data.get('synthesis_result')
        narrative = all_data.get('narrative_update')
        signals = all_data.get('signals', [])
        inst_context = all_data.get('institutional_context')
        
        # Build data summary
        data_summary = ""
        
        if synthesis:
            if isinstance(synthesis, dict):
                conf = synthesis.get('confluence', {})
                if conf:
                    data_summary += f"""
SIGNAL BRAIN SYNTHESIS:
- Confluence: {conf.get('score', 0):.0f}% {conf.get('bias', 'NEUTRAL')}
"""
                rec = synthesis.get('recommendation')
                if rec:
                    data_summary += f"- Recommendation: {rec.get('action', 'WAIT')} @ ${rec.get('entry_price', 0):.2f}\n"
                
                ctx = synthesis.get('context', {})
                if ctx:
                    data_summary += f"- SPY: ${ctx.get('spy_price', 0):.2f}\n"
                    data_summary += f"- QQQ: ${ctx.get('qqq_price', 0):.2f}\n"
                    data_summary += f"- VIX: {ctx.get('vix_level', 0):.2f}\n"
            else:
                # Dataclass format
                if hasattr(synthesis, 'confluence'):
                    data_summary += f"""
SIGNAL BRAIN SYNTHESIS:
- Confluence: {synthesis.confluence.score:.0f}% {synthesis.confluence.bias.value if hasattr(synthesis.confluence.bias, 'value') else synthesis.confluence.bias}
- Recommendation: {synthesis.recommendation.action if synthesis.recommendation else 'WAIT'}
- SPY: ${synthesis.context.spy_price:.2f} ({synthesis.context.spy_trend_1h.value if hasattr(synthesis.context.spy_trend_1h, 'value') else synthesis.context.spy_trend_1h})
- QQQ: ${synthesis.context.qqq_price:.2f}
- VIX: {synthesis.context.vix_level:.2f}
"""
        
        if narrative:
            if isinstance(narrative, dict):
                data_summary += f"""
NARRATIVE BRAIN UPDATE:
- Title: {narrative.get('title', 'N/A')}
- Content: {narrative.get('content', '')[:200]}...
- Priority: {narrative.get('priority', 'MEDIUM')}
"""
            else:
                if hasattr(narrative, 'content'):
                    data_summary += f"""
NARRATIVE BRAIN UPDATE:
- Title: {narrative.title}
- Content: {narrative.content[:200]}...
- Priority: {narrative.priority.value if hasattr(narrative.priority, 'value') else narrative.priority}
"""
        
        if signals:
            master_signals = [
                s for s in signals 
                if (hasattr(s, 'is_master_signal') and s.is_master_signal) 
                or s.get('is_master_signal', False)
            ]
            data_summary += f"""
ACTIVE SIGNALS:
- Total: {len(signals)}
- Master (75%+): {len(master_signals)}
"""
        
        if inst_context:
            if isinstance(inst_context, dict):
                data_summary += f"""
INSTITUTIONAL CONTEXT:
- Buying Pressure: {inst_context.get('institutional_buying_pressure', 0):.0%}
- Squeeze Potential: {inst_context.get('squeeze_potential', 0):.0%}
- Gamma Pressure: {inst_context.get('gamma_pressure', 0):.0%}
- DP Battlegrounds: {len(inst_context.get('dp_battlegrounds', []))}
"""
            else:
                if hasattr(inst_context, 'institutional_buying_pressure'):
                    data_summary += f"""
INSTITUTIONAL CONTEXT:
- Buying Pressure: {inst_context.institutional_buying_pressure:.0%}
- Squeeze Potential: {inst_context.squeeze_potential:.0%}
- Gamma Pressure: {inst_context.gamma_pressure:.0%}
- DP Battlegrounds: {len(inst_context.dp_battlegrounds)}
"""
        
        prompt = f"""You are the Narrative Brain - the master savage intelligence agent.

You have insights from ALL specialized agents:

{insights_text}

ADDITIONAL DATA CONTEXT:
{data_summary}

YOUR MISSION:
Synthesize ALL of this into ONE unified market narrative. Tell me:
1. What's REALLY happening in the market right now? (Connect ALL the dots)
2. What are the key themes? (Identify patterns across all sources)
3. What should I be watching? (Prioritize what matters)
4. What's the big picture? (How does everything fit together?)
5. What's your actionable recommendation? (Be specific - entry, stop, target)

Be savage. Connect ALL the dots. Challenge weak analysis. Anticipate next moves.
Provide the ultimate market intelligence that makes everything make sense.
Reference specific numbers and data points from the agent insights above."""
        
        return prompt

