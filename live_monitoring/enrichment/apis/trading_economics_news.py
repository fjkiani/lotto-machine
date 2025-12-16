"""
Trading Economics News Extractor
=================================

Extracts news articles from Trading Economics.
Supports both API (if key available) and web scraping (free).
"""

import logging
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
import time

logger = logging.getLogger(__name__)


class TradingEconomicsNewsExtractor:
    """
    Extract news from Trading Economics.
    
    Tries API first (if key available), falls back to web scraping.
    """
    
    API_BASE_URL = "https://api.tradingeconomics.com/news"
    WEB_BASE_URL = "https://tradingeconomics.com"
    NEWS_STREAM_URL = f"{WEB_BASE_URL}/stream"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize news extractor.
        
        Args:
            api_key: Trading Economics API key (format: "key:secret") or None for scraping
        """
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        if api_key:
            logger.info("✅ TradingEconomicsNewsExtractor initialized (API mode)")
        else:
            logger.info("✅ TradingEconomicsNewsExtractor initialized (Scraping mode)")
    
    def get_latest_news(
        self,
        limit: int = 50,
        news_type: Optional[str] = None,
        country: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get latest news articles.
        
        Args:
            limit: Maximum number of articles
            news_type: 'markets' or 'economy' (API only)
            country: Country name (e.g., "United States")
            start_date: Start date (YYYY-MM-DD) (API only)
            end_date: End date (YYYY-MM-DD) (API only)
        
        Returns:
            List of news articles
        """
        # Try API first if key available
        if self.api_key:
            try:
                return self._get_news_from_api(
                    limit=limit,
                    news_type=news_type,
                    country=country,
                    start_date=start_date,
                    end_date=end_date
                )
            except Exception as e:
                logger.warning(f"API failed, falling back to scraping: {e}")
        
        # Fallback to web scraping
        return self._get_news_from_scraping(limit=limit, country=country)
    
    def _get_news_from_api(
        self,
        limit: int = 50,
        news_type: Optional[str] = None,
        country: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch news from Trading Economics API"""
        params = {'c': self.api_key}
        
        if start_date:
            params['d1'] = start_date
        if end_date:
            params['d2'] = end_date
        if news_type:
            params['type'] = news_type
        if country:
            params['country'] = country.lower()
        
        response = self.session.get(self.API_BASE_URL, params=params, timeout=30)
        response.raise_for_status()
        
        articles = response.json()
        
        # Normalize API response
        normalized = []
        for article in articles[:limit]:
            normalized.append(self._normalize_api_article(article))
        
        logger.info(f"Fetched {len(normalized)} news articles from API")
        return normalized
    
    def _get_news_from_scraping(
        self,
        limit: int = 50,
        country: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Scrape news from Trading Economics website"""
        try:
            # Determine URL
            if country:
                country_slug = country.lower().replace(' ', '-')
                url = f"{self.WEB_BASE_URL}/{country_slug}/news"
            else:
                url = self.NEWS_STREAM_URL
            
            logger.info(f"Scraping news from: {url}")
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            articles = []
            
            # Try multiple selectors (site structure may vary)
            news_items = (
                soup.find_all('div', class_=lambda x: x and ('news' in str(x).lower() or 'article' in str(x).lower())) or
                soup.find_all('article') or
                soup.select('div[data-news-id]') or
                soup.find_all('div', {'class': 'te-news-item'}) or
                soup.find_all('div', {'class': 'news-item'})
            )
            
            # If no specific news containers, look for links with news patterns
            if not news_items:
                # Look for links to news articles
                all_links = soup.find_all('a', href=True)
                news_links = [link for link in all_links if '/news/' in link.get('href', '')]
                
                for link in news_links[:limit]:
                    article = self._parse_news_link(link)
                    if article:
                        articles.append(article)
            else:
                for item in news_items[:limit]:
                    article = self._parse_news_item(item)
                    if article:
                        articles.append(article)
            
            logger.info(f"Scraped {len(articles)} news articles")
            return articles[:limit]
            
        except Exception as e:
            logger.error(f"Error scraping news: {e}")
            return []
    
    def _parse_news_item(self, item) -> Optional[Dict[str, Any]]:
        """Parse a single news item from HTML"""
        try:
            # Extract title
            title_elem = (
                item.find('a', class_=lambda x: x and 'title' in str(x).lower()) or
                item.find('h2') or
                item.find('h3') or
                item.find('h4') or
                item.find('a', href=lambda x: x and '/news/' in str(x))
            )
            title = title_elem.get_text(strip=True) if title_elem else ''
            
            if not title:
                return None
            
            # Extract link
            link_elem = item.find('a', href=True)
            link = ''
            if link_elem:
                link = link_elem['href']
                if link and not link.startswith('http'):
                    link = f"{self.WEB_BASE_URL}{link}"
            elif title_elem and title_elem.name == 'a':
                link = title_elem.get('href', '')
                if link and not link.startswith('http'):
                    link = f"{self.WEB_BASE_URL}{link}"
            
            # Extract date
            date_elem = (
                item.find('time') or
                item.find('span', class_=lambda x: x and 'date' in str(x).lower()) or
                item.find('div', class_=lambda x: x and 'date' in str(x).lower())
            )
            date_str = date_elem.get_text(strip=True) if date_elem else ''
            
            # Extract description
            desc_elem = (
                item.find('p') or
                item.find('div', class_=lambda x: x and 'description' in str(x).lower()) or
                item.find('span', class_=lambda x: x and 'description' in str(x).lower())
            )
            description = desc_elem.get_text(strip=True) if desc_elem else ''
            
            # Extract country/category from tags or parent elements
            country = ''
            category = ''
            
            # Look for country/category in tags
            tags = item.find_all('a', class_=lambda x: x and 'tag' in str(x).lower())
            for tag in tags:
                tag_text = tag.get_text(strip=True)
                # Common countries
                if any(c in tag_text for c in ['United States', 'China', 'Japan', 'Germany', 
                                                'United Kingdom', 'France', 'Italy', 'Canada']):
                    country = tag_text
                else:
                    category = tag_text
            
            # Try to extract from URL
            if not country and link:
                url_parts = link.split('/')
                if len(url_parts) > 2:
                    potential_country = url_parts[-2]
                    if potential_country not in ['news', 'stream', 'calendar']:
                        country = potential_country.replace('-', ' ').title()
            
            return {
                'title': title,
                'url': link,
                'date': date_str,
                'description': description,
                'country': country,
                'category': category,
                'source': 'Trading Economics',
                'scraped_at': datetime.now().isoformat(),
                'method': 'scraping'
            }
            
        except Exception as e:
            logger.debug(f"Error parsing news item: {e}")
            return None
    
    def _parse_news_link(self, link) -> Optional[Dict[str, Any]]:
        """Parse news from a link element"""
        try:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            
            if not title or not href:
                return None
            
            if not href.startswith('http'):
                href = f"{self.WEB_BASE_URL}{href}"
            
            # Extract country from URL if possible
            country = ''
            if '/news/' in href:
                parts = href.split('/news/')[0].split('/')
                if parts:
                    country = parts[-1].replace('-', ' ').title()
            
            return {
                'title': title,
                'url': href,
                'date': '',
                'description': '',
                'country': country,
                'category': '',
                'source': 'Trading Economics',
                'scraped_at': datetime.now().isoformat(),
                'method': 'scraping'
            }
            
        except Exception as e:
            logger.debug(f"Error parsing news link: {e}")
            return None
    
    def _normalize_api_article(self, api_article: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize API article response"""
        return {
            'id': api_article.get('id', ''),
            'title': api_article.get('title', ''),
            'url': api_article.get('url', ''),
            'date': api_article.get('date', ''),
            'description': api_article.get('description', ''),
            'country': api_article.get('country', ''),
            'category': api_article.get('category', ''),
            'importance': api_article.get('importance', 0),
            'related_indicators': api_article.get('related_indicators', []),
            'source': api_article.get('source', 'Trading Economics'),
            'scraped_at': datetime.now().isoformat(),
            'method': 'api'
        }
    
    def get_news_by_country(self, country: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get news for a specific country.
        
        Args:
            country: Country name (e.g., "United States")
            limit: Maximum articles
        
        Returns:
            List of news articles
        """
        return self.get_latest_news(country=country, limit=limit)
    
    def get_market_news(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get market-related news.
        
        Args:
            limit: Maximum articles
        
        Returns:
            List of market news articles
        """
        return self.get_latest_news(news_type='markets', limit=limit)
    
    def get_economy_news(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get economy-related news.
        
        Args:
            limit: Maximum articles
        
        Returns:
            List of economy news articles
        """
        return self.get_latest_news(news_type='economy', limit=limit)


# Convenience function
def get_trading_economics_news(api_key: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
    """
    Get Trading Economics news.
    
    Args:
        api_key: Optional API key (uses scraping if not provided)
        **kwargs: Additional filters (limit, country, news_type, etc.)
    
    Returns:
        List of news articles
    """
    extractor = TradingEconomicsNewsExtractor(api_key=api_key)
    return extractor.get_latest_news(**kwargs)


# Test when run directly
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("📰 TESTING TRADING ECONOMICS NEWS EXTRACTOR")
    print("=" * 70)
    
    # Test without API key (scraping)
    extractor = TradingEconomicsNewsExtractor()
    
    print("\n1️⃣ Testing: Latest News (Scraping)")
    news = extractor.get_latest_news(limit=10)
    print(f"✅ Found {len(news)} articles")
    
    if news:
        print("\n📰 Sample Articles:")
        for i, article in enumerate(news[:5], 1):
            print(f"\n  {i}. {article.get('title', 'No title')}")
            if article.get('country'):
                print(f"     Country: {article['country']}")
            if article.get('url'):
                print(f"     URL: {article['url']}")
            if article.get('date'):
                print(f"     Date: {article['date']}")
    
    print("\n2️⃣ Testing: US News")
    us_news = extractor.get_news_by_country("United States", limit=5)
    print(f"✅ Found {len(us_news)} US articles")
    
    print("\n" + "=" * 70)
    print("✅ NEWS EXTRACTOR TEST COMPLETE")



