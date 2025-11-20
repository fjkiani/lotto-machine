import os
import json
import logging
import matplotlib.pyplot as plt
import seaborn as sns
from dotenv import load_dotenv
from prettytable import PrettyTable
from src.data.connectors.yahoo_finance_insights import YahooFinanceInsightsConnector

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Set seaborn style for nicer plots
sns.set_style("whitegrid")

def display_technical_events(insights):
    """Display technical events (short, mid, long term patterns)"""
    print("\n=== TECHNICAL EVENTS ===")
    tech_events = insights.get("technical_events", {})
    if not tech_events:
        print("No technical events data available.")
        return
    
    table = PrettyTable()
    table.field_names = ["Timeframe", "Signal"]
    table.add_row(["Short Term", tech_events.get("short_term", "N/A")])
    table.add_row(["Mid Term", tech_events.get("mid_term", "N/A")])
    table.add_row(["Long Term", tech_events.get("long_term", "N/A")])
    print(table)

def display_key_technicals(insights):
    """Display key technical levels (support, resistance, stop loss)"""
    print("\n=== KEY TECHNICAL LEVELS ===")
    key_tech = insights.get("key_technicals", {})
    if not key_tech:
        print("No key technicals data available.")
        return
    
    table = PrettyTable()
    table.field_names = ["Level Type", "Price"]
    table.add_row(["Support", key_tech.get("support", "N/A")])
    table.add_row(["Resistance", key_tech.get("resistance", "N/A")])
    table.add_row(["Stop Loss", key_tech.get("stop_loss", "N/A")])
    print(table)

def display_valuation(insights):
    """Display valuation metrics"""
    print("\n=== VALUATION METRICS ===")
    valuation = insights.get("valuation", {})
    if not valuation:
        print("No valuation data available.")
        return
    
    print(f"Description: {valuation.get('description', 'N/A')}")
    
    table = PrettyTable()
    table.field_names = ["Metric", "Value"]
    table.add_row(["Trailing P/E", valuation.get("trailing_pe", "N/A")])
    table.add_row(["Forward P/E", valuation.get("forward_pe", "N/A")])
    table.add_row(["Discount/Premium", valuation.get("discount", "N/A")])
    print(table)

def display_recommendation(insights):
    """Display analyst recommendations"""
    print("\n=== ANALYST RECOMMENDATION ===")
    rec = insights.get("recommendation", {})
    if not rec:
        print("No recommendation data available.")
        return
    
    table = PrettyTable()
    table.field_names = ["Provider", "Rating", "Target Price"]
    table.add_row([
        rec.get("provider", "N/A"),
        rec.get("rating", "N/A"),
        rec.get("target_price", "N/A")
    ])
    print(table)

def display_upcoming_events(insights):
    """Display upcoming events (earnings, dividends, splits)"""
    print("\n=== UPCOMING EVENTS ===")
    events = insights.get("upcoming_events", {})
    if not events:
        print("No upcoming events data available.")
        return
    
    # Earnings
    earnings = events.get("earnings", {})
    if earnings and earnings.get("date"):
        print(f"Earnings: {earnings.get('date')} {earnings.get('time', '')}")
    
    # Dividend
    dividend = events.get("dividend", {})
    if dividend and dividend.get("date"):
        print(f"Dividend: {dividend.get('date')} - Amount: {dividend.get('amount', 'N/A')}")
    
    # Split
    split = events.get("split", {})
    if split and split.get("date"):
        print(f"Split: {split.get('date')} - Ratio: {split.get('ratio', 'N/A')}")
    
    if not (earnings.get("date") or dividend.get("date") or split.get("date")):
        print("No specific upcoming events found.")

def display_risk_profile(insights):
    """Display risk profile"""
    print("\n=== RISK PROFILE ===")
    risk = insights.get("risk", {})
    if not risk:
        print("No risk data available.")
        return
    
    print(f"Risk Rating: {risk.get('rating', 'N/A')}")
    print(f"Risk Score: {risk.get('score', 'N/A')}")

def plot_technical_indicators(symbol, insights):
    """Create a visual representation of the technical indicators"""
    try:
        # Extract key technical levels
        key_tech = insights.get("key_technicals", {})
        if not key_tech or not all(key_tech.get(k) for k in ["support", "resistance", "stop_loss"]):
            print("Not enough technical data to create chart.")
            return
        
        # Convert values to float
        support = float(key_tech.get("support", 0))
        resistance = float(key_tech.get("resistance", 0))
        stop_loss = float(key_tech.get("stop_loss", 0))
        
        # Current price is assumed to be between support and resistance
        # This is a simplified visualization without actual price data
        current_price = (support + resistance) / 2
        
        # Create figure
        plt.figure(figsize=(10, 6))
        
        # Plot price levels
        levels = {
            "Resistance": resistance,
            "Current Price": current_price,
            "Support": support,
            "Stop Loss": stop_loss
        }
        
        # Sort levels from highest to lowest
        sorted_levels = sorted(levels.items(), key=lambda x: x[1], reverse=True)
        
        # Colors for different levels
        colors = {
            "Resistance": "red",
            "Current Price": "green",
            "Support": "blue",
            "Stop Loss": "purple"
        }
        
        # Plot horizontal lines
        for name, value in sorted_levels:
            plt.axhline(y=value, color=colors[name], linestyle='-', alpha=0.7, label=f"{name}: {value:.2f}")
        
        # Add labels and title
        plt.ylabel("Price ($)")
        plt.title(f"Key Technical Levels for {symbol}")
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        # Adjust y-axis to show all levels with some padding
        min_value = min(levels.values())
        max_value = max(levels.values())
        range_value = max_value - min_value
        plt.ylim(min_value - range_value*0.1, max_value + range_value*0.1)
        
        # Show the plot
        plt.tight_layout()
        plt.savefig(f"{symbol}_technical_levels.png")
        print(f"Technical levels chart saved as {symbol}_technical_levels.png")
        plt.close()
        
    except Exception as e:
        print(f"Error creating technical chart: {str(e)}")

def run_demo():
    """Run demo of Yahoo Finance Insights API"""
    # Define symbols to analyze
    symbols = ["SPY", "AAPL", "MSFT", "AMZN"]
    
    # Check for API key
    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        logger.error("RAPIDAPI_KEY not found in environment variables")
        return
    
    # Create connector
    connector = YahooFinanceInsightsConnector(api_key)
    
    # Analyze each symbol
    for symbol in symbols:
        print(f"\n\n{'='*50}")
        print(f"ANALYSIS FOR {symbol}")
        print(f"{'='*50}")
        
        # Get condensed insights
        insights = connector.get_condensed_insights(symbol)
        
        if "error" in insights:
            print(f"Error retrieving insights for {symbol}: {insights['error']}")
            continue
        
        # Display different components of the insights
        display_technical_events(insights)
        display_key_technicals(insights)
        display_valuation(insights)
        display_recommendation(insights)
        display_upcoming_events(insights)
        display_risk_profile(insights)
        
        # Create visualization
        plot_technical_indicators(symbol, insights)

if __name__ == "__main__":
    run_demo() 