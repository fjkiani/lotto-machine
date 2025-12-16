"""
📊 ALERTS LOADER
Loads signals from alerts_history.db for production analysis
"""

import sqlite3
import json
import re
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

@dataclass
class SignalAlert:
    """Signal alert from production system"""
    timestamp: datetime
    alert_type: str  # dp_alert, synthesis, narrative_brain, etc.
    symbol: str
    source: str
    title: str
    content: Optional[str]
    embed_data: Dict[str, Any]
    confluence_score: Optional[float] = None
    direction: Optional[str] = None  # LONG, SHORT
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_reward: Optional[float] = None

class AlertsLoader:
    """Loads production alerts from alerts_history.db"""
    
    def __init__(self, db_path: str = "data/alerts_history.db"):
        self.db_path = db_path
    
    def load_date(self, date: str) -> List[SignalAlert]:
        """
        Load all alerts for a specific date
        
        Args:
            date: Date in YYYY-MM-DD format
            
        Returns:
            List of SignalAlert objects
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Handle both date-only and full datetime formats
        start_datetime = f"{date}T00:00:00"
        end_datetime = f"{date}T23:59:59.999999"  # Include microseconds
        
        cursor.execute('''
            SELECT timestamp, alert_type, symbol, source, title, content, embed_json
            FROM alerts
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
        ''', [start_datetime, end_datetime])
        
        rows = cursor.fetchall()
        alerts = []
        
        for row in rows:
            try:
                # Parse embed_json (handle None)
                embed_data = {}
                if row[6]:
                    try:
                        embed_data = json.loads(row[6])
                    except json.JSONDecodeError:
                        embed_data = {}
                
                # Parse timestamp
                timestamp_str = row[0]
                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                except ValueError:
                    # Try without microseconds
                    timestamp = datetime.strptime(timestamp_str.split('.')[0], '%Y-%m-%dT%H:%M:%S')
                
                alert = SignalAlert(
                    timestamp=timestamp,
                    alert_type=row[1] or 'unknown',
                    symbol=row[2] or 'N/A',
                    source=row[3] or 'unknown',
                    title=row[4] or '',
                    content=row[5],
                    embed_data=embed_data,
                    confluence_score=self._extract_confluence(embed_data, row[4] or ''),
                    direction=self._extract_direction(embed_data, row[4] or ''),
                    entry_price=self._extract_price(embed_data, 'entry', 'Entry'),
                    stop_loss=self._extract_price(embed_data, 'stop', 'Stop'),
                    take_profit=self._extract_price(embed_data, 'target', 'Target'),
                    risk_reward=self._extract_risk_reward(embed_data, row[4] or '')
                )
                alerts.append(alert)
            except Exception as e:
                # Log first few errors for debugging
                if len(alerts) < 3:
                    print(f"⚠️  Error processing alert: {e}")
                    import traceback
                    traceback.print_exc()
                continue
        
        conn.close()
        return alerts
    
    def load_today(self) -> List[SignalAlert]:
        """Load today's alerts"""
        today = datetime.now().strftime('%Y-%m-%d')
        return self.load_date(today)
    
    def load_date_range(self, start_date: str, end_date: str) -> List[SignalAlert]:
        """Load alerts for a date range"""
        alerts = []
        current = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        while current <= end:
            date_str = current.strftime('%Y-%m-%d')
            alerts.extend(self.load_date(date_str))
            current += timedelta(days=1)
        
        return alerts
    
    def load_session(self, date: str, start_time: str = "09:30", end_time: str = "16:00") -> List[SignalAlert]:
        """Load alerts for a specific trading session"""
        all_alerts = self.load_date(date)
        start_datetime = datetime.strptime(f"{date}T{start_time}:00", '%Y-%m-%dT%H:%M:%S')
        end_datetime = datetime.strptime(f"{date}T{end_time}:00", '%Y-%m-%dT%H:%M:%S')
        
        return [
            alert for alert in all_alerts
            if start_datetime <= alert.timestamp <= end_datetime
        ]
    
    @staticmethod
    def _extract_confluence(embed_data: Dict, title: str) -> Optional[float]:
        """Extract confluence score from embed or title"""
        # Try fields first
        fields = embed_data.get('fields', [])
        for field in fields:
            name = field.get('name', '')
            value = field.get('value', '')
            if 'confluence' in name.lower():
                # Extract number from value
                match = re.search(r'(\d+(?:\.\d+)?)', value)
                if match:
                    return float(match.group(1))
        
        # Try description
        desc = embed_data.get('description', '')
        match = re.search(r'confluence[:\s]+(\d+(?:\.\d+)?)', desc, re.IGNORECASE)
        if match:
            return float(match.group(1))
        
        # Try title
        match = re.search(r'(\d+(?:\.\d+)?)%', title)
        if match:
            return float(match.group(1))
        
        return None
    
    @staticmethod
    def _extract_direction(embed_data: Dict, title: str) -> Optional[str]:
        """Extract trade direction"""
        # Check fields
        fields = embed_data.get('fields', [])
        for field in fields:
            value = field.get('value', '')
            if 'LONG' in value.upper() or '📈' in value:
                return 'LONG'
            if 'SHORT' in value.upper() or '📉' in value:
                return 'SHORT'
        
        # Check title
        if 'LONG' in title.upper() or '📈' in title:
            return 'LONG'
        if 'SHORT' in title.upper() or '📉' in title:
            return 'SHORT'
        
        return None
    
    @staticmethod
    def _extract_price(embed_data: Dict, key: str, label: str) -> Optional[float]:
        """Extract price from embed fields"""
        fields = embed_data.get('fields', [])
        for field in fields:
            name = field.get('name', '')
            value = field.get('value', '')
            if label.lower() in name.lower():
                # Extract $XX.XX
                match = re.search(r'\$(\d+(?:\.\d+)?)', value)
                if match:
                    return float(match.group(1))
        return None
    
    @staticmethod
    def _extract_risk_reward(embed_data: Dict, title: str) -> Optional[float]:
        """Extract risk/reward ratio"""
        # Check fields
        fields = embed_data.get('fields', [])
        for field in fields:
            value = field.get('value', '')
            # Look for R/R: X:Y or X:1
            match = re.search(r'R/R[:\s]+(\d+(?:\.\d+)?):(\d+(?:\.\d+)?)', value, re.IGNORECASE)
            if match:
                return float(match.group(1)) / float(match.group(2))
        
        # Check title
        match = re.search(r'(\d+(?:\.\d+)?):(\d+(?:\.\d+)?)', title)
        if match:
            return float(match.group(1)) / float(match.group(2))
        
        return None

