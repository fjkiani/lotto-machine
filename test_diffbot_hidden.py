import os
import sys
from dotenv import load_dotenv

base_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_path)
load_dotenv()

from live_monitoring.agents.hidden_layers.politician_monitor import PoliticianMonitor
from live_monitoring.agents.hidden_layers.insider_monitor import InsiderMonitor

def run_tests():
    print("=" * 70)
    print("🕵️  TESTING DIFFBOT HIDDEN LAYER EXTRACTORS")
    print("=" * 70)
    
    print("\n1️⃣ Testing Politician Monitor (CapitolTrades Pelosi Profile)...")
    pol_monitor = PoliticianMonitor()
    pol_monitor.trade_sources = [
        "https://www.capitoltrades.com/politicians/P000197", # Nancy Pelosi
        "https://www.quiverquant.com/congresstrading/politician/Nancy%20Pelosi-P000197"
    ]
    pol_trades = pol_monitor.poll_latest_trades()
    
    print(f"✅ Extracted {len(pol_trades)} congressional trades!")
    if pol_trades:
        print("📝 Sample Trade Row:")
        print(pol_trades[0])
        
    print("\n2️⃣ Testing Insider Monitor (OpenInsider Homepage)...")
    ins_monitor = InsiderMonitor()
    ins_monitor.insider_sources = ["http://openinsider.com/"]
    ins_trades = ins_monitor.poll_latest_trades()
    
    print(f"✅ Extracted {len(ins_trades)} insider trades!")
    if ins_trades:
        print("📝 Sample Trade Row:")
        print(ins_trades[0])

if __name__ == "__main__":
    run_tests()
