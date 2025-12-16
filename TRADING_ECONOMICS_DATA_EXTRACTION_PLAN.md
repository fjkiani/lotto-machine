# 🚀 TRADING ECONOMICS - COMPREHENSIVE DATA EXTRACTION PLAN

**Goal:** Extract news, markets, indicators, and other data from Trading Economics  
**Status:** 📋 **PLANNING PHASE**

---

## 📊 AVAILABLE DATA SOURCES

### **1. Economic Calendar** ✅ (Already Implemented)
- **Endpoint:** `https://api.tradingeconomics.com/calendar`
- **Access:** Public (`guest:guest`)
- **Status:** ✅ Working
- **Data:** 23 fields per event

### **2. News Articles** ⚠️ (Requires API Key)
- **Endpoint:** `https://api.tradingeconomics.com/news`
- **Access:** Requires API key subscription
- **Status:** ⚠️ Needs authentication
- **Alternative:** Web scraping

### **3. Market Data** ✅ (Public Access)
- **Endpoints:**
  - Markets: `https://api.tradingeconomics.com/markets`
  - Commodities: `https://api.tradingeconomics.com/markets/commodities`
  - Currencies: `https://api.tradingeconomics.com/markets/currency`
  - Stocks: `https://api.tradingeconomics.com/markets/index`
  - Bonds: `https://api.tradingeconomics.com/markets/bond`
- **Access:** Public (`guest:guest`)
- **Status:** ⏳ Not yet implemented

### **4. Economic Indicators** ✅ (Public Access)
- **Endpoint:** `https://api.tradingeconomics.com/indicators`
- **Access:** Public (`guest:guest`)
- **Status:** ⏳ Not yet implemented

### **5. Forecasts** ⚠️ (May Require API Key)
- **Endpoint:** `https://api.tradingeconomics.com/forecasts`
- **Access:** Unknown (needs testing)
- **Status:** ⏳ Not yet implemented

---

## 🎯 NEWS EXTRACTION STRATEGIES

### **Strategy 1: API Access (Preferred - If You Have Key)**

**Pros:**
- ✅ Structured JSON data
- ✅ Real-time updates
- ✅ WebSocket streaming available
- ✅ Filtering by date, type, country
- ✅ No parsing needed

**Cons:**
- ❌ Requires paid API subscription
- ❌ Rate limits may apply

**Implementation:**
```python
import requests

def get_trading_economics_news(api_key: str, **filters):
    """
    Fetch news from Trading Economics API.
    
    Args:
        api_key: Your API key (format: "key:secret")
        filters: Optional filters (d1, d2, type, country, etc.)
    
    Returns:
        List of news articles
    """
    url = "https://api.tradingeconomics.com/news"
    params = {'c': api_key}
    
    # Add filters
    if 'start_date' in filters:
        params['d1'] = filters['start_date']
    if 'end_date' in filters:
        params['d2'] = filters['end_date']
    if 'news_type' in filters:
        params['type'] = filters['news_type']  # 'markets' or 'economy'
    if 'country' in filters:
        params['country'] = filters['country']
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    
    return response.json()
```

**News Article Structure (from API):**
```json
{
  "id": 12345,
  "title": "US Inflation Rises to 2.4%",
  "date": "2025-12-10T10:30:00",
  "description": "US inflation rate increased to 2.4% in November...",
  "country": "United States",
  "category": "inflation",
  "url": "https://tradingeconomics.com/united-states/news/...",
  "importance": 3,
  "related_indicators": ["CPI", "PCE"],
  "source": "Trading Economics"
}
```

---

### **Strategy 2: Web Scraping (Free Alternative)**

**Pros:**
- ✅ No API key needed
- ✅ Free access
- ✅ Can extract all visible news

**Cons:**
- ❌ HTML parsing required
- ❌ May break if site structure changes
- ❌ Rate limiting/blocking risk
- ❌ Less structured data

