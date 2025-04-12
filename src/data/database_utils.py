import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Configure logging
logger = logging.getLogger(__name__)

# Define the database file path (e.g., in the workspace root)
DB_FILE = "analysis_history.db"

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row # Optional: return rows as dict-like objects
        logger.debug(f"Successfully connected to database: {DB_FILE}")
        return conn
    except sqlite3.Error as e:
        logger.error(f"Error connecting to database {DB_FILE}: {e}", exc_info=True)
        raise # Re-raise the exception after logging

def init_db():
    """Initializes the database and creates the analysis_history table if it doesn't exist."""
    logger.info(f"Initializing database schema in {DB_FILE}...")
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analysis_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    analysis_type TEXT NOT NULL,
                    result_json TEXT NOT NULL
                );
            """)
            # Optional: Add index for faster lookups later
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ticker_type_time ON analysis_history (ticker, analysis_type, timestamp);")
            conn.commit()
            logger.info("Database schema initialized successfully (table 'analysis_history' created or already exists).")
    except sqlite3.Error as e:
        logger.error(f"Error initializing database schema: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error during database initialization: {e}", exc_info=True)


def save_analysis(ticker: str, analysis_type: str, result_dict: Dict[str, Any]):
    """Saves the analysis result dictionary to the database.

    Args:
        ticker: The stock ticker symbol.
        analysis_type: A string identifying the type of analysis (e.g., 'options', 'technical').
        result_dict: The dictionary containing the analysis results.
    """
    timestamp = datetime.now().isoformat()
    
    # Ensure result_dict is serializable to JSON
    try:
        result_json = json.dumps(result_dict, default=str) # Use default=str to handle non-serializable types like datetime
    except TypeError as e:
        logger.error(f"Failed to serialize result_dict to JSON for {ticker} ({analysis_type}): {e}", exc_info=True)
        # Decide how to handle: skip saving, save partial, save error placeholder?
        # For now, we'll just log the error and not save.
        return 
    except Exception as e:
        logger.error(f"Unexpected error serializing result_dict for {ticker} ({analysis_type}): {e}", exc_info=True)
        return

    logger.info(f"Attempting to save analysis for {ticker} ({analysis_type}) to database.")
    sql = """
        INSERT INTO analysis_history (timestamp, ticker, analysis_type, result_json)
        VALUES (?, ?, ?, ?);
    """
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (timestamp, ticker, analysis_type, result_json))
            conn.commit()
            logger.info(f"Successfully saved analysis for {ticker} ({analysis_type}) at {timestamp}.")
    except sqlite3.Error as e:
        logger.error(f"Error saving analysis to database for {ticker} ({analysis_type}): {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error saving analysis for {ticker} ({analysis_type}): {e}", exc_info=True)

# Example retrieval function for Phase 2
def get_latest_analysis(ticker: str, analysis_type: str) -> Optional[Dict]:
    """Retrieves the most recent analysis result for a given ticker and type."""
    logger.info(f"Retrieving latest analysis for {ticker} ({analysis_type})...")
    sql = """
        SELECT result_json 
        FROM analysis_history 
        WHERE ticker = ? AND analysis_type = ? 
        ORDER BY timestamp DESC 
        LIMIT 1;
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (ticker, analysis_type))
            row = cursor.fetchone()
            if row:
                logger.info(f"Found latest analysis for {ticker} ({analysis_type}).")
                return json.loads(row['result_json'])
            else:
                logger.info(f"No previous analysis found for {ticker} ({analysis_type}).")
                return None
    except sqlite3.Error as e:
        logger.error(f"Error retrieving latest analysis for {ticker} ({analysis_type}): {e}", exc_info=True)
        return None
    except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON for latest analysis of {ticker} ({analysis_type}): {e}", exc_info=True)
            # Potentially return the raw string or handle corrupt data
            return {"error": "Failed to decode stored JSON."}
    except Exception as e:
        logger.error(f"Unexpected error retrieving analysis for {ticker} ({analysis_type}): {e}", exc_info=True)
        return None

# Example Usage (can be removed or kept for testing)
if __name__ == '__main__':
    print("Initializing DB (if needed)...")
    init_db()
    print("Saving sample analysis...")
    sample_result = {
        "summary": "Looking bullish",
        "confidence": "High",
        "target": 150.50,
        "calculated_at": datetime.now() # Example of non-serializable type handled by default=str
    }
    save_analysis("TEST", "technical", sample_result)
    print("Sample analysis saved.")

    print("Retrieving latest 'technical' analysis for 'TEST'...")
    latest = get_latest_analysis("TEST", "technical")
    if latest:
        print("Latest Analysis Found:")
        print(json.dumps(latest, indent=2))
    else:
        print("No analysis found.") 