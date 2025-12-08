#!/usr/bin/env python3
"""
🔥 TRAIN THE ECONOMIC BEAST 🔥

Fetches REAL historical economic data from FRED and trains the model.

Data sources:
- FRED API (Federal Reserve Economic Data) - ALL historical releases
- yfinance - Market reactions (SPY, TLT, VIX)
- ChartExchange - Dark Pool positioning

This will create a BEAST that predicts Fed Watch movements!
"""

import os
import sys
import logging
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Setup
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# Add path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from live_monitoring.agents.economic import EconomicIntelligenceEngine
from live_monitoring.agents.economic.models import EconomicRelease, EventType
from live_monitoring.agents.economic.data_collector import EconomicDataCollector, FRED_SERIES


def train_the_beast():
    """
    🔥 TRAIN THE ECONOMIC BEAST! 🔥
    
    Fetches ALL historical data and learns patterns.
    """
    print("=" * 80)
    print("🔥 TRAINING THE ECONOMIC BEAST 🔥")
    print("=" * 80)
    
    fred_key = os.getenv('FRED_API_KEY')
    if not fred_key:
        print("❌ FRED_API_KEY not set!")
        return
    
    print(f"✅ FRED API Key: {fred_key[:8]}...")
    
    # Initialize
    engine = EconomicIntelligenceEngine()
    collector = EconomicDataCollector(fred_api_key=fred_key)
    
    # =========================================================================
    # STEP 1: Fetch ALL historical data from FRED
    # =========================================================================
    print("\n" + "=" * 80)
    print("📊 STEP 1: FETCHING HISTORICAL DATA FROM FRED")
    print("=" * 80)
    
    # Events to fetch
    event_types = [
        EventType.NFP,
        EventType.UNEMPLOYMENT,
        EventType.CPI,
        EventType.CORE_CPI,
        EventType.PPI,
        EventType.PCE,
        EventType.RETAIL_SALES,
        EventType.JOBLESS_CLAIMS,
    ]
    
    all_releases = []
    
    for event_type in event_types:
        print(f"\n📥 Fetching {event_type.value}...")
        
        releases = collector.fetch_economic_releases(
            event_type=event_type,
            start_date="2020-01-01"  # Last 5 years
        )
        
        print(f"   → Got {len(releases)} releases")
        all_releases.extend(releases)
        
        # Rate limit
        time.sleep(0.5)
    
    print(f"\n📊 Total releases fetched: {len(all_releases)}")
    
    # =========================================================================
    # STEP 2: Enrich with market reactions
    # =========================================================================
    print("\n" + "=" * 80)
    print("📈 STEP 2: ENRICHING WITH MARKET REACTIONS (SPY, TLT, VIX)")
    print("=" * 80)
    
    print("   (This may take a few minutes...)")
    
    enriched = collector.enrich_with_market_data(all_releases)
    
    print(f"   ✅ Enriched {len(enriched)} releases with market data")
    
    # =========================================================================
    # STEP 3: Add curated Fed Watch data (manual - most important!)
    # =========================================================================
    print("\n" + "=" * 80)
    print("🎯 STEP 3: ADDING CURATED FED WATCH DATA")
    print("=" * 80)
    
    # These are KNOWN Fed Watch shifts from major releases
    # This is the GOLD - what we're trying to predict!
    curated_data = [
        # 2024 NFP releases with Fed Watch data
        EconomicRelease(
            date="2024-12-06", time="08:30", event_type=EventType.NFP,
            event_name="Nonfarm Payrolls", actual=227000, forecast=200000, previous=36000,
            surprise_pct=13.5, surprise_sigma=1.35,
            fed_watch_before=66, fed_watch_after_1hr=74, fed_watch_shift_1hr=8,
            spy_change_1hr=0.3, tlt_change_1hr=0.5, days_to_fomc=12,
            source="curated"
        ),
        EconomicRelease(
            date="2024-11-01", time="08:30", event_type=EventType.NFP,
            event_name="Nonfarm Payrolls", actual=12000, forecast=100000, previous=254000,
            surprise_pct=-88, surprise_sigma=-2.2,
            fed_watch_before=70, fed_watch_after_1hr=82, fed_watch_shift_1hr=12,
            spy_change_1hr=0.8, tlt_change_1hr=0.9, days_to_fomc=6,
            source="curated"
        ),
        EconomicRelease(
            date="2024-10-04", time="08:30", event_type=EventType.NFP,
            event_name="Nonfarm Payrolls", actual=254000, forecast=140000, previous=159000,
            surprise_pct=81, surprise_sigma=2.5,
            fed_watch_before=95, fed_watch_after_1hr=85, fed_watch_shift_1hr=-10,
            spy_change_1hr=-0.2, tlt_change_1hr=-0.5, days_to_fomc=33,
            source="curated"
        ),
        EconomicRelease(
            date="2024-09-06", time="08:30", event_type=EventType.NFP,
            event_name="Nonfarm Payrolls", actual=142000, forecast=160000, previous=89000,
            surprise_pct=-11, surprise_sigma=-0.9,
            fed_watch_before=60, fed_watch_after_1hr=70, fed_watch_shift_1hr=10,
            spy_change_1hr=0.5, tlt_change_1hr=0.3, days_to_fomc=12,
            source="curated"
        ),
        EconomicRelease(
            date="2024-08-02", time="08:30", event_type=EventType.NFP,
            event_name="Nonfarm Payrolls", actual=114000, forecast=175000, previous=179000,
            surprise_pct=-35, surprise_sigma=-1.8,
            fed_watch_before=75, fed_watch_after_1hr=90, fed_watch_shift_1hr=15,
            spy_change_1hr=1.2, tlt_change_1hr=1.5, days_to_fomc=46,
            source="curated"
        ),
        EconomicRelease(
            date="2024-07-05", time="08:30", event_type=EventType.NFP,
            event_name="Nonfarm Payrolls", actual=206000, forecast=190000, previous=218000,
            surprise_pct=8.4, surprise_sigma=0.5,
            fed_watch_before=58, fed_watch_after_1hr=55, fed_watch_shift_1hr=-3,
            spy_change_1hr=-0.1, days_to_fomc=26,
            source="curated"
        ),
        EconomicRelease(
            date="2024-06-07", time="08:30", event_type=EventType.NFP,
            event_name="Nonfarm Payrolls", actual=272000, forecast=180000, previous=165000,
            surprise_pct=51, surprise_sigma=2.0,
            fed_watch_before=68, fed_watch_after_1hr=52, fed_watch_shift_1hr=-16,
            spy_change_1hr=-0.8, days_to_fomc=5,
            source="curated"
        ),
        EconomicRelease(
            date="2024-05-03", time="08:30", event_type=EventType.NFP,
            event_name="Nonfarm Payrolls", actual=175000, forecast=240000, previous=315000,
            surprise_pct=-27, surprise_sigma=-1.3,
            fed_watch_before=12, fed_watch_after_1hr=20, fed_watch_shift_1hr=8,
            spy_change_1hr=0.6, days_to_fomc=4,
            source="curated"
        ),
        
        # 2024 CPI releases
        EconomicRelease(
            date="2024-11-13", time="08:30", event_type=EventType.CPI,
            event_name="CPI", actual=2.6, forecast=2.6, previous=2.4,
            surprise_pct=0, surprise_sigma=0,
            fed_watch_before=62, fed_watch_after_1hr=65, fed_watch_shift_1hr=3,
            spy_change_1hr=0.2, days_to_fomc=35,
            source="curated"
        ),
        EconomicRelease(
            date="2024-10-10", time="08:30", event_type=EventType.CPI,
            event_name="CPI", actual=2.4, forecast=2.3, previous=2.5,
            surprise_pct=4.3, surprise_sigma=0.43,
            fed_watch_before=85, fed_watch_after_1hr=83, fed_watch_shift_1hr=-2,
            spy_change_1hr=-0.1, days_to_fomc=27,
            source="curated"
        ),
        EconomicRelease(
            date="2024-09-11", time="08:30", event_type=EventType.CPI,
            event_name="CPI", actual=2.5, forecast=2.5, previous=2.9,
            surprise_pct=0, surprise_sigma=0,
            fed_watch_before=67, fed_watch_after_1hr=70, fed_watch_shift_1hr=3,
            spy_change_1hr=0.3, days_to_fomc=7,
            source="curated"
        ),
        EconomicRelease(
            date="2024-08-14", time="08:30", event_type=EventType.CPI,
            event_name="CPI", actual=2.9, forecast=3.0, previous=3.0,
            surprise_pct=-3.3, surprise_sigma=-0.33,
            fed_watch_before=48, fed_watch_after_1hr=55, fed_watch_shift_1hr=7,
            spy_change_1hr=0.5, days_to_fomc=35,
            source="curated"
        ),
        EconomicRelease(
            date="2024-07-11", time="08:30", event_type=EventType.CPI,
            event_name="CPI", actual=3.0, forecast=3.1, previous=3.3,
            surprise_pct=-3.2, surprise_sigma=-0.32,
            fed_watch_before=73, fed_watch_after_1hr=92, fed_watch_shift_1hr=19,
            spy_change_1hr=0.8, days_to_fomc=20,
            source="curated"
        ),
        
        # PCE releases (Fed's preferred measure!)
        EconomicRelease(
            date="2024-11-27", time="08:30", event_type=EventType.PCE,
            event_name="PCE", actual=2.3, forecast=2.3, previous=2.1,
            surprise_pct=0, surprise_sigma=0,
            fed_watch_before=60, fed_watch_after_1hr=58, fed_watch_shift_1hr=-2,
            spy_change_1hr=-0.1, days_to_fomc=21,
            source="curated"
        ),
        EconomicRelease(
            date="2024-10-31", time="08:30", event_type=EventType.PCE,
            event_name="PCE", actual=2.1, forecast=2.1, previous=2.2,
            surprise_pct=0, surprise_sigma=0,
            fed_watch_before=97, fed_watch_after_1hr=97, fed_watch_shift_1hr=0,
            spy_change_1hr=0.0, days_to_fomc=7,
            source="curated"
        ),
        EconomicRelease(
            date="2024-09-27", time="08:30", event_type=EventType.PCE,
            event_name="PCE", actual=2.2, forecast=2.3, previous=2.5,
            surprise_pct=-4.3, surprise_sigma=-0.43,
            fed_watch_before=52, fed_watch_after_1hr=58, fed_watch_shift_1hr=6,
            spy_change_1hr=0.4, days_to_fomc=40,
            source="curated"
        ),
    ]
    
    print(f"   Added {len(curated_data)} curated releases with Fed Watch data")
    
    # =========================================================================
    # STEP 4: Save ALL data to database
    # =========================================================================
    print("\n" + "=" * 80)
    print("💾 STEP 4: SAVING TO DATABASE")
    print("=" * 80)
    
    # Save enriched FRED data
    engine.db.save_releases_batch(enriched)
    print(f"   ✅ Saved {len(enriched)} FRED releases")
    
    # Save curated data (this has the gold - Fed Watch shifts!)
    engine.db.save_releases_batch(curated_data)
    print(f"   ✅ Saved {len(curated_data)} curated releases")
    
    # =========================================================================
    # STEP 5: TRAIN THE BEAST!
    # =========================================================================
    print("\n" + "=" * 80)
    print("🧠 STEP 5: TRAINING THE BEAST!")
    print("=" * 80)
    
    # Get all data and learn patterns
    all_data = engine.db.get_all_releases(min_fed_watch_data=True)
    print(f"   Training on {len(all_data)} releases with Fed Watch data...")
    
    patterns = engine.learner.learn_all_patterns(all_data)
    
    # Save patterns
    for pattern in patterns.values():
        engine.db.save_pattern(pattern)
    
    engine.predictor.set_patterns(patterns)
    
    # =========================================================================
    # STEP 6: Show what the BEAST learned!
    # =========================================================================
    print("\n" + "=" * 80)
    print("🔥 THE BEAST IS TRAINED! 🔥")
    print("=" * 80)
    
    engine.print_status()
    
    # =========================================================================
    # STEP 7: Test predictions
    # =========================================================================
    print("\n" + "=" * 80)
    print("🔮 TESTING THE BEAST'S PREDICTIONS")
    print("=" * 80)
    
    # Test NFP miss
    print("\n📊 If NFP MISSES by 2σ (weak jobs report):")
    pred = engine.predict("nfp", surprise_sigma=-2.0, current_fed_watch=89, days_to_fomc=10)
    print(f"   Fed Watch: 89% → {pred.predicted_fed_watch:.1f}% ({pred.predicted_shift:+.1f}%)")
    print(f"   Direction: {pred.direction.value} (more cuts!)")
    print(f"   Confidence: {pred.confidence:.0%}")
    
    # Test NFP beat
    print("\n📊 If NFP BEATS by 2σ (strong jobs report):")
    pred = engine.predict("nfp", surprise_sigma=+2.0, current_fed_watch=89, days_to_fomc=10)
    print(f"   Fed Watch: 89% → {pred.predicted_fed_watch:.1f}% ({pred.predicted_shift:+.1f}%)")
    print(f"   Direction: {pred.direction.value} (fewer cuts!)")
    print(f"   Confidence: {pred.confidence:.0%}")
    
    # Test CPI
    print("\n📊 If CPI HOT (+1σ):")
    pred = engine.predict("cpi", surprise_sigma=+1.0, current_fed_watch=89, days_to_fomc=20)
    print(f"   Fed Watch: 89% → {pred.predicted_fed_watch:.1f}% ({pred.predicted_shift:+.1f}%)")
    print(f"   Confidence: {pred.confidence:.0%}")
    
    # Test CPI cool
    print("\n📊 If CPI COOL (-1σ):")
    pred = engine.predict("cpi", surprise_sigma=-1.0, current_fed_watch=89, days_to_fomc=20)
    print(f"   Fed Watch: 89% → {pred.predicted_fed_watch:.1f}% ({pred.predicted_shift:+.1f}%)")
    print(f"   Confidence: {pred.confidence:.0%}")
    
    print("\n" + "=" * 80)
    print("✅ THE BEAST IS READY FOR BATTLE!")
    print("=" * 80)
    
    # Summary
    stats = engine.db.get_stats()
    print(f"\n📊 FINAL STATS:")
    print(f"   Total releases in DB: {stats['total_releases']}")
    print(f"   With Fed Watch data: {stats['complete_releases']}")
    print(f"   Patterns learned: {stats['learned_patterns']}")
    
    return engine


if __name__ == "__main__":
    engine = train_the_beast()