**Implementation:**
```python
from bs4 import BeautifulSoup
import requests
from datetime import datetime
from typing import List, Dict, Any

class TradingEconomicsNewsScraper:
    """Scrape news from Trading Economics website"""
    
    BASE_URL = "https://tradingeconomics.com"
    NEWS_URL = f"{BASE_URL}/stream"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_latest_news(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrape latest news from Trading Economics.
        
        Args:
            limit: Maximum number of articles to fetch
        
        Returns:
            List of news articles
        """
        try:
            response = self.session.get(self.NEWS_URL, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            articles = []
            
            # Find news articles (structure may vary)
            # Look for article containers
            news_items = soup.find_all('div', class_=lambda x: x and 'news' in x.lower()) or \
                        soup.find_all('article') or \
                        soup.select('div[data-news-id]')
            
            for item in news_items[:limit]:
                article = self._parse_news_item(item)
                if article:
                    articles.append(article)
            
            return articles
            
        except Exception as e:
            logger.error(f"Error scraping news: {e}")
            return []
    
    def _parse_news_item(self, item) -> Optional[Dict[str, Any]]:
        """Parse a single news item from HTML"""
        try:
            # Extract title
            title_elem = item.find('a', class_=lambda x: x and 'title' in x.lower()) or \
                        item.find('h2') or \
                        item.find('h3')
            title = title_elem.get_text(strip=True) if title_elem else ''
            
            # Extract link
            link_elem = item.find('a', href=True)
            link = link_elem['href'] if link_elem else ''
            if link and not link.startswith('http'):
                link = f"{self.BASE_URL}{link}"
            
            # Extract date
            date_elem = item.find('time') or \
                       item.find('span', class_=lambda x: x and 'date' in x.lower())
            date_str = date_elem.get_text(strip=True) if date_elem else ''
            
            # Extract description
            desc_elem = item.find('p') or \
                       item.find('div', class_=lambda x: x and 'description' in x.lower())
            description = desc_elem.get_text(strip=True) if desc_elem else ''
            
            # Extract country/category
            country = ''
            category = ''
            tags = item.find_all('a', class_=lambda x: x and 'tag' in x.lower())
            for tag in tags:
                tag_text = tag.get_text(strip=True)
                if tag_text in ['United States', 'China', 'Japan', 'Germany', etc.]:
                    country = tag_text
                else:
                    category = tag_text
            
            return {
                'title': title,
                'url': link,
                'date': date_str,
                'description': description,
                'country': country,
                'category': category,
                'source': 'Trading Economics',
                'scraped_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.debug(f"Error parsing news item: {e}")
            return None
    
    def get_news_by_country(self, country: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get news for a specific country.
        
        Args:
            country: Country name (e.g., "United States")
            limit: Maximum articles
        
        Returns:
            List of news articles
        """
        # Country-specific news URL
        country_slug = country.lower().replace(' ', '-')
        url = f"{self.BASE_URL}/{country_slug}/news"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            articles = []
            
            # Parse news items (same logic as get_latest_news)
            news_items = soup.find_all('div', class_=lambda x: x and 'news' in x.lower())
            
            for item in news_items[:limit]:
                article = self._parse_news_item(item)
                if article:
                    article['country'] = country
                    articles.append(article)
            
            return articles
            
        except Exception as e:
            logger.error(f"Error fetching country news: {e}")
            return []
```

---

### **Strategy 3: RSS Feeds (If Available)**

**Check for RSS:**
```bash
curl -s "https://tradingeconomics.com/stream/rss"
curl -s "https://tradingeconomics.com/united-states/news/rss"
```

**If RSS exists:**
```python
import feedparser

def get_news_from_rss(country: str = None):
    """Parse Trading Economics RSS feed"""
    if country:
        url = f"https://tradingeconomics.com/{country.lower().replace(' ', '-')}/news/rss"
    else:
        url = "https://tradingeconomics.com/stream/rss"
    
    feed = feedparser.parse(url)
    
    articles = []
    for entry in feed.entries:
        articles.append({
            'title': entry.title,
            'url': entry.link,
            'date': entry.published,
            'description': entry.summary,
            'source': 'Trading Economics RSS'
        })
    
    return articles
```

---

## 📈 OTHER DATA SOURCES TO EXTRACT

### **1. Market Data** (Public API)

**Endpoints:**
```python
# All markets
GET https://api.tradingeconomics.com/markets?c=guest:guest

# Commodities
GET https://api.tradingeconomics.com/markets/commodities?c=guest:guest

# Currencies
GET https://api.tradingeconomics.com/markets/currency?c=guest:guest

# Stock indices
GET https://api.tradingeconomics.com/markets/index?c=guest:guest

# Bonds
GET https://api.tradingeconomics.com/markets/bond?c=guest:guest
```

**Implementation:**
```python
def get_market_data(market_type: str = "all"):
    """Get market data from Trading Economics API"""
    url = f"https://api.tradingeconomics.com/markets"
    if market_type != "all":
        url += f"/{market_type}"
    
    params = {'c': 'guest:guest'}
    response = requests.get(url, params=params)
    return response.json()
```

**Data Structure:**
```json
{
  "Symbol": "SPX",
  "Ticker": "SPX",
  "Name": "S&P 500",
  "Country": "United States",
  "Date": "2025-12-10T16:00:00",
  "Value": 4750.25,
  "Change": 12.5,
  "ChangePercent": 0.26,
  "High": 4760.00,
  "Low": 4740.00,
  "Volume": 4500000000
}
```

