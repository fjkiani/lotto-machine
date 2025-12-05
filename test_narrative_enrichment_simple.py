#!/usr/bin/env python3
"""
Simple test of narrative enrichment without full institutional context.
Just tests the narrative pipeline integration.
"""

import sys
import os
from pathlib import Path
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

print("=" * 120)
print("🧪 TESTING NARRATIVE ENRICHMENT - SIMPLE VERSION")
print("=" * 120)

# Add paths
sys.path.append(str(Path(__file__).parent / 'live_monitoring' / 'enrichment'))

from market_narrative_pipeline import market_narrative_pipeline

def test_narrative_pipeline():
    """Test that the complete narrative pipeline works."""
    
    print("\n🔥 Testing Market Narrative Pipeline for SPY...")
    print("   This will:")
    print("   1. Load economic events (EventLoader)")
    print("   2. Fetch institutional context (ChartExchange)")
    print("   3. Query Perplexity for news")
    print("   4. Detect divergences")
    print("   5. Synthesize final narrative (Gemini)")
    print("   6. Log all outputs")
    
    try:
        # Run the pipeline
        narrative = market_narrative_pipeline(
            symbol="SPY",
            date=datetime.now().strftime("%Y-%m-%d"),
            enable_logging=True
        )
        
        print("\n" + "=" * 120)
        print("✅ NARRATIVE PIPELINE COMPLETE!")
        print("=" * 120)
        
        print(f"\n📊 NARRATIVE OUTPUT:")
        print(f"   Symbol: {narrative.symbol}")
        print(f"   Direction: {narrative.overall_direction}")
        print(f"   Conviction: {narrative.conviction}")
        print(f"   Causal Chain: {narrative.causal_chain[:200] if narrative.causal_chain else 'N/A'}...")
        if hasattr(narrative, 'warnings') and narrative.warnings:
            print(f"   ⚠️  Warnings: {', '.join(narrative.warnings)}")
        
        print("\n✅ Test complete! Check logs/narratives/ for full output.")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error running narrative pipeline: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_narrative_pipeline()
    sys.exit(0 if success else 1)

