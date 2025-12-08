#!/usr/bin/env python3
"""
TRUMP PATTERN LEARNER AGENT
===========================
Autonomous agent that learns patterns from historical Trump statements.
Calculates correlations, updates statistics, provides data-driven predictions.

This is AGENT 2 in the Trump Intelligence System.
"""

import os
import sys
import logging
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from trump_data_models import (
    TrumpStatement, TopicCorrelation, Prediction, 
    SimilarStatement, TrumpSignal, AgentAccuracy
)
from trump_database import TrumpDatabase

logger = logging.getLogger(__name__)


class TrumpPatternAgent:
    """
    Learns patterns from historical Trump statements and their market reactions.
    
    Key capabilities:
    1. Calculate topic-specific correlations
    2. Find similar historical statements
    3. Make data-driven predictions
    4. Track and report accuracy
    """
    
    def __init__(self, db: TrumpDatabase = None):
        self.db = db or TrumpDatabase()
        self.agent_name = "pattern_learner"
        
        # Cache for performance
        self._correlation_cache: Dict[str, TopicCorrelation] = {}
        self._cache_updated = None
        
        logger.info("🧠 Trump Pattern Agent initialized")
    
    def update_topic_correlations(self) -> Dict[str, TopicCorrelation]:
        """
        Calculate correlations for all topics based on historical data.
        This is the LEARNING function - it learns from past data.
        """
        logger.info("📈 Updating topic correlations...")
        
        # Get all statements with market data
        statements = self.db.get_all_statements_with_market_data()
        
        if not statements:
            logger.warning("No statements with market data to learn from")
            return {}
        
        # Group by topic
        topic_data = defaultdict(list)
        
        for stmt in statements:
            if stmt.spy_change_1hr is None:
                continue
            
            for topic in stmt.topics:
                topic_data[topic].append({
                    'change': stmt.spy_change_1hr,
                    'timestamp': stmt.timestamp,
                    'is_market_hours': stmt.is_market_hours,
                    'sentiment': stmt.sentiment,
                    'intensity': stmt.intensity
                })
        
        # Calculate correlations for each topic
        correlations = {}
        
        for topic, data_points in topic_data.items():
            if len(data_points) < 3:  # Need minimum data
                continue
            
            changes = [d['change'] for d in data_points]
            
            # Basic statistics
            avg_change = np.mean(changes)
            std_change = np.std(changes)
            median_change = np.median(changes)
            
            # Direction counts
            bullish = sum(1 for c in changes if c > 0.1)
            bearish = sum(1 for c in changes if c < -0.1)
            neutral = len(changes) - bullish - bearish
            
            # By market session
            premarket = [d['change'] for d in data_points if not d['is_market_hours'] and d['timestamp'].hour < 9]
            rth = [d['change'] for d in data_points if d['is_market_hours']]
            afterhours = [d['change'] for d in data_points if not d['is_market_hours'] and d['timestamp'].hour >= 16]
            
            correlation = TopicCorrelation(
                topic=topic,
                statement_count=len(data_points),
                avg_spy_change_1hr=round(avg_change, 4),
                std_spy_change_1hr=round(std_change, 4),
                median_spy_change_1hr=round(median_change, 4),
                bullish_count=bullish,
                bearish_count=bearish,
                neutral_count=neutral,
                premarket_avg_impact=round(np.mean(premarket), 4) if premarket else 0,
                rth_avg_impact=round(np.mean(rth), 4) if rth else 0,
                afterhours_avg_impact=round(np.mean(afterhours), 4) if afterhours else 0,
                last_updated=datetime.now()
            )
            
            # Save to database
            self.db.save_topic_correlation(correlation)
            correlations[topic] = correlation
            
            logger.debug(f"   {topic}: avg={avg_change:+.3f}%, n={len(data_points)}")
        
        self._correlation_cache = correlations
        self._cache_updated = datetime.now()
        
        logger.info(f"✅ Updated {len(correlations)} topic correlations")
        return correlations
    
    def get_topic_correlation(self, topic: str) -> Optional[TopicCorrelation]:
        """Get correlation for a specific topic"""
        # Check cache
        if topic in self._correlation_cache:
            return self._correlation_cache[topic]
        
        # Check database
        return self.db.get_topic_correlation(topic)
    
    def find_similar_statements(self, statement: TrumpStatement, top_k: int = 10) -> List[SimilarStatement]:
        """
        Find historically similar statements.
        Uses topic overlap and entity overlap for similarity.
        
        In the future: Use embeddings for semantic similarity.
        """
        all_statements = self.db.get_all_statements_with_market_data()
        
        if not all_statements:
            return []
        
        similarities = []
        
        for hist_stmt in all_statements:
            if hist_stmt.id == statement.id:
                continue
            
            # Calculate similarity based on topics and entities
            topic_overlap = len(set(statement.topics) & set(hist_stmt.topics))
            entity_overlap = len(set(statement.entities) & set(hist_stmt.entities))
            
            # Weighted similarity score
            similarity = (topic_overlap * 0.6 + entity_overlap * 0.4) / max(
                len(statement.topics) + len(statement.entities), 1
            )
            
            if similarity > 0.2 and hist_stmt.spy_change_1hr is not None:
                similarities.append(SimilarStatement(
                    statement=hist_stmt,
                    similarity_score=round(similarity, 3),
                    market_reaction=hist_stmt.spy_change_1hr
                ))
        
        # Sort by similarity and return top_k
        similarities.sort(key=lambda x: x.similarity_score, reverse=True)
        return similarities[:top_k]
    
    def predict_impact(self, statement: TrumpStatement) -> Dict[str, Any]:
        """
        Predict market impact based on historical patterns.
        This is DATA-DRIVEN, not hardcoded rules.
        """
        # Find similar statements
        similar = self.find_similar_statements(statement, top_k=10)
        
        # Get topic correlations
        topic_impacts = []
        for topic in statement.topics:
            corr = self.get_topic_correlation(topic)
            if corr and corr.statement_count >= 3:
                topic_impacts.append({
                    'topic': topic,
                    'avg_impact': corr.avg_spy_change_1hr,
                    'std': corr.std_spy_change_1hr,
                    'n': corr.statement_count
                })
        
        # Calculate prediction
        if similar:
            # Weighted average of similar statement reactions
            weights = [s.similarity_score for s in similar]
            reactions = [s.market_reaction for s in similar]
            
            weighted_avg = np.average(reactions, weights=weights)
            reaction_std = np.std(reactions)
            
            # Direction
            if weighted_avg > 0.1:
                direction = "BULLISH"
            elif weighted_avg < -0.1:
                direction = "BEARISH"
            else:
                direction = "NEUTRAL"
            
            # Confidence based on:
            # 1. Number of similar statements
            # 2. Consistency of reactions
            # 3. Similarity scores
            n_factor = min(len(similar) / 10, 1.0)  # More similar = more confident
            consistency = 1 - min(reaction_std / 2, 1.0)  # Lower std = more confident
            similarity_factor = np.mean(weights)  # Higher similarity = more confident
            
            confidence = (n_factor * 0.3 + consistency * 0.4 + similarity_factor * 0.3)
            
            # Magnitude estimate
            magnitude = abs(weighted_avg)
            
        else:
            # Fall back to topic correlations
            if topic_impacts:
                avg_impact = np.mean([t['avg_impact'] for t in topic_impacts])
                direction = "BULLISH" if avg_impact > 0.1 else "BEARISH" if avg_impact < -0.1 else "NEUTRAL"
                magnitude = abs(avg_impact)
                confidence = 0.3  # Lower confidence without similar statements
            else:
                direction = "NEUTRAL"
                magnitude = 0.0
                confidence = 0.1
        
        # Build reasoning
        reasoning_parts = []
        
        if similar:
            reasoning_parts.append(f"Based on {len(similar)} similar historical statements")
            top_similar = similar[:3]
            avg_reaction = np.mean([s.market_reaction for s in top_similar])
            reasoning_parts.append(f"Average reaction of top 3 similar: {avg_reaction:+.2f}%")
        
        if topic_impacts:
            for ti in topic_impacts[:2]:
                reasoning_parts.append(f"Topic '{ti['topic']}': historically {ti['avg_impact']:+.2f}% avg (n={ti['n']})")
        
        reasoning = ". ".join(reasoning_parts) if reasoning_parts else "Insufficient historical data"
        
        return {
            'direction': direction,
            'magnitude': round(magnitude, 3),
            'confidence': round(confidence, 3),
            'reasoning': reasoning,
            'similar_count': len(similar),
            'topic_correlations': topic_impacts,
            'agent_name': self.agent_name
        }
    
    def generate_signal(self, statement: TrumpStatement) -> Optional[TrumpSignal]:
        """
        Generate a trading signal for a Trump statement.
        Combines all analysis into actionable signal.
        """
        # Get prediction
        prediction = self.predict_impact(statement)
        
        # Find similar statements
        similar = self.find_similar_statements(statement, top_k=5)
        
        # Get topic correlation
        topic_corr = None
        if statement.topics:
            topic_corr = self.get_topic_correlation(statement.topics[0])
        
        # Determine if we should trade
        # Dynamic threshold based on historical accuracy
        accuracy_stats = self.db.get_prediction_accuracy()
        base_threshold = 0.5
        
        # Adjust threshold based on past accuracy
        if accuracy_stats and accuracy_stats.get('overall_accuracy', 0) > 0.6:
            base_threshold = 0.4  # Lower threshold if we've been accurate
        elif accuracy_stats and accuracy_stats.get('overall_accuracy', 0) < 0.4:
            base_threshold = 0.6  # Higher threshold if we've been inaccurate
        
        should_trade = (
            prediction['confidence'] >= base_threshold and
            prediction['direction'] != "NEUTRAL" and
            prediction['magnitude'] >= 0.3
        )
        
        # Determine symbols to trade
        symbols = ['SPY']  # Default
        if 'China' in statement.entities:
            symbols.extend(['FXI', 'BABA'])
        if any(e in ['AAPL', 'AMZN', 'GOOGL', 'MSFT', 'META', 'TSLA', 'NVDA'] for e in statement.entities):
            symbols.extend([e for e in statement.entities if e in ['AAPL', 'AMZN', 'GOOGL', 'MSFT', 'META', 'TSLA', 'NVDA']])
        
        # Position sizing based on confidence
        if prediction['confidence'] >= 0.7:
            position_size = 0.03  # 3% for high confidence
        elif prediction['confidence'] >= 0.5:
            position_size = 0.02  # 2% for medium confidence
        else:
            position_size = 0.01  # 1% for low confidence
        
        # Stop loss and target based on historical volatility
        if topic_corr:
            stop_loss = max(0.5, topic_corr.std_spy_change_1hr * 1.5)
            target = max(1.0, abs(topic_corr.avg_spy_change_1hr) * 2)
        else:
            stop_loss = 0.5
            target = 1.0
        
        signal = TrumpSignal(
            timestamp=datetime.now(),
            statement=statement,
            direction=prediction['direction'],
            magnitude=prediction['magnitude'],
            confidence=prediction['confidence'],
            similar_statements=similar,
            topic_correlation=topic_corr,
            agent_votes={self.agent_name: prediction['direction']},
            agent_confidences={self.agent_name: prediction['confidence']},
            should_trade=should_trade,
            suggested_symbols=list(set(symbols)),
            suggested_position_size=position_size,
            stop_loss_pct=round(stop_loss, 2),
            target_pct=round(target, 2),
            reasoning=prediction['reasoning'],
            data_points_used=len(similar) + (1 if topic_corr else 0)
        )
        
        # Record prediction for accuracy tracking
        pred_record = Prediction(
            id=f"pred_{statement.id}_{datetime.now().timestamp()}",
            statement_id=statement.id,
            timestamp=datetime.now(),
            predicted_direction=prediction['direction'],
            predicted_magnitude=prediction['magnitude'],
            confidence=prediction['confidence'],
            reasoning=prediction['reasoning'],
            contributing_agents=[self.agent_name],
            similar_statements_used=[s.statement.id for s in similar]
        )
        self.db.save_prediction(pred_record)
        
        return signal
    
    def get_learning_summary(self) -> Dict[str, Any]:
        """Get summary of what the agent has learned"""
        correlations = self.db.get_all_correlations()
        accuracy = self.db.get_prediction_accuracy()
        stats = self.db.get_stats()
        
        # Top movers by topic
        sorted_corr = sorted(correlations, key=lambda x: abs(x.avg_spy_change_1hr), reverse=True)
        
        top_movers = []
        for corr in sorted_corr[:5]:
            top_movers.append({
                'topic': corr.topic,
                'avg_impact': f"{corr.avg_spy_change_1hr:+.2f}%",
                'direction': 'BEARISH' if corr.avg_spy_change_1hr < 0 else 'BULLISH',
                'sample_size': corr.statement_count
            })
        
        return {
            'total_statements_learned': stats.get('statements_with_market_data', 0),
            'topics_tracked': len(correlations),
            'prediction_accuracy': accuracy.get('overall_accuracy', 0),
            'total_predictions': accuracy.get('total_predictions', 0),
            'top_moving_topics': top_movers,
            'accuracy_by_confidence': accuracy.get('by_confidence', {})
        }
    
    def print_learning_report(self):
        """Print human-readable learning report"""
        summary = self.get_learning_summary()
        
        print("\n" + "=" * 70)
        print("🧠 TRUMP PATTERN AGENT - LEARNING REPORT")
        print("=" * 70)
        
        print(f"\n📊 DATA SUMMARY:")
        print(f"   Statements with market data: {summary['total_statements_learned']}")
        print(f"   Topics tracked: {summary['topics_tracked']}")
        print(f"   Total predictions made: {summary['total_predictions']}")
        
        if summary['prediction_accuracy'] > 0:
            print(f"\n📈 PREDICTION ACCURACY:")
            print(f"   Overall: {summary['prediction_accuracy']:.1%}")
            
            by_conf = summary.get('accuracy_by_confidence', {})
            for level in ['high', 'medium', 'low']:
                if level in by_conf:
                    data = by_conf[level]
                    print(f"   {level.capitalize()} confidence: {data['accuracy']:.1%} ({data['correct']}/{data['total']})")
        
        print(f"\n🔥 TOP MARKET-MOVING TOPICS:")
        for i, topic in enumerate(summary.get('top_moving_topics', [])[:5], 1):
            print(f"   {i}. {topic['topic']}: {topic['avg_impact']} avg ({topic['direction']}, n={topic['sample_size']})")
        
        print("\n" + "=" * 70)


if __name__ == "__main__":
    # Test the pattern agent
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    print("=" * 60)
    print("🧠 TRUMP PATTERN AGENT - TEST")
    print("=" * 60)
    
    db = TrumpDatabase()
    agent = TrumpPatternAgent(db=db)
    
    # Update correlations
    correlations = agent.update_topic_correlations()
    
    # Print learning report
    agent.print_learning_report()
    
    # Test prediction on a sample statement
    test_stmt = TrumpStatement(
        id="test_001",
        timestamp=datetime.now(),
        source="test",
        raw_text="Trump threatens 25% tariffs on China",
        topics=["tariff", "china"],
        entities=["China"]
    )
    
    print("\n🔮 TEST PREDICTION:")
    prediction = agent.predict_impact(test_stmt)
    print(f"   Direction: {prediction['direction']}")
    print(f"   Magnitude: {prediction['magnitude']:.2f}%")
    print(f"   Confidence: {prediction['confidence']:.0%}")
    print(f"   Reasoning: {prediction['reasoning']}")




