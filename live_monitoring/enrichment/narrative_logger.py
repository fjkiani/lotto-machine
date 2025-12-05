"""
Narrative Logging System
Persists all narrative outputs for review, backtesting, and model improvement.

Structure:
logs/narratives/{DATE}/
├── {symbol}_event_schedule.json        # Economic calendar
├── {symbol}_mainstream.json            # Perplexity output
├── {symbol}_institutional.json         # ChartExchange stats
├── {symbol}_divergences.json           # Detected conflicts
├── {symbol}_final_narrative.json       # Synthesis output
└── {symbol}_signal_impact.json         # How narrative affected signals
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class NarrativeLogger:
    """
    Logs all narrative pipeline outputs for audit and review.
    
    Manager's Doctrine:
    "Per-agent memory & logging: Each agent should persist inputs/context,
    outputs, source list, and any 'no source' flags. This feeds post-trade
    review and detection of drift/bugs in specific agents or sources."
    """
    
    def __init__(self, base_dir: str = "logs/narratives"):
        """
        Initialize narrative logger.
        
        Args:
            base_dir: Base directory for narrative logs
        """
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        logger.info(f"📝 NarrativeLogger initialized: {base_dir}")
    
    def get_log_dir(self, date: str = None) -> Path:
        """
        Get log directory for a given date.
        
        Args:
            date: Date in YYYY-MM-DD format (defaults to today)
        
        Returns:
            Path to log directory
        """
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        log_dir = Path(self.base_dir) / date
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir
    
    def log_event_schedule(self, symbol: str, events: Dict, date: str = None):
        """
        Log economic calendar events.
        
        Args:
            symbol: Ticker symbol
            events: Output from EventLoader.load_events()
            date: Date (defaults to today)
        """
        log_dir = self.get_log_dir(date)
        log_file = log_dir / f"{symbol.lower()}_event_schedule.json"
        
        try:
            with open(log_file, 'w') as f:
                json.dump(events, f, indent=2)
            logger.info(f"✅ Logged event schedule: {log_file}")
        except Exception as e:
            logger.error(f"❌ Error logging event schedule: {e}")
    
    def log_mainstream_narrative(self, symbol: str, narrative_data: Dict, date: str = None):
        """
        Log mainstream narrative from Perplexity.
        
        Args:
            symbol: Ticker symbol
            narrative_data: Output from PerplexitySearchClient
            date: Date (defaults to today)
        """
        log_dir = self.get_log_dir(date)
        log_file = log_dir / f"{symbol.lower()}_mainstream.json"
        
        try:
            # Add metadata
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "symbol": symbol,
                "source": "perplexity",
                **narrative_data
            }
            
            with open(log_file, 'w') as f:
                json.dump(log_data, f, indent=2)
            logger.info(f"✅ Logged mainstream narrative: {log_file}")
        except Exception as e:
            logger.error(f"❌ Error logging mainstream narrative: {e}")
    
    def log_institutional_stats(self, symbol: str, stats: Dict, date: str = None):
        """
        Log institutional data from ChartExchange.
        
        Args:
            symbol: Ticker symbol
            stats: Institutional stats dict
            date: Date (defaults to today)
        """
        log_dir = self.get_log_dir(date)
        log_file = log_dir / f"{symbol.lower()}_institutional.json"
        
        try:
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "symbol": symbol,
                "source": "chartexchange",
                **stats
            }
            
            with open(log_file, 'w') as f:
                json.dump(log_data, f, indent=2)
            logger.info(f"✅ Logged institutional stats: {log_file}")
        except Exception as e:
            logger.error(f"❌ Error logging institutional stats: {e}")
    
    def log_divergences(self, symbol: str, divergences: list, date: str = None):
        """
        Log detected narrative divergences.
        
        Args:
            symbol: Ticker symbol
            divergences: List of divergence dicts
            date: Date (defaults to today)
        """
        log_dir = self.get_log_dir(date)
        log_file = log_dir / f"{symbol.lower()}_divergences.json"
        
        try:
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "symbol": symbol,
                "divergence_count": len(divergences),
                "divergences": divergences
            }
            
            with open(log_file, 'w') as f:
                json.dump(log_data, f, indent=2)
            logger.info(f"✅ Logged divergences: {log_file}")
        except Exception as e:
            logger.error(f"❌ Error logging divergences: {e}")
    
    def log_final_narrative(self, symbol: str, narrative: Dict, date: str = None):
        """
        Log final synthesized narrative.
        
        Args:
            symbol: Ticker symbol
            narrative: Final narrative dict from synthesis
            date: Date (defaults to today)
        """
        log_dir = self.get_log_dir(date)
        log_file = log_dir / f"{symbol.lower()}_final_narrative.json"
        
        try:
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "symbol": symbol,
                **narrative
            }
            
            with open(log_file, 'w') as f:
                json.dump(log_data, f, indent=2)
            logger.info(f"✅ Logged final narrative: {log_file}")
        except Exception as e:
            logger.error(f"❌ Error logging final narrative: {e}")
    
    def log_signal_impact(self, symbol: str, signal_data: Dict, date: str = None):
        """
        Log how narrative affected signal confidence.
        
        Args:
            symbol: Ticker symbol
            signal_data: Dict with original/adjusted confidence + rationale
            date: Date (defaults to today)
        """
        log_dir = self.get_log_dir(date)
        log_file = log_dir / f"{symbol.lower()}_signal_impact.json"
        
        try:
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "symbol": symbol,
                **signal_data
            }
            
            with open(log_file, 'w') as f:
                json.dump(log_data, f, indent=2)
            logger.info(f"✅ Logged signal impact: {log_file}")
        except Exception as e:
            logger.error(f"❌ Error logging signal impact: {e}")
    
    def log_complete_pipeline(self, symbol: str, pipeline_output: Dict, date: str = None):
        """
        Log all outputs from market_narrative_pipeline at once.
        
        Args:
            symbol: Ticker symbol
            pipeline_output: Complete output from market_narrative_pipeline()
            date: Date (defaults to today)
        """
        # Log each component
        if 'events' in pipeline_output:
            self.log_event_schedule(symbol, pipeline_output['events'], date)
        
        if 'mainstream_narrative' in pipeline_output:
            self.log_mainstream_narrative(
                symbol,
                {"narrative": pipeline_output['mainstream_narrative']},
                date
            )
        
        if 'institutional_stats' in pipeline_output:
            self.log_institutional_stats(
                symbol,
                pipeline_output['institutional_stats'],
                date
            )
        
        if 'divergences' in pipeline_output:
            self.log_divergences(symbol, pipeline_output['divergences'], date)
        
        if 'final_narrative' in pipeline_output:
            self.log_final_narrative(symbol, pipeline_output['final_narrative'], date)
        
        logger.info(f"✅ Complete pipeline logged for {symbol}")
    
    def get_daily_summary(self, date: str = None) -> Dict:
        """
        Get summary of all narratives for a given day.
        
        Args:
            date: Date in YYYY-MM-DD format (defaults to today)
        
        Returns:
            {
                "date": "2025-11-20",
                "symbols": ["SPY", "QQQ"],
                "total_narratives": 2,
                "total_divergences": 3,
                "files": [...]
            }
        """
        log_dir = self.get_log_dir(date)
        
        if not log_dir.exists():
            return {
                "date": date or datetime.now().strftime('%Y-%m-%d'),
                "symbols": [],
                "total_narratives": 0,
                "total_divergences": 0,
                "files": []
            }
        
        # Find all narrative files
        narrative_files = list(log_dir.glob("*_final_narrative.json"))
        divergence_files = list(log_dir.glob("*_divergences.json"))
        
        # Extract symbols
        symbols = set()
        for f in narrative_files:
            symbol = f.stem.replace('_final_narrative', '').upper()
            symbols.add(symbol)
        
        # Count total divergences
        total_divergences = 0
        for f in divergence_files:
            try:
                with open(f) as file:
                    data = json.load(file)
                    total_divergences += data.get('divergence_count', 0)
            except:
                pass
        
        return {
            "date": date or datetime.now().strftime('%Y-%m-%d'),
            "symbols": sorted(list(symbols)),
            "total_narratives": len(narrative_files),
            "total_divergences": total_divergences,
            "files": [str(f) for f in log_dir.iterdir()]
        }


# ========================================================================================
# DEMO / TEST
# ========================================================================================

def _demo():
    """Test NarrativeLogger."""
    print("=" * 80)
    print("🧪 TESTING NARRATIVE LOGGER")
    print("=" * 80)
    
    logger_obj = NarrativeLogger()
    
    # Test logging components
    print("\n📝 Logging test narrative components...")
    
    # Event schedule
    logger_obj.log_event_schedule("SPY", {
        "date": "2025-11-20",
        "macro_events": [
            {"name": "CPI", "time": "08:30", "actual": "3.5%", "estimate": "3.2%"}
        ],
        "opex": False
    })
    
    # Mainstream narrative
    logger_obj.log_mainstream_narrative("SPY", {
        "narrative": "Moody's downgrade + hawkish Fed → selloff",
        "sources": ["https://ft.com/...", "https://bloomberg.com/..."]
    })
    
    # Institutional stats
    logger_obj.log_institutional_stats("SPY", {
        "dp_battleground": 660.00,
        "dp_buying_ratio": 0.68,
        "max_pain": 665.00
    })
    
    # Divergences
    logger_obj.log_divergences("SPY", [
        {
            "type": "DISTRIBUTION_MASKED_AS_RALLY",
            "severity": "HIGH",
            "explanation": "Price up, DP selling"
        }
    ])
    
    # Final narrative
    logger_obj.log_final_narrative("SPY", {
        "narrative": "Institutional accumulation at $660 support...",
        "conviction": "HIGH",
        "risk_environment": "ACCUMULATION_PHASE"
    })
    
    # Signal impact
    logger_obj.log_signal_impact("SPY", {
        "original_confidence": 0.66,
        "narrative_boost": 0.15,
        "final_confidence": 0.81
    })
    
    print("\n📊 Daily summary:")
    summary = logger_obj.get_daily_summary()
    print(json.dumps(summary, indent=2))
    
    print("\n" + "=" * 80)
    print("✅ NarrativeLogger test complete!")
    print(f"📁 Check logs at: logs/narratives/{datetime.now().strftime('%Y-%m-%d')}/")
    print("=" * 80)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    _demo()

