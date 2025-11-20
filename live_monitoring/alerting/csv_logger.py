#!/usr/bin/env python3
"""
CSV LOGGER - Audit trail for all signals
- Log every signal to CSV
- Queryable history
"""

import csv
from pathlib import Path
from datetime import datetime
import sys

sys.path.append(str(Path(__file__).parent.parent / 'core'))
from signal_generator import LiveSignal

class CSVLogger:
    """Log signals to CSV for audit trail"""
    
    def __init__(self, csv_file: str = "signals.csv"):
        self.csv_file = Path(csv_file)
        self.csv_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize CSV with headers if needed
        if not self.csv_file.exists():
            self._write_header()
    
    def _write_header(self):
        """Write CSV header"""
        with open(self.csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp',
                'symbol',
                'action',
                'signal_type',
                'current_price',
                'entry_price',
                'stop_loss',
                'take_profit',
                'confidence',
                'risk_reward',
                'position_pct',
                'dp_level',
                'institutional_score',
                'is_master',
                'primary_reason',
                'supporting_factors'
            ])
    
    def alert_signal(self, signal: LiveSignal):
        """Log signal to CSV"""
        try:
            with open(self.csv_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    signal.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    signal.symbol,
                    signal.action,
                    signal.signal_type,
                    f"{signal.current_price:.2f}",
                    f"{signal.entry_price:.2f}",
                    f"{signal.stop_loss:.2f}",
                    f"{signal.take_profit:.2f}",
                    f"{signal.confidence:.2f}",
                    f"{signal.risk_reward_ratio:.2f}",
                    f"{signal.position_size_pct:.3f}",
                    f"{signal.dp_level:.2f}",
                    f"{signal.institutional_score:.2f}",
                    signal.is_master_signal,
                    signal.primary_reason,
                    " | ".join(signal.supporting_factors)
                ])
        except Exception as e:
            print(f"Error logging to CSV: {e}")



