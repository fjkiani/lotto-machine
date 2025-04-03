"""
Technical Indicators Module

This module provides a comprehensive collection of technical indicators for financial analysis.
It includes trend, momentum, volume, and volatility indicators with a flexible, extensible architecture.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union, Tuple
import logging

# Set up logging
logger = logging.getLogger(__name__)

class Indicator:
    """Base class for all technical indicators"""
    
    def __init__(self, name: str, category: str):
        """
        Initialize the indicator
        
        Args:
            name: Name of the indicator
            category: Category of the indicator (trend, momentum, volume, volatility)
        """
        self.name = name
        self.category = category
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate the indicator values
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with indicator values added
        """
        raise NotImplementedError("Subclasses must implement calculate()")
    
    def get_signals(self, df: pd.DataFrame) -> Dict:
        """
        Get trading signals based on the indicator
        
        Args:
            df: DataFrame with indicator values
            
        Returns:
            Dictionary with signal information
        """
        raise NotImplementedError("Subclasses must implement get_signals()")
    
    def get_visualization_config(self) -> Dict:
        """
        Get configuration for visualization
        
        Returns:
            Dictionary with visualization configuration
        """
        raise NotImplementedError("Subclasses must implement get_visualization_config()")


class MovingAverage(Indicator):
    """Moving Average indicator"""
    
    def __init__(self, window: int = 20, column: str = 'Close'):
        """
        Initialize the Moving Average indicator
        
        Args:
            window: Window size for the moving average
            column: Column to calculate the moving average on
        """
        super().__init__(f"MA{window}", "trend")
        self.window = window
        self.column = column
        self.output_column = f"MA{window}"
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate the moving average
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with moving average added
        """
        try:
            df[self.output_column] = df[self.column].rolling(window=self.window).mean()
            return df
        except Exception as e:
            logger.error(f"Error calculating {self.name}: {str(e)}")
            return df
    
    def get_signals(self, df: pd.DataFrame) -> Dict:
        """
        Get trading signals based on the moving average
        
        Args:
            df: DataFrame with indicator values
            
        Returns:
            Dictionary with signal information
        """
        signals = {
            "crossovers": [],
            "trend": "neutral",
            "strength": 0
        }
        
        try:
            # Check if price is above or below MA
            if df[self.column].iloc[-1] > df[self.output_column].iloc[-1]:
                signals["trend"] = "bullish"
                # Calculate strength based on distance from MA
                signals["strength"] = min(100, int((df[self.column].iloc[-1] / df[self.output_column].iloc[-1] - 1) * 100))
            elif df[self.column].iloc[-1] < df[self.output_column].iloc[-1]:
                signals["trend"] = "bearish"
                # Calculate strength based on distance from MA
                signals["strength"] = min(100, int((1 - df[self.column].iloc[-1] / df[self.output_column].iloc[-1]) * 100))
            
            # Detect crossovers
            for i in range(1, min(10, len(df))):
                if (df[self.column].iloc[-i] > df[self.output_column].iloc[-i] and 
                    df[self.column].iloc[-i-1] < df[self.output_column].iloc[-i-1]):
                    signals["crossovers"].append({
                        "type": "bullish",
                        "date": df.index[-i].strftime("%Y-%m-%d") if hasattr(df.index[-i], 'strftime') else str(df.index[-i]),
                        "price": float(df[self.column].iloc[-i])
                    })
                elif (df[self.column].iloc[-i] < df[self.output_column].iloc[-i] and 
                      df[self.column].iloc[-i-1] > df[self.output_column].iloc[-i-1]):
                    signals["crossovers"].append({
                        "type": "bearish",
                        "date": df.index[-i].strftime("%Y-%m-%d") if hasattr(df.index[-i], 'strftime') else str(df.index[-i]),
                        "price": float(df[self.column].iloc[-i])
                    })
        except Exception as e:
            logger.error(f"Error getting signals for {self.name}: {str(e)}")
        
        return signals
    
    def get_visualization_config(self) -> Dict:
        """
        Get configuration for visualization
        
        Returns:
            Dictionary with visualization configuration
        """
        colors = {
            20: "orange",
            50: "green",
            100: "blue",
            200: "red"
        }
        
        return {
            "type": "line",
            "name": self.name,
            "color": colors.get(self.window, "purple"),
            "width": 1,
            "dash": "solid",
            "opacity": 0.8,
            "subplot": False  # Plot on main price chart
        }


class BollingerBands(Indicator):
    """Bollinger Bands indicator"""
    
    def __init__(self, window: int = 20, num_std: float = 2.0, column: str = 'Close'):
        """
        Initialize the Bollinger Bands indicator
        
        Args:
            window: Window size for the moving average
            num_std: Number of standard deviations for the bands
            column: Column to calculate the bands on
        """
        super().__init__("Bollinger Bands", "volatility")
        self.window = window
        self.num_std = num_std
        self.column = column
        self.ma_column = f"MA{window}"
        self.upper_column = f"Upper_Band"
        self.lower_column = f"Lower_Band"
        self.width_column = f"BB_Width"
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate the Bollinger Bands
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with Bollinger Bands added
        """
        try:
            # Calculate middle band (SMA)
            df[self.ma_column] = df[self.column].rolling(window=self.window).mean()
            
            # Calculate standard deviation
            std = df[self.column].rolling(window=self.window).std()
            
            # Calculate upper and lower bands
            df[self.upper_column] = df[self.ma_column] + (std * self.num_std)
            df[self.lower_column] = df[self.ma_column] - (std * self.num_std)
            
            # Calculate bandwidth
            df[self.width_column] = (df[self.upper_column] - df[self.lower_column]) / df[self.ma_column]
            
            return df
        except Exception as e:
            logger.error(f"Error calculating {self.name}: {str(e)}")
            return df
    
    def get_signals(self, df: pd.DataFrame) -> Dict:
        """
        Get trading signals based on Bollinger Bands
        
        Args:
            df: DataFrame with indicator values
            
        Returns:
            Dictionary with signal information
        """
        signals = {
            "position": "middle",
            "bandwidth": 0,
            "squeeze": False,
            "breakouts": []
        }
        
        try:
            # Determine position within bands
            last_close = df[self.column].iloc[-1]
            upper_band = df[self.upper_column].iloc[-1]
            lower_band = df[self.lower_column].iloc[-1]
            middle_band = df[self.ma_column].iloc[-1]
            
            if last_close > upper_band:
                signals["position"] = "above"
            elif last_close < lower_band:
                signals["position"] = "below"
            else:
                # Calculate relative position within bands (0-100)
                band_range = upper_band - lower_band
                if band_range > 0:
                    position_pct = (last_close - lower_band) / band_range * 100
                    if position_pct < 33:
                        signals["position"] = "lower_third"
                    elif position_pct > 66:
                        signals["position"] = "upper_third"
                    else:
                        signals["position"] = "middle"
            
            # Calculate bandwidth and detect squeeze
            signals["bandwidth"] = float(df[self.width_column].iloc[-1])
            
            # Detect Bollinger Band squeeze (low volatility)
            recent_width = df[self.width_column].iloc[-20:] if len(df) >= 20 else df[self.width_column]
            if signals["bandwidth"] < recent_width.quantile(0.2):
                signals["squeeze"] = True
            
            # Detect breakouts
            for i in range(1, min(10, len(df))):
                # Bullish breakout
                if (df[self.column].iloc[-i] > df[self.upper_column].iloc[-i] and 
                    df[self.column].iloc[-i-1] <= df[self.upper_column].iloc[-i-1]):
                    signals["breakouts"].append({
                        "type": "bullish",
                        "date": df.index[-i].strftime("%Y-%m-%d") if hasattr(df.index[-i], 'strftime') else str(df.index[-i]),
                        "price": float(df[self.column].iloc[-i])
                    })
                # Bearish breakout
                elif (df[self.column].iloc[-i] < df[self.lower_column].iloc[-i] and 
                      df[self.column].iloc[-i-1] >= df[self.lower_column].iloc[-i-1]):
                    signals["breakouts"].append({
                        "type": "bearish",
                        "date": df.index[-i].strftime("%Y-%m-%d") if hasattr(df.index[-i], 'strftime') else str(df.index[-i]),
                        "price": float(df[self.column].iloc[-i])
                    })
        except Exception as e:
            logger.error(f"Error getting signals for {self.name}: {str(e)}")
        
        return signals
    
    def get_visualization_config(self) -> Dict:
        """
        Get configuration for visualization
        
        Returns:
            Dictionary with visualization configuration
        """
        return {
            "type": "bands",
            "name": self.name,
            "middle": {
                "color": "purple",
                "width": 1,
                "dash": "solid"
            },
            "upper": {
                "color": "gray",
                "width": 1,
                "dash": "dash"
            },
            "lower": {
                "color": "gray",
                "width": 1,
                "dash": "dash"
            },
            "fill": True,
            "fill_color": "rgba(200, 200, 200, 0.2)",
            "subplot": False  # Plot on main price chart
        }


