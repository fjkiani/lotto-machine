import os
import json
import sqlite3
from typing import Dict, Any, List

class ContextDataProvider:
    """
    Provides context (Narrative Agent JSON output, Stockgrid DP snapshot) for a specific date.
    Required for simulating the 'morning brief' that the system receives before trading begins.
    """
    
    def __init__(self, data_dir: str = None):
        if not data_dir:
            # Default to project root / data
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            self.data_dir = os.path.join(base_path, "data")
        else:
            self.data_dir = data_dir
            
    def get_dp_snapshot(self, date_str: str) -> Dict[str, Any]:
        """
        Loads the Stockgrid DP snapshot for the given date from the SQLite database.
        Returns the closest snapshot available before market open on that date.
        """
        db_path = os.path.join(self.data_dir, "dp_timeseries.db")
        if not os.path.exists(db_path):
            return {"alerts": 0, "levels": [], "warning": f"DB not found: {db_path}"}
            
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # For backtesting, we just want the morning snapshot (e.g. 09:00 - 09:30)
            # We'll pull the first record found for the date
            query = """
                SELECT json_data FROM dp_snapshots 
                WHERE date(timestamp) = ?
                ORDER BY timestamp ASC LIMIT 1
            """
            cursor.execute(query, (date_str,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return json.loads(row[0])
            else:
                return {"alerts": 0, "levels": [], "warning": f"No DP data found for {date_str}"}
                
        except Exception as e:
            return {"alerts": 0, "levels": [], "error": str(e)}

    def get_narrative_context(self, date_str: str, logs_dir: str = None) -> Dict[str, Any]:
        """
        Loads the pre-market Narrative Agent JSON file for the given date.
        e.g., /logs/narrative_20260309.json
        """
        if not logs_dir:
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            logs_dir = os.path.join(base_path, "logs")
            
        # Format date from YYYY-MM-DD to YYYYMMDD
        date_formatted = date_str.replace("-", "")
        filepath = os.path.join(logs_dir, f"narrative_{date_formatted}.json")
        
        if not os.path.exists(filepath):
            return {
                "direction": "UNKNOWN",
                "conviction": "LOW",
                "risk_environment": "NEUTRAL",
                "warning": f"No narrative context file found: {filepath}"
            }
            
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                
            # Flatten or extract relevant fields from the NarrativeResult
            return {
                "direction": data.get("direction", "UNKNOWN"),
                "conviction": data.get("conviction", "LOW"),
                "risk_environment": data.get("risk_environment", "NEUTRAL"),
                "confidence_adjustment": data.get("confidence_adjustment", 0),
                "thesis": data.get("thesis", ""),
                "catalysts": data.get("catalysts", [])
            }
        except Exception as e:
            return {
                "direction": "UNKNOWN",
                "conviction": "LOW",
                "risk_environment": "NEUTRAL",
                "error": str(e)
            }
