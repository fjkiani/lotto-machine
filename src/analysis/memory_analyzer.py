import logging
from typing import Dict, Optional

# Import necessary components
try:
    from src.llm.memory_enhanced_analysis import MemoryEnhancedAnalysis
except ImportError:
    logging.error("Failed to import MemoryEnhancedAnalysis from src.llm")
    MemoryEnhancedAnalysis = None

try:
    from src.data.connectors.yahoo_finance import YahooFinanceConnector
except ImportError:
    logging.error("Failed to import YahooFinanceConnector from src.data.connectors")
    YahooFinanceConnector = None

logger = logging.getLogger(__name__)

def run_memory_analysis(
    ticker: str,
    connector: Optional[YahooFinanceConnector],
    memory_analyzer_instance: Optional[MemoryEnhancedAnalysis]
) -> Dict:
    """
    Wrapper function to run the memory-enhanced analysis.

    Args:
        ticker: The stock ticker symbol.
        connector: An instance of YahooFinanceConnector.
        memory_analyzer_instance: An instance of MemoryEnhancedAnalysis (from session state).

    Returns:
        A dictionary containing the analysis results or an error.
    """
    logger.info(f"Running Memory-Enhanced Analysis workflow for {ticker}")

    # Check if necessary components are available
    if not memory_analyzer_instance:
        logger.error("MemoryEnhancedAnalysis instance was not provided.")
        return {"error": "Memory analyzer instance is missing."}
    if not connector:
        logger.error("YahooFinanceConnector instance was not provided.")
        return {"error": "Data connector instance is missing."}
    
    # Ensure the imported class is valid before using the instance
    if not MemoryEnhancedAnalysis:
         logger.error("MemoryEnhancedAnalysis class could not be imported.")
         return {"error": "MemoryEnhancedAnalysis class failed to import."}
    if not isinstance(memory_analyzer_instance, MemoryEnhancedAnalysis):
         logger.error(f"Invalid type for memory_analyzer_instance: {type(memory_analyzer_instance)}")
         return {"error": "Invalid memory analyzer instance provided."}

    try:
        # Call the analysis method on the provided instance
        result = memory_analyzer_instance.analyze_ticker_with_memory(
            ticker=ticker
        )
        logger.info(f"Memory-Enhanced Analysis completed for {ticker}")
        return result
    except Exception as e:
        logger.error(f"Error running memory-enhanced analysis workflow for {ticker}: {e}", exc_info=True)
        return {"error": f"An unexpected error occurred during memory-enhanced analysis: {e}"} 