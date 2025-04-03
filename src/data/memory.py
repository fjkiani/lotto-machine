import os
import json
import logging
import sqlite3
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class AnalysisMemory:
    """
    Memory system for storing and retrieving historical analyses
    to provide context for future analyses.
    """
    
    def __init__(self, db_path: str = "memory.db"):
        """
        Initialize the memory system
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._initialize_db()
    
    def _initialize_db(self) -> None:
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create analyses table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            ticker TEXT,
            current_price REAL,
            analysis_type TEXT,
            market_sentiment TEXT,
            recommendation TEXT,
            risk_level TEXT,
            analysis_data TEXT,
            feedback_data TEXT,
            learning_points TEXT
        )
        ''')
        
        # Create price_history table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id INTEGER,
            timestamp TEXT,
            price REAL,
            FOREIGN KEY (analysis_id) REFERENCES analyses(id)
        )
        ''')
        
        # Create user_feedback table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id INTEGER,
            timestamp TEXT,
            feedback_type TEXT,
            feedback_text TEXT,
            FOREIGN KEY (analysis_id) REFERENCES analyses(id)
        )
        ''')
        
        # Create technical_indicators table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS technical_indicators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            timestamp TEXT,
            indicator_name TEXT,
            indicator_category TEXT,
            indicator_values TEXT,
            indicator_signals TEXT
        )
        ''')
        
        # Create indicator_performance table to track prediction accuracy
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS indicator_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            indicator_id INTEGER,
            prediction_timestamp TEXT,
            prediction_type TEXT,
            prediction_value TEXT,
            actual_outcome TEXT,
            accuracy_score REAL,
            verification_timestamp TEXT,
            FOREIGN KEY (indicator_id) REFERENCES technical_indicators(id)
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def store_analysis(self, 
                      ticker: str, 
                      current_price: float,
                      analysis_type: str,
                      analysis_data: Dict,
                      feedback_data: Optional[Dict] = None,
                      learning_points: Optional[List[str]] = None) -> int:
        """
        Store an analysis in the memory database
        
        Args:
            ticker: Ticker symbol
            current_price: Current price at time of analysis
            analysis_type: Type of analysis (basic, comprehensive, etc.)
            analysis_data: Full analysis data
            feedback_data: Feedback loop data if available
            learning_points: Learning points if available
            
        Returns:
            ID of the stored analysis
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        
        # Extract key information from analysis data
        market_sentiment = analysis_data.get('market_sentiment', 'neutral')
        recommendation = analysis_data.get('recommendation', 'hold')
        risk_level = analysis_data.get('risk_level', 'medium')
        
        # Convert dictionaries to JSON strings
        analysis_json = json.dumps(analysis_data)
        feedback_json = json.dumps(feedback_data) if feedback_data else None
        learning_points_json = json.dumps(learning_points) if learning_points else None
        
        cursor.execute('''
        INSERT INTO analyses 
        (timestamp, ticker, current_price, analysis_type, market_sentiment, 
         recommendation, risk_level, analysis_data, feedback_data, learning_points)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, ticker, current_price, analysis_type, market_sentiment,
              recommendation, risk_level, analysis_json, feedback_json, learning_points_json))
        
        analysis_id = cursor.lastrowid
        
        # Store initial price history
        cursor.execute('''
        INSERT INTO price_history (analysis_id, timestamp, price)
        VALUES (?, ?, ?)
        ''', (analysis_id, timestamp, current_price))
        
        conn.commit()
        conn.close()
        
        return analysis_id
    
    def store_technical_indicators(self, ticker: str, indicators_data: Dict[str, Dict]) -> None:
        """
        Store technical indicator values in the database
        
        Args:
            ticker: Ticker symbol
            indicators_data: Dictionary of indicator data
                {
                    "indicator_name": {
                        "category": "trend|momentum|volume|volatility",
                        "values": {...},  # Latest calculated values
                        "signals": {...}  # Latest signals
                    },
                    ...
                }
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        
        for indicator_name, data in indicators_data.items():
            category = data.get('category', 'unknown')
            values = json.dumps(data.get('values', {}))
            signals = json.dumps(data.get('signals', {}))
            
            cursor.execute('''
            INSERT INTO technical_indicators
            (ticker, timestamp, indicator_name, indicator_category, indicator_values, indicator_signals)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (ticker, timestamp, indicator_name, category, values, signals))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Stored technical indicators for {ticker}: {list(indicators_data.keys())}")
    
    def store_indicator_performance(self, indicator_id: int, prediction_type: str, 
                                   prediction_value: str, actual_outcome: str, 
                                   accuracy_score: float) -> None:
        """
        Store the performance of an indicator prediction
        
        Args:
            indicator_id: ID of the technical indicator
            prediction_type: Type of prediction (e.g., "price_direction", "support_level")
            prediction_value: The predicted value
            actual_outcome: The actual outcome
            accuracy_score: Score representing prediction accuracy (0.0-1.0)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        prediction_timestamp = datetime.now().isoformat()
        
        cursor.execute('''
        INSERT INTO indicator_performance
        (indicator_id, prediction_timestamp, prediction_type, prediction_value, 
         actual_outcome, accuracy_score, verification_timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (indicator_id, prediction_timestamp, prediction_type, prediction_value,
              actual_outcome, accuracy_score, prediction_timestamp))
        
        conn.commit()
        conn.close()
    
    def get_technical_indicators_history(self, ticker: str, indicator_name: Optional[str] = None, 
                                        limit: int = 10) -> List[Dict]:
        """
        Get historical technical indicator values for a ticker
        
        Args:
            ticker: Ticker symbol
            indicator_name: Optional name of specific indicator to retrieve
            limit: Maximum number of records to retrieve
            
        Returns:
            List of indicator records
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if indicator_name:
            cursor.execute('''
            SELECT * FROM technical_indicators
            WHERE ticker = ? AND indicator_name = ?
            ORDER BY timestamp DESC
            LIMIT ?
            ''', (ticker, indicator_name, limit))
        else:
            cursor.execute('''
            SELECT * FROM technical_indicators
            WHERE ticker = ?
            ORDER BY timestamp DESC
            LIMIT ?
            ''', (ticker, limit))
        
        rows = cursor.fetchall()
        
        results = []
        for row in rows:
            result = dict(row)
            # Parse JSON strings
            result['indicator_values'] = json.loads(result['indicator_values'])
            result['indicator_signals'] = json.loads(result['indicator_signals'])
            results.append(result)
        
        conn.close()
        
        return results
    
    def get_indicator_performance_metrics(self, ticker: str, indicator_name: Optional[str] = None) -> Dict:
        """
        Get performance metrics for indicators
        
        Args:
            ticker: Ticker symbol
            indicator_name: Optional name of specific indicator
            
        Returns:
            Dictionary with performance metrics
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Join technical_indicators and indicator_performance tables
        if indicator_name:
            cursor.execute('''
            SELECT ti.indicator_name, ip.prediction_type, 
                   AVG(ip.accuracy_score) as avg_accuracy,
                   COUNT(ip.id) as prediction_count
            FROM technical_indicators ti
            JOIN indicator_performance ip ON ti.id = ip.indicator_id
            WHERE ti.ticker = ? AND ti.indicator_name = ?
            GROUP BY ti.indicator_name, ip.prediction_type
            ''', (ticker, indicator_name))
        else:
            cursor.execute('''
            SELECT ti.indicator_name, ip.prediction_type, 
                   AVG(ip.accuracy_score) as avg_accuracy,
                   COUNT(ip.id) as prediction_count
            FROM technical_indicators ti
            JOIN indicator_performance ip ON ti.id = ip.indicator_id
            WHERE ti.ticker = ?
            GROUP BY ti.indicator_name, ip.prediction_type
            ''', (ticker,))
        
        rows = cursor.fetchall()
        
        metrics = {}
        for row in rows:
            indicator = row['indicator_name']
            if indicator not in metrics:
                metrics[indicator] = {}
            
            metrics[indicator][row['prediction_type']] = {
                'avg_accuracy': row['avg_accuracy'],
                'prediction_count': row['prediction_count']
            }
        
        conn.close()
        
        return metrics
    
    def generate_technical_context(self, ticker: str) -> str:
        """
        Generate context string with technical indicator history
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Context string for LLM prompt
        """
        # Get recent indicator history
        indicators_history = self.get_technical_indicators_history(ticker, limit=5)
        
        # Get performance metrics
        performance_metrics = self.get_indicator_performance_metrics(ticker)
        
        if not indicators_history:
            return "No historical technical indicator data available."
        
        # Format the context
        context = f"Historical Technical Indicators for {ticker}:\n\n"
        
        # Group by timestamp
        by_timestamp = {}
        for record in indicators_history:
            timestamp = record['timestamp']
            if timestamp not in by_timestamp:
                by_timestamp[timestamp] = []
            by_timestamp[timestamp].append(record)
        
        # Format each timestamp group
        for timestamp, records in by_timestamp.items():
            dt = datetime.fromisoformat(timestamp)
            formatted_date = dt.strftime("%Y-%m-%d %H:%M:%S")
            context += f"Date: {formatted_date}\n"
            
            for record in records:
                indicator_name = record['indicator_name']
                category = record['indicator_category']
                values = record['indicator_values']
                signals = record['indicator_signals']
                
                context += f"  {indicator_name} ({category}):\n"
                
                # Format values (show only the most recent values)
                if isinstance(values, dict):
                    for k, v in values.items():
                        if isinstance(v, (list, dict)):
                            # For complex values, just show the last few items
                            if isinstance(v, list) and len(v) > 0:
                                context += f"    {k}: {v[-3:]} (last 3 values)\n"
                            elif isinstance(v, dict) and len(v) > 0:
                                context += f"    {k}: {list(v.items())[-3:]} (last 3 items)\n"
                        else:
                            context += f"    {k}: {v}\n"
                
                # Format signals
                if signals:
                    context += f"    Signals: {signals}\n"
                
                # Add performance metrics if available
                if indicator_name in performance_metrics:
                    context += "    Performance:\n"
                    for pred_type, metrics in performance_metrics[indicator_name].items():
                        accuracy = metrics['avg_accuracy']
                        count = metrics['prediction_count']
                        context += f"      {pred_type}: {accuracy:.2f} accuracy over {count} predictions\n"
            
            context += "\n"
        
        return context
    
    def store_price_update(self, analysis_id: int, price: float) -> None:
        """
        Store a price update for a previous analysis
        
        Args:
            analysis_id: ID of the analysis
            price: Current price
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        
        cursor.execute('''
        INSERT INTO price_history (analysis_id, timestamp, price)
        VALUES (?, ?, ?)
        ''', (analysis_id, timestamp, price))
        
        conn.commit()
        conn.close()
    
    def store_user_feedback(self, analysis_id: int, feedback_type: str, feedback_text: str) -> None:
        """
        Store user feedback for a previous analysis
        
        Args:
            analysis_id: ID of the analysis
            feedback_type: Type of feedback (accuracy, usefulness, etc.)
            feedback_text: Text of the feedback
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        
        cursor.execute('''
        INSERT INTO user_feedback (analysis_id, timestamp, feedback_type, feedback_text)
        VALUES (?, ?, ?, ?)
        ''', (analysis_id, timestamp, feedback_type, feedback_text))
        
        conn.commit()
        conn.close()
    
    def get_ticker_history(self, ticker: str, limit: int = 5) -> List[Dict]:
        """
        Get historical analyses for a ticker
        
        Args:
            ticker: Ticker symbol
            limit: Maximum number of analyses to return
            
        Returns:
            List of historical analyses
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT * FROM analyses
        WHERE ticker = ?
        ORDER BY timestamp DESC
        LIMIT ?
        ''', (ticker, limit))
        
        rows = cursor.fetchall()
        
        analyses = []
        for row in rows:
            analysis = dict(row)
            
            # Parse JSON fields
            if analysis["analysis_data"]:
                analysis["analysis_data"] = json.loads(analysis["analysis_data"])
            if analysis["feedback_data"]:
                analysis["feedback_data"] = json.loads(analysis["feedback_data"])
            if analysis["learning_points"]:
                analysis["learning_points"] = json.loads(analysis["learning_points"])
            
            # Get price history
            cursor.execute('''
            SELECT timestamp, price FROM price_history
            WHERE analysis_id = ?
            ORDER BY timestamp ASC
            ''', (analysis["id"],))
            
            price_history = [dict(r) for r in cursor.fetchall()]
            analysis["price_history"] = price_history
            
            # Get user feedback
            cursor.execute('''
            SELECT timestamp, feedback_type, feedback_text FROM user_feedback
            WHERE analysis_id = ?
            ORDER BY timestamp ASC
            ''', (analysis["id"],))
            
            user_feedback = [dict(r) for r in cursor.fetchall()]
            analysis["user_feedback"] = user_feedback
            
            analyses.append(analysis)
        
        conn.close()
        return analyses
    
    def get_similar_market_conditions(self, 
                                     ticker: str, 
                                     current_price: float,
                                     price_change_pct: float,
                                     market_sentiment: str,
                                     limit: int = 3) -> List[Dict]:
        """
        Find analyses with similar market conditions
        
        Args:
            ticker: Ticker symbol
            current_price: Current price
            price_change_pct: Price change percentage
            market_sentiment: Current market sentiment
            limit: Maximum number of analyses to return
            
        Returns:
            List of similar analyses
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # This is a simplified approach - in a real system, we would use more
        # sophisticated similarity metrics
        cursor.execute('''
        SELECT * FROM analyses
        WHERE ticker = ? AND market_sentiment = ?
        ORDER BY ABS(current_price - ?) ASC
        LIMIT ?
        ''', (ticker, market_sentiment, current_price, limit))
        
        rows = cursor.fetchall()
        
        analyses = []
        for row in rows:
            analysis = dict(row)
            
            # Parse JSON fields
            if analysis["analysis_data"]:
                analysis["analysis_data"] = json.loads(analysis["analysis_data"])
            if analysis["feedback_data"]:
                analysis["feedback_data"] = json.loads(analysis["feedback_data"])
            if analysis["learning_points"]:
                analysis["learning_points"] = json.loads(analysis["learning_points"])
            
            analyses.append(analysis)
        
        conn.close()
        return analyses
    
    def get_recommendation_accuracy(self, ticker: str) -> Dict[str, float]:
        """
        Calculate the accuracy of past recommendations
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Dictionary with accuracy metrics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all analyses with price updates
        cursor.execute('''
        SELECT a.id, a.recommendation, a.current_price, 
               MAX(p.price) as latest_price
        FROM analyses a
        JOIN price_history p ON a.id = p.analysis_id
        WHERE a.ticker = ?
        GROUP BY a.id
        ''', (ticker,))
        
        rows = cursor.fetchall()
        
        # Calculate accuracy
        correct = 0
        total = 0
        
        for row in rows:
            analysis_id, recommendation, initial_price, latest_price = row
            price_change_pct = ((latest_price - initial_price) / initial_price) * 100
            
            # Simple accuracy metric
            if (recommendation == "buy" and price_change_pct > 0) or \
               (recommendation == "sell" and price_change_pct < 0) or \
               (recommendation == "hold" and abs(price_change_pct) < 5):
                correct += 1
            
            total += 1
        
        conn.close()
        
        accuracy = correct / total if total > 0 else 0
        return {
            "accuracy": accuracy,
            "correct": correct,
            "total": total
        }
    
    def generate_memory_context(self, ticker: str, current_price: float, price_change_pct: float) -> str:
        """
        Generate a context string from memory for the LLM
        
        Args:
            ticker: Ticker symbol
            current_price: Current price
            price_change_pct: Price change percentage
            
        Returns:
            Context string for the LLM
        """
        # Get historical analyses
        history = self.get_ticker_history(ticker, limit=3)
        
        # Get accuracy metrics
        accuracy = self.get_recommendation_accuracy(ticker)
        
        # Build context string
        context = f"### Historical Analysis Context for {ticker} ###\n\n"
        
        if history:
            context += "Previous analyses:\n"
            for i, analysis in enumerate(history, 1):
                timestamp = datetime.fromisoformat(analysis["timestamp"]).strftime("%Y-%m-%d")
                context += f"{i}. Analysis from {timestamp}:\n"
                context += f"   - Price: ${analysis['current_price']:.2f}\n"
                context += f"   - Sentiment: {analysis['market_sentiment']}\n"
                context += f"   - Recommendation: {analysis['recommendation']}\n"
                context += f"   - Risk Level: {analysis['risk_level']}\n"
                
                # Add price history if available
                if analysis.get("price_history"):
                    latest = analysis["price_history"][-1]
                    latest_price = latest["price"]
                    latest_date = datetime.fromisoformat(latest["timestamp"]).strftime("%Y-%m-%d")
                    price_change = ((latest_price - analysis['current_price']) / analysis['current_price']) * 100
                    context += f"   - Price on {latest_date}: ${latest_price:.2f} ({price_change:.1f}%)\n"
                
                # Add key learning points
                if analysis.get("learning_points"):
                    context += "   - Key learning points:\n"
                    for point in analysis["learning_points"][:2]:  # Limit to 2 points
                        context += f"     * {point}\n"
                
                context += "\n"
        
        # Add accuracy metrics
        if accuracy["total"] > 0:
            context += f"Recommendation accuracy: {accuracy['accuracy']*100:.1f}% ({accuracy['correct']}/{accuracy['total']} correct)\n\n"
        
        # Add current context
        context += f"Current price: ${current_price:.2f} ({price_change_pct:.1f}% change)\n"
        
        return context 