class RSI(Indicator):
    """Relative Strength Index indicator"""
    
    def __init__(self, window: int = 14, column: str = 'Close'):
        """
        Initialize the RSI indicator
        
        Args:
            window: Window size for the RSI calculation
            column: Column to calculate the RSI on
        """
        super().__init__("RSI", "momentum")
        self.window = window
        self.column = column
        self.output_column = "RSI"
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate the RSI
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with RSI added
        """
        try:
            delta = df[self.column].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            
            avg_gain = gain.rolling(window=self.window).mean()
            avg_loss = loss.rolling(window=self.window).mean()
            
            rs = avg_gain / avg_loss
            df[self.output_column] = 100 - (100 / (1 + rs))
            
            return df
        except Exception as e:
            logger.error(f"Error calculating {self.name}: {str(e)}")
            return df
    
    def get_signals(self, df: pd.DataFrame) -> Dict:
        """
        Get trading signals based on RSI
        
        Args:
            df: DataFrame with indicator values
            
        Returns:
            Dictionary with signal information
        """
        signals = {
            "value": 0,
            "condition": "neutral",
            "divergences": [],
            "crossovers": []
        }
        
        try:
            last_rsi = df[self.output_column].iloc[-1]
            signals["value"] = float(last_rsi)
            
            # Determine overbought/oversold condition
            if last_rsi >= 70:
                signals["condition"] = "overbought"
            elif last_rsi <= 30:
                signals["condition"] = "oversold"
            else:
                signals["condition"] = "neutral"
            
            # Detect crossovers of 30/70 levels
            for i in range(1, min(10, len(df))):
                # Bullish crossover (crossing above 30)
                if (df[self.output_column].iloc[-i] > 30 and 
                    df[self.output_column].iloc[-i-1] <= 30):
                    signals["crossovers"].append({
                        "type": "bullish",
                        "level": 30,
                        "date": df.index[-i].strftime("%Y-%m-%d") if hasattr(df.index[-i], 'strftime') else str(df.index[-i])
                    })
                # Bearish crossover (crossing below 70)
                elif (df[self.output_column].iloc[-i] < 70 and 
                      df[self.output_column].iloc[-i-1] >= 70):
                    signals["crossovers"].append({
                        "type": "bearish",
                        "level": 70,
                        "date": df.index[-i].strftime("%Y-%m-%d") if hasattr(df.index[-i], 'strftime') else str(df.index[-i])
                    })
            
            # Detect divergences (basic implementation)
            # This is a simplified approach - real divergence detection is more complex
            if len(df) >= 20:
                # Check for bearish divergence (price higher, RSI lower)
                if (df[self.column].iloc[-1] > df[self.column].iloc[-10] and 
                    df[self.output_column].iloc[-1] < df[self.output_column].iloc[-10] and
                    df[self.output_column].iloc[-1] > 70):
                    signals["divergences"].append({
                        "type": "bearish",
                        "start_date": df.index[-10].strftime("%Y-%m-%d") if hasattr(df.index[-10], 'strftime') else str(df.index[-10]),
                        "end_date": df.index[-1].strftime("%Y-%m-%d") if hasattr(df.index[-1], 'strftime') else str(df.index[-1])
                    })
                
                # Check for bullish divergence (price lower, RSI higher)
                if (df[self.column].iloc[-1] < df[self.column].iloc[-10] and 
                    df[self.output_column].iloc[-1] > df[self.output_column].iloc[-10] and
                    df[self.output_column].iloc[-1] < 30):
                    signals["divergences"].append({
                        "type": "bullish",
                        "start_date": df.index[-10].strftime("%Y-%m-%d") if hasattr(df.index[-10], 'strftime') else str(df.index[-10]),
                        "end_date": df.index[-1].strftime("%Y-%m-%d") if hasattr(df.index[-1], 'strftime') else str(df.index[-1])
                    })
        except Exception as e:
            logger.error(f"Error getting signals for {self.name}: {str(e)}")
        
        return signals
    
    def get_visualization_config(self) -> Dict:
        """
        Get configuration for visualization
        
        Returns:
            Dictionary with visualization configuration
        """
        return {
            "type": "line",
            "name": self.name,
            "color": "purple",
            "width": 1.5,
            "dash": "solid",
            "subplot": True,  # Create a separate subplot
            "subplot_config": {
                "title": "RSI",
                "range": [0, 100],
                "height": 0.2,  # 20% of the chart height
                "reference_lines": [
                    {"value": 70, "color": "red", "width": 1, "dash": "dash"},
                    {"value": 30, "color": "green", "width": 1, "dash": "dash"},
                    {"value": 50, "color": "gray", "width": 1, "dash": "dot"}
                ]
            }
        }


class MACD(Indicator):
    """Moving Average Convergence Divergence indicator"""
    
    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9, column: str = 'Close'):
        """
        Initialize the MACD indicator
        
        Args:
            fast_period: Period for the fast EMA
            slow_period: Period for the slow EMA
            signal_period: Period for the signal line
            column: Column to calculate the MACD on
        """
        super().__init__("MACD", "momentum")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.column = column
        self.macd_column = "MACD"
        self.signal_column = "MACD_Signal"
        self.histogram_column = "MACD_Hist"
    
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate the MACD
        
        Args:
            df: DataFrame with OHLCV data
            
        Returns:
            DataFrame with MACD added
        """
        try:
            # Calculate fast and slow EMAs
            fast_ema = df[self.column].ewm(span=self.fast_period, adjust=False).mean()
            slow_ema = df[self.column].ewm(span=self.slow_period, adjust=False).mean()
            
            # Calculate MACD line
            df[self.macd_column] = fast_ema - slow_ema
            
            # Calculate signal line
            df[self.signal_column] = df[self.macd_column].ewm(span=self.signal_period, adjust=False).mean()
            
            # Calculate histogram
            df[self.histogram_column] = df[self.macd_column] - df[self.signal_column]
            
            return df
        except Exception as e:
            logger.error(f"Error calculating {self.name}: {str(e)}")
            return df
    
    def get_signals(self, df: pd.DataFrame) -> Dict:
        """
        Get trading signals based on MACD
        
        Args:
            df: DataFrame with indicator values
            
        Returns:
            Dictionary with signal information
        """
        signals = {
            "macd_value": 0,
            "signal_value": 0,
            "histogram_value": 0,
            "trend": "neutral",
            "strength": 0,
            "crossovers": [],
            "divergences": []
        }
        
        try:
            signals["macd_value"] = float(df[self.macd_column].iloc[-1])
            signals["signal_value"] = float(df[self.signal_column].iloc[-1])
            signals["histogram_value"] = float(df[self.histogram_column].iloc[-1])
            
            # Determine trend
            if signals["macd_value"] > signals["signal_value"]:
                signals["trend"] = "bullish"
                # Calculate strength based on histogram value
                max_hist = df[self.histogram_column].abs().quantile(0.9)
                signals["strength"] = min(100, int(abs(signals["histogram_value"]) / max_hist * 100)) if max_hist > 0 else 50
            elif signals["macd_value"] < signals["signal_value"]:
                signals["trend"] = "bearish"
                # Calculate strength based on histogram value
                max_hist = df[self.histogram_column].abs().quantile(0.9)
                signals["strength"] = min(100, int(abs(signals["histogram_value"]) / max_hist * 100)) if max_hist > 0 else 50
            
            # Detect crossovers
            for i in range(1, min(10, len(df))):
                # Bullish crossover (MACD crosses above signal)
                if (df[self.macd_column].iloc[-i] > df[self.signal_column].iloc[-i] and 
                    df[self.macd_column].iloc[-i-1] <= df[self.signal_column].iloc[-i-1]):
                    signals["crossovers"].append({
                        "type": "bullish",
                        "date": df.index[-i].strftime("%Y-%m-%d") if hasattr(df.index[-i], 'strftime') else str(df.index[-i])
                    })
                # Bearish crossover (MACD crosses below signal)
                elif (df[self.macd_column].iloc[-i] < df[self.signal_column].iloc[-i] and 
                      df[self.macd_column].iloc[-i-1] >= df[self.signal_column].iloc[-i-1]):
                    signals["crossovers"].append({
                        "type": "bearish",
                        "date": df.index[-i].strftime("%Y-%m-%d") if hasattr(df.index[-i], 'strftime') else str(df.index[-i])
                    })
            
            # Detect divergences (basic implementation)
            if len(df) >= 20:
                # Check for bearish divergence (price higher, MACD lower)
                if (df[self.column].iloc[-1] > df[self.column].iloc[-10] and 
                    df[self.macd_column].iloc[-1] < df[self.macd_column].iloc[-10] and
                    df[self.macd_column].iloc[-1] > 0):
                    signals["divergences"].append({
                        "type": "bearish",
                        "start_date": df.index[-10].strftime("%Y-%m-%d") if hasattr(df.index[-10], 'strftime') else str(df.index[-10]),
                        "end_date": df.index[-1].strftime("%Y-%m-%d") if hasattr(df.index[-1], 'strftime') else str(df.index[-1])
                    })
                
                # Check for bullish divergence (price lower, MACD higher)
                if (df[self.column].iloc[-1] < df[self.column].iloc[-10] and 
                    df[self.macd_column].iloc[-1] > df[self.macd_column].iloc[-10] and
                    df[self.macd_column].iloc[-1] < 0):
                    signals["divergences"].append({
                        "type": "bullish",
                        "start_date": df.index[-10].strftime("%Y-%m-%d") if hasattr(df.index[-10], 'strftime') else str(df.index[-10]),
                        "end_date": df.index[-1].strftime("%Y-%m-%d") if hasattr(df.index[-1], 'strftime') else str(df.index[-1])
                    })
        except Exception as e:
            logger.error(f"Error getting signals for {self.name}: {str(e)}")
        
        return signals
    
    def get_visualization_config(self) -> Dict:
        """
        Get configuration for visualization
        
        Returns:
            Dictionary with visualization configuration
        """
        return {
            "type": "macd",
            "name": self.name,
            "macd_line": {
                "color": "blue",
                "width": 1.5,
                "dash": "solid"
            },
            "signal_line": {
                "color": "red",
                "width": 1.5,
                "dash": "solid"
            },
            "histogram": {
                "up_color": "green",
                "down_color": "red",
                "opacity": 0.7
            },
            "subplot": True,  # Create a separate subplot
            "subplot_config": {
                "title": "MACD",
                "height": 0.2,  # 20% of the chart height
                "reference_lines": [
                    {"value": 0, "color": "gray", "width": 1, "dash": "dot"}
                ]
            }
        }


