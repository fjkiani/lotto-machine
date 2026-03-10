"""
📡 Fed RSS & Calendar Poller
=============================
Directly pulls Fed Speeches & Calendar events.
Uses Diffbot to extract clean JSON content from direct Federal Reserve links.
"""

import logging
import feedparser
import requests
from datetime import datetime
from typing import List, Dict, Any

from live_monitoring.enrichment.apis.diffbot_extractor import DiffbotExtractor
from live_monitoring.agents.fed_officials.database import FedOfficialsDatabase
from live_monitoring.agents.fed_officials.sentiment_analyzer import SentimentAnalyzer

logger = logging.getLogger(__name__)

class FedRSSCalendarPoller:
    """
    Polls Fed RSS feeds and Calendar APIs.
    Hooks extraction via Diffbot and routes to database and narrative engine.
    """
    
    def __init__(self, db: FedOfficialsDatabase, sentiment_analyzer: SentimentAnalyzer):
        self.db = db
        self.sentiment_analyzer = sentiment_analyzer
        self.extractor = DiffbotExtractor()
        
        # We can track the last parsed time to avoid duplicate parsing
        # (For this example we fetch all and let DB deduplicate via unique URLs/hashes)
        self.last_check = None 
        
        self.rss_urls = [
            "https://www.federalreserve.gov/feeds/speeches.xml",
            "https://www.federalreserve.gov/feeds/speeches_and_testimony.xml"
        ]
        self.calendar_url = "https://www.federalreserve.gov/json/calendar.json"

    def poll_speeches(self) -> List[Dict[str, Any]]:
        """
        Fetch the newest items from the RSS feed, extract via Diffbot,
        and analyze tone.
        """
        extracted_speeches = []
        for url in self.rss_urls:
            try:
                feed = feedparser.parse(url)
                
                # Fetch new entries. In a real persistent loop we filter by timestamp.
                # Here we just parse up to latest 3 for efficiency.
                for entry in feed.entries[:3]:
                    logger.info(f"📡 Found RSS Entry: {entry.title} - {entry.link}")
                    
                    # 1. Ask Diffbot for clean text
                    speech_data = self.extractor.extract_article(entry.link)
                    if speech_data and speech_data.get("full_text"):
                        
                        # 2. Tone Analysis
                        # Note: Our SentimentAnalyzer expects a string to process via LLM
                        # We pass the full_text or a chunk of it
                        text_chunk = speech_data["full_text"][:2000] # Pass first 2000 chars
                        speaker_name = speech_data.get("speaker") or "Fed Official"
                        sentiment, confidence, reasoning = self.sentiment_analyzer.analyze(text_chunk, speaker_name)
                        
                        logger.info(f"   🧠 Analyzed Tone: {sentiment} ({confidence:.0%}) - {speaker_name}")
                        
                        result = {
                            "source_url": entry.link,
                            "title": entry.title,
                            "speaker": speaker_name,
                            "date": speech_data.get("date"),
                            "full_text": speech_data["full_text"],
                            "sentiment": sentiment,
                            "sentiment_confidence": confidence,
                            "reasoning": reasoning
                        }
                        
                        extracted_speeches.append(result)
                        
                        # Note: In production, we store in self.db and wire to NarrativeEngine
                        
            except Exception as e:
                logger.error(f"Failed to poll speeches from {url}: {e}")
                
        return extracted_speeches

    def poll_calendar(self) -> List[Dict[str, Any]]:
        """
        Fetch upcoming FOMC and Fed events directly from the official calendar JSON.
        """
        events = []
        try:
            r = requests.get(self.calendar_url, timeout=10)
            if r.status_code == 200:
                import json
                text = r.content.decode('utf-8-sig')
                data = json.loads(text)
                # data["events"] contains a list of dicts with date, title, speaker, etc.
                for evt in data.get("events", [])[:5]:
                    event_data = {
                        "date": f"{evt.get('month', '')} {evt.get('days', '')} {evt.get('time', '')}".strip(),
                        "title": evt.get("title", ""),
                        "speaker": evt.get("description", "Unknown Speaker")[:50],  # Often embedded in description
                        "location": evt.get("location", "")
                    }
                    events.append(event_data)
                    logger.info(f"📅 Calendar Event: {event_data['date']} - {event_data['title']}")
        except Exception as e:
            logger.error(f"Failed to poll calendar: {e}")
            
        return events
