import os
import sys
from dotenv import load_dotenv

# Setup paths
base_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_path)
load_dotenv()

from live_monitoring.enrichment.apis.diffbot_extractor import DiffbotExtractor
import feedparser
import json

def run_diffbot_test():
    print("=" * 70)
    print("🧪 TESTING DIFFBOT EXTRACTION FROM FED RSS")
    print("=" * 70)
    
    token = os.getenv("DIFFBOT_TOKEN")
    if not token:
        print("❌ ERROR: DIFFBOT_TOKEN not found in env.")
        return
        
    print(f"✅ Found Diffbot Token: {token[:6]}...")
    
    extractor = DiffbotExtractor(token=token)
    
    # Poll RSS feed for latest speeches
    url = "https://www.federalreserve.gov/feeds/speeches.xml"
    feed = feedparser.parse(url)
    if not feed.entries:
        print("⚠️ No entries found in RSS feed.")
        return
        
    latest_speech = feed.entries[0]
    print(f"📡 Latest RSS Entry: {latest_speech.title}")
    print(f"🔗 Link: {latest_speech.link}")
    
    print("-" * 70)
    print("🤖 Extracting clean transcript with Diffbot...")
    data = extractor.extract_article(latest_speech.link)
    
    if data:
        print(f"✅ Extracted Title: {data.get('title')}")
        print(f"✅ Extracted Speaker: {data.get('speaker')}")
        print(f"✅ Extracted Date: {data.get('date')}")
        
        full_text = data.get('full_text', '')
        print("\n📝 Transcript Preview:")
        print(full_text[:500] + "...\n")
        print(f"📊 Total length: {len(full_text)} chars")
    else:
        print("❌ Failed to extract data.")
        
    print("-" * 70)
    print("📅 Testing Calendar JSON...")
    import requests
    try:
        r = requests.get("https://www.federalreserve.gov/json/calendar.json", timeout=10)
        text = r.content.decode('utf-8-sig')
        cal_data = json.loads(text)
        print(f"✅ Calendar events parsed: {len(cal_data.get('events', []))}")
        if cal_data.get('events'):
            latest_evt = cal_data['events'][0]
            print(f"📝 First Event: {latest_evt.get('Date')} | {latest_evt.get('Speaker')} | {latest_evt.get('Title')}")
    except Exception as e:
        print(f"❌ Failed to test calendar: {e}")

if __name__ == "__main__":
    run_diffbot_test()