# Factory function to create indicators
def create_indicator(indicator_type: str, **kwargs) -> Indicator:
    """
    Create an indicator instance based on the indicator type
    
    Args:
        indicator_type: Type of indicator to create
        **kwargs: Additional parameters for the indicator
        
    Returns:
        Indicator instance
    """
    indicators = {
        "ma": MovingAverage,
        "bollinger": BollingerBands,
        "rsi": RSI,
        "macd": MACD
    }
    
    indicator_class = indicators.get(indicator_type.lower())
    if indicator_class:
        return indicator_class(**kwargs)
    else:
        raise ValueError(f"Unknown indicator type: {indicator_type}")


# Function to calculate multiple indicators
def calculate_indicators(df: pd.DataFrame, indicators: List[Indicator]) -> pd.DataFrame:
    """
    Calculate multiple indicators on a DataFrame
    
    Args:
        df: DataFrame with OHLCV data
        indicators: List of indicator instances
        
    Returns:
        DataFrame with indicators added
    """
    result_df = df.copy()
    
    for indicator in indicators:
        try:
            result_df = indicator.calculate(result_df)
        except Exception as e:
            logger.error(f"Error calculating {indicator.name}: {str(e)}")
    
    return result_df


# Function to get signals from multiple indicators
def get_all_signals(df: pd.DataFrame, indicators: List[Indicator]) -> Dict:
    """
    Get signals from multiple indicators
    
    Args:
        df: DataFrame with indicator values
        indicators: List of indicator instances
        
    Returns:
        Dictionary with signals from all indicators
    """
    signals = {}
    
    for indicator in indicators:
        try:
            signals[indicator.name] = indicator.get_signals(df)
        except Exception as e:
            logger.error(f"Error getting signals for {indicator.name}: {str(e)}")
            signals[indicator.name] = {"error": str(e)}
    
    return signals


# Function to get visualization configurations for multiple indicators
def get_visualization_configs(indicators: List[Indicator]) -> Dict:
    """
    Get visualization configurations for multiple indicators
    
    Args:
        indicators: List of indicator instances
        
    Returns:
        Dictionary with visualization configurations
    """
    configs = {}
    
    for indicator in indicators:
        try:
            configs[indicator.name] = indicator.get_visualization_config()
        except Exception as e:
            logger.error(f"Error getting visualization config for {indicator.name}: {str(e)}")
            configs[indicator.name] = {"error": str(e)}
    
    return configs 