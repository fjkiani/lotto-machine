"""
🤖 Diffbot Extractor
====================
Generic Diffbot wrapper for structured data extraction from any URL.
Perfect for turning messy web pages into clean JSON data.

Features:
- Article API for full text extraction (speeches, transcripts)
- Analyze API for auto-detection of page type  
- BS4 fallback for static HTML tables
- Exponential backoff on 429 rate limits (3 retries: 2s/4s/8s)
"""

import os
import time
import logging
import requests
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Retry config
MAX_RETRIES = 3
BACKOFF_BASE = 2  # seconds — exponential: 2s, 4s, 8s


def _request_with_retry(method: str, url: str, **kwargs) -> Optional[requests.Response]:
    """
    Wraps requests with exponential backoff on 429 (rate limit) and 5xx errors.
    Returns the response on success, or None after exhausting retries.
    """
    for attempt in range(MAX_RETRIES + 1):
        try:
            r = requests.request(method, url, **kwargs)

            if r.status_code == 200:
                return r

            if r.status_code == 429 or r.status_code >= 500:
                if attempt < MAX_RETRIES:
                    wait = BACKOFF_BASE ** (attempt + 1)  # 2, 4, 8
                    logger.warning(
                        f"Diffbot {r.status_code} on attempt {attempt + 1}/{MAX_RETRIES + 1}. "
                        f"Retrying in {wait}s..."
                    )
                    time.sleep(wait)
                    continue
                else:
                    logger.error(
                        f"Diffbot {r.status_code} — exhausted {MAX_RETRIES} retries for {url}"
                    )
                    return None
            else:
                # Non-retryable error (400, 401, 403, etc.)
                logger.error(f"Diffbot API error (Status {r.status_code}): {r.text[:200]}")
                return None

        except requests.exceptions.Timeout:
            if attempt < MAX_RETRIES:
                wait = BACKOFF_BASE ** (attempt + 1)
                logger.warning(f"Diffbot timeout on attempt {attempt + 1}. Retrying in {wait}s...")
                time.sleep(wait)
                continue
            else:
                logger.error(f"Diffbot timeout — exhausted retries for {url}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Diffbot request failed for {url}: {e}")
            return None

    return None


class DiffbotExtractor:
    """Wraps Diffbot API for structured data extraction."""
    
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("DIFFBOT_TOKEN")
        if not self.token:
            logger.warning("DIFFBOT_TOKEN not found in environment. Data extraction will fail.")
        self.base_url = "https://api.diffbot.com/v3"

    def extract_article(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Extracts article/speech data from a URL using the Article API.
        Returns a dict with clean text, speaker, title, date, and raw HTML.
        Retries on 429 with exponential backoff.
        """
        if not self.token:
            return None
            
        params = {
            "token": self.token,
            "url": url,
            "fields": "title,text,author,date,html"
        }
        
        r = _request_with_retry("GET", f"{self.base_url}/article", params=params, timeout=15)
        if r and r.status_code == 200:
            data = r.json().get("objects", [{}])[0]
            return {
                "speaker": data.get("author"),
                "title": data.get("title"),
                "date": data.get("date"),
                "full_text": data.get("text"),           # Clean transcript
                "raw_html": data.get("html")             # Fallback
            }
            
        return None
        
    def extract_analyze(self, url: str, js_timeout: int = 30000) -> Optional[Dict[str, Any]]:
        """
        Uses the Analyze API to automatically determine the page type
        and extract the appropriate data (e.g. for politician/insider trades).
        Retries on 429 with exponential backoff.
        """
        if not self.token:
            return None
            
        params = {
            "token": self.token,
            "url": url,
            "timeout": js_timeout
        }
        
        r = _request_with_retry("GET", f"{self.base_url}/analyze", params=params, timeout=40)
        if r and r.status_code == 200:
            return r.json().get("objects", [{}])[0]

        return None
        
    def extract_table_bs4(self, url: str, table_class: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fallback for pure static HTML tables (e.g. OpenInsider).
        Much faster and more reliable than JS-heavy extractors for simple sites.
        
        Normalizes non-breaking spaces and whitespace in column headers.
        """
        try:
            from bs4 import BeautifulSoup
            headers_req = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0 Safari/537.36"}
            r = requests.get(url, headers=headers_req, timeout=10)
            if r.status_code != 200:
                return []
                
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Find the target table
            if table_class:
                table = soup.find('table', class_=table_class)
            else:
                tables = soup.find_all('table')
                table = max(tables, key=lambda t: len(t.find_all('tr'))) if tables else None
                
            if not table:
                return []
                
            rows = []
            # Normalize headers: strip whitespace + replace non-breaking spaces
            col_headers = [
                th.text.strip().replace('\xa0', ' ')
                for th in table.find_all('th')
            ]
            
            for tr in table.find_all('tr'):
                cells = [td.text.strip() for td in tr.find_all('td')]
                if cells and len(cells) == len(col_headers):
                    row_dict = dict(zip(col_headers, cells))
                    rows.append(row_dict)
                elif cells:
                    # Fallback if headers mismatch
                    rows.append({f"col_{i}": cell for i, cell in enumerate(cells)})
                    
            return rows
        except Exception as e:
            logger.error(f"BS4 Fallback failed for {url}: {e}")
            return []