---

### **2. Economic Indicators** (Public API)

**Endpoint:**
```python
GET https://api.tradingeconomics.com/indicators?c=guest:guest&s=united states
```

**Implementation:**
```python
def get_economic_indicators(country: str = "united states"):
    """Get economic indicators for a country"""
    url = "https://api.tradingeconomics.com/indicators"
    params = {
        'c': 'guest:guest',
        's': country
    }
    response = requests.get(url, params=params)
    return response.json()
```

---

### **3. Forecasts** (May Require Key)

**Endpoint:**
```python
GET https://api.tradingeconomics.com/forecasts?c=guest:guest
```

**Test if public:**
```python
def test_forecasts_access():
    """Test if forecasts endpoint is publicly accessible"""
    url = "https://api.tradingeconomics.com/forecasts"
    params = {'c': 'guest:guest'}
    response = requests.get(url, params=params)
    return response.status_code == 200
```

---

## 🛠️ IMPLEMENTATION PLAN

### **Phase 1: News Extraction (Priority)**

**Option A: If You Have API Key**
1. ✅ Create `TradingEconomicsNewsAPI` class
2. ✅ Implement news fetching with filters
3. ✅ Add WebSocket streaming support
4. ✅ Integrate with existing wrapper

**Option B: If No API Key (Web Scraping)**
1. ✅ Create `TradingEconomicsNewsScraper` class
2. ✅ Implement HTML parsing
3. ✅ Add country-specific news extraction
4. ✅ Add caching to avoid rate limits
5. ✅ Add error handling for structure changes

**Option C: Hybrid Approach**
1. ✅ Try API first (if key available)
2. ✅ Fallback to web scraping
3. ✅ Best of both worlds

---

### **Phase 2: Market Data Integration**

1. ⏳ Create `TradingEconomicsMarkets` class
2. ⏳ Implement market data fetching
3. ⏳ Add real-time price tracking
4. ⏳ Integrate with signal generation

---

### **Phase 3: Indicators & Forecasts**

1. ⏳ Create `TradingEconomicsIndicators` class
2. ⏳ Test forecasts endpoint access
3. ⏳ Implement historical data fetching
4. ⏳ Build correlation models

---

## 📋 RECOMMENDED APPROACH

### **For News (Immediate):**

**1. Check if you have API key:**
```python
# Test API access
response = requests.get(
    "https://api.tradingeconomics.com/news",
    params={'c': 'YOUR_API_KEY'}
)
if response.status_code == 200:
    # Use API
else:
    # Use web scraping
```

**2. Implement hybrid solution:**
- Try API first
- Fallback to web scraping
- Cache results
- Rate limit protection

**3. Create unified interface:**
```python
class TradingEconomicsDataExtractor:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.news_api = TradingEconomicsNewsAPI(api_key) if api_key else None
        self.news_scraper = TradingEconomicsNewsScraper()
    
    def get_news(self, **filters):
        """Get news - tries API first, falls back to scraping"""
        if self.news_api:
            try:
                return self.news_api.get_news(**filters)
            except:
                logger.warning("API failed, using scraper")
        
        return self.news_scraper.get_latest_news(**filters)
```

---

## 🔥 EXPLOITATION OPPORTUNITIES

### **1. News Sentiment Analysis**
- Extract news articles
- Run sentiment analysis (LLM)
- Correlate with market moves
- Trade on sentiment shifts

### **2. News Event Correlation**
- Link news to economic calendar events
- Track news impact on markets
- Build news-to-price models

### **3. Real-Time News Alerts**
- Monitor news stream
- Alert on high-impact news
- Auto-trade on breaking news

### **4. Market Data Integration**
- Combine news + market data
- Multi-factor signal generation
- Enhanced edge detection

---

## 📊 NEXT STEPS

### **Immediate:**
1. ⏳ **Test news API access** (check if you have key)
2. ⏳ **Implement news scraper** (if no key)
3. ⏳ **Create unified news interface**

### **Short-term:**
4. ⏳ **Add market data extraction**
5. ⏳ **Add indicators extraction**
6. ⏳ **Integrate with signal generation**

### **Medium-term:**
7. ⏳ **Build news sentiment analysis**
8. ⏳ **Create news-to-market correlation models**
9. ⏳ **Implement real-time news streaming**

---

## 💡 KEY INSIGHTS

1. **News API requires key** - But web scraping is free alternative
2. **Market data is public** - Can extract immediately
3. **Hybrid approach best** - API when available, scraping as fallback
4. **News + Calendar = Powerful** - Combine for edge

---

**STATUS: READY TO IMPLEMENT - CHOOSE STRATEGY BASED ON API KEY AVAILABILITY** 🎯⚡💰



