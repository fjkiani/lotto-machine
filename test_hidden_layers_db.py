import os
import sys
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

base_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_path)
load_dotenv()

from live_monitoring.agents.fed_officials.engine import FedOfficialsEngine

def run_tests():
    print("=" * 70)
    print("🕵️  TESTING END-TO-END HIDDEN LAYER ENGINE -> DB")
    print("=" * 70)
    
    engine = FedOfficialsEngine()
    
    print("\n1️⃣ Running fetch_hidden_layers()...")
    results = engine.fetch_hidden_layers()
    
    print("\n✅ Results:")
    print(f"Politician Trades Saved: {results['politicians_saved']}")
    print(f"Insider Trades Saved: {results['insiders_saved']}")

if __name__ == "__main__":
    run_tests()
