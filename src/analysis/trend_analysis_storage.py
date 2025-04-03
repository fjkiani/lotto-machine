"""
Trend Analysis Storage Module

This module provides functionality to store and retrieve trend analysis data
for historical comparison and LLM analysis.
"""

import logging
import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any

# Set up logging
logger = logging.getLogger(__name__)

class TrendAnalysisStorage:
    """
    Class for storing and retrieving trend analysis data
    """
    
    def __init__(self, db_path: str = "memory.db"):
        """
        Initialize the trend analysis storage
        
        Args:
            db_path: Path to the memory database file
        """
        self.db_path = db_path
        self._initialize_db()
    
    def _initialize_db(self) -> None:
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create trend_analysis table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trend_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT,
            timestamp TEXT,
            primary_trend TEXT,
            trend_strength REAL,
            trend_duration TEXT,
            rsi_condition TEXT,
            rsi_value REAL,
            macd_signal TEXT,
            macd_strength REAL,
            bollinger_position TEXT,
            bollinger_bandwidth REAL,
            bollinger_squeeze TEXT,
            support_levels TEXT,
            resistance_levels TEXT,
            support_confidence REAL,
            resistance_confidence REAL,
            short_term_bullish_target REAL,
            short_term_bearish_target REAL,
            short_term_confidence REAL,
            short_term_timeframe TEXT,
            medium_term_bullish_target REAL,
            medium_term_bearish_target REAL,
            medium_term_confidence REAL,
            medium_term_timeframe TEXT,
            stop_loss REAL,
            risk_reward_ratio REAL,
            volatility_risk TEXT,
            risk_factors TEXT,
            analysis_summary TEXT,
            overall_confidence REAL,
            raw_analysis TEXT
        )
        ''')
        
        # Create trend_prediction_accuracy table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trend_prediction_accuracy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trend_analysis_id INTEGER,
            prediction_type TEXT,
            prediction_value TEXT,
            target_price REAL,
            actual_price REAL,
            verification_date TEXT,
            was_correct INTEGER,
            accuracy_score REAL,
            FOREIGN KEY (trend_analysis_id) REFERENCES trend_analysis(id)
        )
        ''')
        
        conn.commit()
        conn.close()
    
    def store_trend_analysis(self, ticker: str, analysis_data: Dict[str, Any]) -> int:
        """
        Store trend analysis data in the database
        
        Args:
            ticker: Ticker symbol
            analysis_data: Dictionary containing trend analysis data
            
        Returns:
            ID of the stored analysis
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        
        # Extract data from the analysis
        primary_trend = analysis_data.get('primary_trend', 'UNKNOWN')
        trend_strength = analysis_data.get('trend_strength', 0.0)
        trend_duration = analysis_data.get('trend_duration', 'unknown')
        
        # RSI data
        rsi_condition = analysis_data.get('rsi_condition', 'UNKNOWN')
        rsi_value = analysis_data.get('rsi_value', 0.0)
        
        # MACD data
        macd_signal = analysis_data.get('macd_signal', 'UNKNOWN')
        macd_strength = analysis_data.get('macd_strength', 0.0)
        
        # Bollinger Bands data
        bollinger_position = analysis_data.get('bollinger_position', 'UNKNOWN')
        bollinger_bandwidth = analysis_data.get('bollinger_bandwidth', 0.0)
        bollinger_squeeze = analysis_data.get('bollinger_squeeze', 'No')
        
        # Support and resistance levels
        support_levels = json.dumps(analysis_data.get('support_levels', []))
        resistance_levels = json.dumps(analysis_data.get('resistance_levels', []))
        support_confidence = analysis_data.get('support_confidence', 0.0)
        resistance_confidence = analysis_data.get('resistance_confidence', 0.0)
        
        # Price targets
        short_term_bullish_target = analysis_data.get('short_term_bullish_target', 0.0)
        short_term_bearish_target = analysis_data.get('short_term_bearish_target', 0.0)
        short_term_confidence = analysis_data.get('short_term_confidence', 0.0)
        short_term_timeframe = analysis_data.get('short_term_timeframe', 'unknown')
        
        medium_term_bullish_target = analysis_data.get('medium_term_bullish_target', 0.0)
        medium_term_bearish_target = analysis_data.get('medium_term_bearish_target', 0.0)
        medium_term_confidence = analysis_data.get('medium_term_confidence', 0.0)
        medium_term_timeframe = analysis_data.get('medium_term_timeframe', 'unknown')
        
        # Risk assessment
        stop_loss = analysis_data.get('stop_loss', 0.0)
        risk_reward_ratio = analysis_data.get('risk_reward_ratio', 0.0)
        volatility_risk = analysis_data.get('volatility_risk', 'UNKNOWN')
        risk_factors = json.dumps(analysis_data.get('risk_factors', []))
        
        # Summary
        analysis_summary = analysis_data.get('analysis_summary', '')
        overall_confidence = analysis_data.get('overall_confidence', 0.0)
        
        # Store the raw analysis for future reference
        raw_analysis = json.dumps(analysis_data)
        
        cursor.execute('''
        INSERT INTO trend_analysis (
            ticker, timestamp, primary_trend, trend_strength, trend_duration,
            rsi_condition, rsi_value, macd_signal, macd_strength,
            bollinger_position, bollinger_bandwidth, bollinger_squeeze,
            support_levels, resistance_levels, support_confidence, resistance_confidence,
            short_term_bullish_target, short_term_bearish_target, short_term_confidence, short_term_timeframe,
            medium_term_bullish_target, medium_term_bearish_target, medium_term_confidence, medium_term_timeframe,
            stop_loss, risk_reward_ratio, volatility_risk, risk_factors,
            analysis_summary, overall_confidence, raw_analysis
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ticker, timestamp, primary_trend, trend_strength, trend_duration,
            rsi_condition, rsi_value, macd_signal, macd_strength,
            bollinger_position, bollinger_bandwidth, bollinger_squeeze,
            support_levels, resistance_levels, support_confidence, resistance_confidence,
            short_term_bullish_target, short_term_bearish_target, short_term_confidence, short_term_timeframe,
            medium_term_bullish_target, medium_term_bearish_target, medium_term_confidence, medium_term_timeframe,
            stop_loss, risk_reward_ratio, volatility_risk, risk_factors,
            analysis_summary, overall_confidence, raw_analysis
        ))
        
        analysis_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        logger.info(f"Stored trend analysis for {ticker} with ID {analysis_id}")
        
        return analysis_id
    
    def get_trend_analysis_history(self, ticker: str, limit: int = 10) -> List[Dict]:
        """
        Get historical trend analysis data for a ticker
        
        Args:
            ticker: Ticker symbol
            limit: Maximum number of records to retrieve
            
        Returns:
            List of trend analysis records
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT * FROM trend_analysis
        WHERE ticker = ?
        ORDER BY timestamp DESC
        LIMIT ?
        ''', (ticker, limit))
        
        rows = cursor.fetchall()
        
        results = []
        for row in rows:
            result = dict(row)
            
            # Parse JSON fields
            result['support_levels'] = json.loads(result['support_levels'])
            result['resistance_levels'] = json.loads(result['resistance_levels'])
            result['risk_factors'] = json.loads(result['risk_factors'])
            result['raw_analysis'] = json.loads(result['raw_analysis'])
            
            results.append(result)
        
        conn.close()
        
        return results
    
    def store_prediction_verification(self, 
                                     trend_analysis_id: int, 
                                     prediction_type: str,
                                     prediction_value: str,
                                     target_price: float,
                                     actual_price: float,
                                     was_correct: bool,
                                     accuracy_score: float) -> int:
        """
        Store verification of a prediction
        
        Args:
            trend_analysis_id: ID of the trend analysis
            prediction_type: Type of prediction (e.g., "short_term", "medium_term")
            prediction_value: Value of the prediction (e.g., "bullish", "bearish")
            target_price: Target price from the prediction
            actual_price: Actual price at verification time
            was_correct: Whether the prediction was correct
            accuracy_score: Score representing prediction accuracy (0.0-1.0)
            
        Returns:
            ID of the stored verification
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        verification_date = datetime.now().isoformat()
        
        cursor.execute('''
        INSERT INTO trend_prediction_accuracy (
            trend_analysis_id, prediction_type, prediction_value,
            target_price, actual_price, verification_date,
            was_correct, accuracy_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trend_analysis_id, prediction_type, prediction_value,
            target_price, actual_price, verification_date,
            1 if was_correct else 0, accuracy_score
        ))
        
        verification_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        logger.info(f"Stored prediction verification for analysis ID {trend_analysis_id}")
        
        return verification_id
    
    def get_prediction_accuracy(self, ticker: str, prediction_type: Optional[str] = None) -> Dict:
        """
        Get prediction accuracy metrics for a ticker
        
        Args:
            ticker: Ticker symbol
            prediction_type: Optional type of prediction to filter by
            
        Returns:
            Dictionary with accuracy metrics
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if prediction_type:
            cursor.execute('''
            SELECT 
                prediction_type,
                prediction_value,
                COUNT(*) as total_predictions,
                SUM(was_correct) as correct_predictions,
                AVG(accuracy_score) as avg_accuracy
            FROM trend_prediction_accuracy tpa
            JOIN trend_analysis ta ON tpa.trend_analysis_id = ta.id
            WHERE ta.ticker = ? AND tpa.prediction_type = ?
            GROUP BY prediction_type, prediction_value
            ''', (ticker, prediction_type))
        else:
            cursor.execute('''
            SELECT 
                prediction_type,
                prediction_value,
                COUNT(*) as total_predictions,
                SUM(was_correct) as correct_predictions,
                AVG(accuracy_score) as avg_accuracy
            FROM trend_prediction_accuracy tpa
            JOIN trend_analysis ta ON tpa.trend_analysis_id = ta.id
            WHERE ta.ticker = ?
            GROUP BY prediction_type, prediction_value
            ''', (ticker,))
        
        rows = cursor.fetchall()
        
        results = {}
        for row in rows:
            pred_type = row['prediction_type']
            pred_value = row['prediction_value']
            
            if pred_type not in results:
                results[pred_type] = {}
            
            results[pred_type][pred_value] = {
                'total_predictions': row['total_predictions'],
                'correct_predictions': row['correct_predictions'],
                'accuracy': row['avg_accuracy']
            }
        
        # Calculate overall accuracy
        if prediction_type:
            cursor.execute('''
            SELECT 
                COUNT(*) as total_predictions,
                SUM(was_correct) as correct_predictions,
                AVG(accuracy_score) as avg_accuracy
            FROM trend_prediction_accuracy tpa
            JOIN trend_analysis ta ON tpa.trend_analysis_id = ta.id
            WHERE ta.ticker = ? AND tpa.prediction_type = ?
            ''', (ticker, prediction_type))
        else:
            cursor.execute('''
            SELECT 
                COUNT(*) as total_predictions,
                SUM(was_correct) as correct_predictions,
                AVG(accuracy_score) as avg_accuracy
            FROM trend_prediction_accuracy tpa
            JOIN trend_analysis ta ON tpa.trend_analysis_id = ta.id
            WHERE ta.ticker = ?
            ''', (ticker,))
        
        row = cursor.fetchone()
        if row:
            results['overall'] = {
                'total_predictions': row['total_predictions'],
                'correct_predictions': row['correct_predictions'],
                'accuracy': row['avg_accuracy']
            }
        
        conn.close()
        
        return results
    
    def get_indicator_trends(self, ticker: str, indicator: str, limit: int = 10) -> Dict:
        """
        Get historical trends for a specific indicator
        
        Args:
            ticker: Ticker symbol
            indicator: Indicator name (e.g., "rsi_value", "macd_signal")
            limit: Maximum number of records to retrieve
            
        Returns:
            Dictionary with trend data
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if the indicator is a valid column
        cursor.execute(f"PRAGMA table_info(trend_analysis)")
        columns = [row['name'] for row in cursor.fetchall()]
        
        if indicator not in columns:
            conn.close()
            return {'error': f"Invalid indicator: {indicator}"}
        
        # Get the indicator values
        cursor.execute(f'''
        SELECT timestamp, {indicator}
        FROM trend_analysis
        WHERE ticker = ?
        ORDER BY timestamp DESC
        LIMIT ?
        ''', (ticker, limit))
        
        rows = cursor.fetchall()
        
        timestamps = []
        values = []
        
        for row in rows:
            timestamps.append(datetime.fromisoformat(row['timestamp']).strftime("%Y-%m-%d %H:%M"))
            values.append(row[indicator])
        
        conn.close()
        
        # Reverse to get chronological order
        timestamps.reverse()
        values.reverse()
        
        return {
            'timestamps': timestamps,
            'values': values
        }
    
    def generate_trend_context(self, ticker: str) -> str:
        """
        Generate context string with trend analysis history
        
        Args:
            ticker: Ticker symbol
            
        Returns:
            Context string for LLM prompt
        """
        # Get recent trend analysis history
        history = self.get_trend_analysis_history(ticker, limit=5)
        
        if not history:
            return "No historical trend analysis data available."
        
        # Get prediction accuracy
        accuracy = self.get_prediction_accuracy(ticker)
        
        # Format the context
        context = f"Historical Trend Analysis for {ticker}:\n\n"
        
        for i, analysis in enumerate(history):
            dt = datetime.fromisoformat(analysis['timestamp'])
            formatted_date = dt.strftime("%Y-%m-%d %H:%M:%S")
            
            context += f"Analysis {i+1} ({formatted_date}):\n"
            context += f"  Primary Trend: {analysis['primary_trend']} (Strength: {analysis['trend_strength']}%, Duration: {analysis['trend_duration']})\n"
            context += f"  RSI: {analysis['rsi_value']} ({analysis['rsi_condition']})\n"
            context += f"  MACD: {analysis['macd_signal']} (Strength: {analysis['macd_strength']}%)\n"
            context += f"  Bollinger Bands: Position: {analysis['bollinger_position']}, Bandwidth: {analysis['bollinger_bandwidth']}, Squeeze: {analysis['bollinger_squeeze']}\n"
            
            # Support and resistance
            context += "  Support Levels:\n"
            for level in analysis['support_levels']:
                context += f"    - ${level}\n"
            
            context += "  Resistance Levels:\n"
            for level in analysis['resistance_levels']:
                context += f"    - ${level}\n"
            
            # Price targets
            context += f"  Short-Term Targets: Bullish: ${analysis['short_term_bullish_target']}, Bearish: ${analysis['short_term_bearish_target']} (Confidence: {analysis['short_term_confidence']}%, Timeframe: {analysis['short_term_timeframe']})\n"
            context += f"  Medium-Term Targets: Bullish: ${analysis['medium_term_bullish_target']}, Bearish: ${analysis['medium_term_bearish_target']} (Confidence: {analysis['medium_term_confidence']}%, Timeframe: {analysis['medium_term_timeframe']})\n"
            
            # Risk assessment
            context += f"  Risk Assessment: Stop Loss: ${analysis['stop_loss']}, Risk/Reward: {analysis['risk_reward_ratio']}, Volatility: {analysis['volatility_risk']}\n"
            
            context += "\n"
        
        # Add prediction accuracy if available
        if 'overall' in accuracy:
            overall = accuracy['overall']
            accuracy_value = overall.get('accuracy', 0)
            correct_predictions = overall.get('correct_predictions', 0)
            total_predictions = overall.get('total_predictions', 0)
            
            if accuracy_value is not None and total_predictions > 0:
                context += f"Prediction Accuracy Summary:\n"
                context += f"  Overall: {accuracy_value*100:.1f}% accuracy ({correct_predictions}/{total_predictions} correct)\n"
                
                for pred_type, values in accuracy.items():
                    if pred_type != 'overall':
                        context += f"  {pred_type.replace('_', ' ').title()} Predictions:\n"
                        for pred_value, metrics in values.items():
                            accuracy_value = metrics.get('accuracy', 0)
                            correct_predictions = metrics.get('correct_predictions', 0)
                            total_predictions = metrics.get('total_predictions', 0)
                            
                            if accuracy_value is not None and total_predictions > 0:
                                context += f"    {pred_value}: {accuracy_value*100:.1f}% accuracy ({correct_predictions}/{total_predictions} correct)\n"
        
        return context
    
    def parse_trend_analysis_from_text(self, text: str) -> Dict[str, Any]:
        """
        Parse trend analysis data from text format
        
        Args:
            text: Text containing trend analysis data
            
        Returns:
            Dictionary with parsed trend analysis data
        """
        analysis_data = {}
        
        # Extract primary trend
        if "Primary Trend:" in text:
            trend_line = text.split("Primary Trend:")[1].split("\n")[0].strip()
            analysis_data['primary_trend'] = trend_line
        
        # Extract trend strength
        if "Trend Strength" in text and "%" in text:
            strength_line = text.split("Trend Strength")[1].split("%")[0].strip()
            try:
                analysis_data['trend_strength'] = float(strength_line)
            except ValueError:
                pass
        
        # Extract trend duration
        if "Duration:" in text:
            duration_line = text.split("Duration:")[1].split("\n")[0].strip()
            analysis_data['trend_duration'] = duration_line
        
        # Extract support and resistance levels
        support_levels = []
        resistance_levels = []
        
        if "Strong Support Levels:" in text:
            support_section = text.split("Strong Support Levels:")[1].split("Weak Support Levels:")[0]
            for line in support_section.strip().split("\n"):
                if "$" in line:
                    try:
                        level = float(line.strip().replace("$", ""))
                        support_levels.append(level)
                    except ValueError:
                        pass
        
        if "Weak Support Levels:" in text:
            support_section = text.split("Weak Support Levels:")[1].split("Strong Resistance Levels:")[0]
            for line in support_section.strip().split("\n"):
                if "$" in line:
                    try:
                        level = float(line.strip().replace("$", ""))
                        support_levels.append(level)
                    except ValueError:
                        pass
        
        if "Strong Resistance Levels:" in text:
            resistance_section = text.split("Strong Resistance Levels:")[1].split("Weak Resistance Levels:")[0]
            for line in resistance_section.strip().split("\n"):
                if "$" in line:
                    try:
                        level = float(line.strip().replace("$", ""))
                        resistance_levels.append(level)
                    except ValueError:
                        pass
        
        if "Weak Resistance Levels:" in text:
            resistance_section = text.split("Weak Resistance Levels:")[1].split("Support Confidence")[0]
            for line in resistance_section.strip().split("\n"):
                if "$" in line:
                    try:
                        level = float(line.strip().replace("$", ""))
                        resistance_levels.append(level)
                    except ValueError:
                        pass
        
        analysis_data['support_levels'] = support_levels
        analysis_data['resistance_levels'] = resistance_levels
        
        # Extract confidence levels
        if "Support Confidence" in text and "%" in text:
            confidence_line = text.split("Support Confidence")[1].split("%")[0].strip()
            try:
                analysis_data['support_confidence'] = float(confidence_line)
            except ValueError:
                pass
        
        if "Resistance Confidence" in text and "%" in text:
            confidence_line = text.split("Resistance Confidence")[1].split("%")[0].strip()
            try:
                analysis_data['resistance_confidence'] = float(confidence_line)
            except ValueError:
                pass
        
        # Extract RSI data
        if "RSI Analysis" in text and "Condition:" in text:
            condition_line = text.split("Condition:")[1].split("\n")[0].strip()
            analysis_data['rsi_condition'] = condition_line
        
        if "RSI Value" in text:
            value_line = text.split("RSI Value")[1].split("\n")[0].strip()
            try:
                analysis_data['rsi_value'] = float(value_line)
            except ValueError:
                pass
        
        # Extract MACD data
        if "MACD Analysis" in text and "Signal:" in text:
            signal_line = text.split("Signal:")[1].split("\n")[0].strip()
            analysis_data['macd_signal'] = signal_line
        
        if "Signal Strength" in text and "%" in text:
            strength_line = text.split("Signal Strength")[1].split("%")[0].strip()
            try:
                analysis_data['macd_strength'] = float(strength_line)
            except ValueError:
                pass
        
        # Extract Bollinger Bands data
        if "Bollinger Bands Analysis" in text and "Position:" in text:
            position_line = text.split("Position:")[1].split("\n")[0].strip()
            analysis_data['bollinger_position'] = position_line
        
        if "Bandwidth" in text:
            bandwidth_line = text.split("Bandwidth")[1].split("\n")[0].strip()
            try:
                analysis_data['bollinger_bandwidth'] = float(bandwidth_line)
            except ValueError:
                pass
        
        if "Squeeze Potential:" in text:
            squeeze_line = text.split("Squeeze Potential:")[1].split("\n")[0].strip()
            analysis_data['bollinger_squeeze'] = squeeze_line
        
        # Extract price targets
        if "Short Term Targets" in text:
            if "Bullish Target" in text and "$" in text:
                target_line = text.split("Bullish Target")[1].split("\n")[0].strip()
                try:
                    analysis_data['short_term_bullish_target'] = float(target_line.replace("$", ""))
                except ValueError:
                    pass
            
            if "Bearish Target" in text and "$" in text:
                target_line = text.split("Bearish Target")[1].split("\n")[0].strip()
                try:
                    analysis_data['short_term_bearish_target'] = float(target_line.replace("$", ""))
                except ValueError:
                    pass
            
            if "Confidence" in text and "%" in text:
                confidence_section = text.split("Confidence")[1].split("Timeframe:")[0]
                confidence_line = confidence_section.strip().split("%")[0].strip()
                try:
                    analysis_data['short_term_confidence'] = float(confidence_line)
                except ValueError:
                    pass
            
            if "Timeframe:" in text:
                timeframe_line = text.split("Timeframe:")[1].split("Medium Term Targets")[0].strip()
                analysis_data['short_term_timeframe'] = timeframe_line
        
        if "Medium Term Targets" in text:
            if "Bullish Target" in text and "$" in text:
                section = text.split("Medium Term Targets")[1]
                target_line = section.split("Bullish Target")[1].split("\n")[0].strip()
                try:
                    analysis_data['medium_term_bullish_target'] = float(target_line.replace("$", ""))
                except ValueError:
                    pass
            
            if "Bearish Target" in text and "$" in text:
                section = text.split("Medium Term Targets")[1]
                target_line = section.split("Bearish Target")[1].split("\n")[0].strip()
                try:
                    analysis_data['medium_term_bearish_target'] = float(target_line.replace("$", ""))
                except ValueError:
                    pass
            
            if "Confidence" in text and "%" in text:
                section = text.split("Medium Term Targets")[1]
                confidence_section = section.split("Confidence")[1].split("Timeframe:")[0]
                confidence_line = confidence_section.strip().split("%")[0].strip()
                try:
                    analysis_data['medium_term_confidence'] = float(confidence_line)
                except ValueError:
                    pass
            
            if "Timeframe:" in text:
                section = text.split("Medium Term Targets")[1]
                timeframe_line = section.split("Timeframe:")[1].split("Risk Assessment")[0].strip()
                analysis_data['medium_term_timeframe'] = timeframe_line
        
        # Extract risk assessment
        if "Optimal Stop Loss" in text and "$" in text:
            stop_loss_line = text.split("Optimal Stop Loss")[1].split("\n")[0].strip()
            try:
                analysis_data['stop_loss'] = float(stop_loss_line.replace("$", ""))
            except ValueError:
                pass
        
        if "Risk/Reward Ratio" in text:
            ratio_line = text.split("Risk/Reward Ratio")[1].split("\n")[0].strip()
            try:
                analysis_data['risk_reward_ratio'] = float(ratio_line)
            except ValueError:
                pass
        
        if "Volatility Risk:" in text:
            risk_line = text.split("Volatility Risk:")[1].split("\n")[0].strip()
            analysis_data['volatility_risk'] = risk_line
        
        # Extract risk factors
        risk_factors = []
        if "Key Risk Factors:" in text:
            factors_section = text.split("Key Risk Factors:")[1].split("Analysis Summary")[0]
            for line in factors_section.strip().split("\n"):
                if line.strip():
                    risk_factors.append(line.strip())
        
        analysis_data['risk_factors'] = risk_factors
        
        # Extract analysis summary
        if "Analysis Summary" in text:
            summary = text.split("Analysis Summary")[1].split("Overall Confidence Score")[0].strip()
            analysis_data['analysis_summary'] = summary
        
        # Extract overall confidence
        if "Overall Confidence Score" in text and "%" in text:
            confidence_line = text.split("Overall Confidence Score")[1].split("%")[0].strip()
            try:
                analysis_data['overall_confidence'] = float(confidence_line)
            except ValueError:
                pass
        
        return analysis_data 