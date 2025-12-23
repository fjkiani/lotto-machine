"""
Trading Economics Credit Ratings Extractor
==========================================

Extracts credit ratings from Trading Economics API.
Tracks rating changes and calculates credit risk scores.
"""

import logging
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class TradingEconomicsCreditMonitor:
    """
    Monitor credit ratings from Trading Economics.
    
    Tracks ratings from multiple agencies:
    - Trading Economics (TE)
    - Standard & Poor's (SP)
    - Moody's
    - Fitch
    - DBRS
    """
    
    API_BASE_URL = "https://api.tradingeconomics.com/ratings"
    
    # Rating to score mapping (lower = riskier)
    RATING_SCORES = {
        'AAA': 1, 'AA+': 2, 'AA': 3, 'AA-': 4,
        'A+': 5, 'A': 6, 'A-': 7,
        'BBB+': 8, 'BBB': 9, 'BBB-': 10,
        'BB+': 11, 'BB': 12, 'BB-': 13,
        'B+': 14, 'B': 15, 'B-': 16,
        'CCC+': 17, 'CCC': 18, 'CCC-': 19,
        'CC': 20, 'C': 21, 'D': 22,
        # Moody's scale
        'Aaa': 1, 'Aa1': 2, 'Aa2': 3, 'Aa3': 4,
        'A1': 5, 'A2': 6, 'A3': 7,
        'Baa1': 8, 'Baa2': 9, 'Baa3': 10,
        'Ba1': 11, 'Ba2': 12, 'Ba3': 13,
        'B1': 14, 'B2': 15, 'B3': 16,
        'Caa1': 17, 'Caa2': 18, 'Caa3': 19,
        'Ca': 20, 'C': 21
    }
    
    def __init__(self, api_credentials: str = "guest:guest"):
        """
        Initialize credit monitor.
        
        Args:
            api_credentials: API credentials (format: "key:secret" or "guest:guest")
        """
        self.credentials = api_credentials
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Store historical ratings for change detection
        self.historical_ratings: Dict[str, Dict[str, Any]] = {}
        
        logger.info("✅ TradingEconomicsCreditMonitor initialized")
    
    def get_all_ratings(self) -> List[Dict[str, Any]]:
        """
        Get all credit ratings.
        
        Returns:
            List of credit ratings with agency data
        """
        params = {'c': self.credentials}
        
        try:
            response = self.session.get(self.API_BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching ratings: {e}")
            return []
    
    def get_country_rating(self, country: str) -> Optional[Dict[str, Any]]:
        """
        Get rating for specific country.
        
        Args:
            country: Country name (e.g., "United States", "Germany")
        
        Returns:
            Rating data or None if not found
        """
        all_ratings = self.get_all_ratings()
        
        for rating in all_ratings:
            if rating['Country'].lower() == country.lower():
                return rating
        
        return None
    
    def score_credit_risk(self, country: str) -> Optional[Dict[str, Any]]:
        """
        Score credit risk for a country.
        
        Args:
            country: Country name
        
        Returns:
            Dict with composite score, risk level, and ratings
        """
        rating = self.get_country_rating(country)
        if not rating:
            return None
        
        # Convert ratings to scores
        scores = []
        
        if rating.get('SP'):
            sp_score = self.RATING_SCORES.get(rating['SP'], 15)
            scores.append(sp_score)
        
        if rating.get('Moodys'):
            moodys_score = self.RATING_SCORES.get(rating['Moodys'], 15)
            scores.append(moodys_score)
        
        if rating.get('Fitch'):
            fitch_score = self.RATING_SCORES.get(rating['Fitch'], 15)
            scores.append(fitch_score)
        
        if rating.get('TE'):
            # TE uses numeric scale (lower = riskier)
            try:
                te_score = int(rating['TE']) / 10  # Normalize to 1-22 scale
                scores.append(te_score)
            except:
                pass
        
        composite_score = sum(scores) / len(scores) if scores else 15
        
        # Determine risk level
        if composite_score < 8:
            risk_level = 'LOW'
        elif composite_score < 15:
            risk_level = 'MEDIUM'
        else:
            risk_level = 'HIGH'
        
        return {
            'country': country,
            'composite_score': composite_score,
            'risk_level': risk_level,
            'ratings': rating,
            'outlook': rating.get('SP_Outlook') or rating.get('Moodys_Outlook', 'Unknown')
        }
    
    def detect_rating_changes(self) -> List[Dict[str, Any]]:
        """
        Detect rating changes since last check.
        
        Returns:
            List of rating changes
        """
        current_ratings = self.get_all_ratings()
        changes = []
        
        for rating in current_ratings:
            country = rating['Country']
            
            if country in self.historical_ratings:
                old = self.historical_ratings[country]
                
                # Check for S&P changes
                if rating.get('SP') != old.get('SP'):
                    changes.append({
                        'country': country,
                        'agency': 'S&P',
                        'old_rating': old.get('SP'),
                        'new_rating': rating.get('SP'),
                        'old_outlook': old.get('SP_Outlook'),
                        'new_outlook': rating.get('SP_Outlook'),
                        'change_type': 'RATING_CHANGE'
                    })
                
                # Check for Moody's changes
                if rating.get('Moodys') != old.get('Moodys'):
                    changes.append({
                        'country': country,
                        'agency': 'Moody\'s',
                        'old_rating': old.get('Moodys'),
                        'new_rating': rating.get('Moodys'),
                        'old_outlook': old.get('Moodys_Outlook'),
                        'new_outlook': rating.get('Moodys_Outlook'),
                        'change_type': 'RATING_CHANGE'
                    })
                
                # Check for outlook changes
                if rating.get('SP_Outlook') != old.get('SP_Outlook'):
                    changes.append({
                        'country': country,
                        'agency': 'S&P',
                        'old_outlook': old.get('SP_Outlook'),
                        'new_outlook': rating.get('SP_Outlook'),
                        'change_type': 'OUTLOOK_CHANGE'
                    })
        
        # Update historical
        self.historical_ratings = {r['Country']: r for r in current_ratings}
        
        return changes
    
    def get_major_countries_ratings(self) -> List[Dict[str, Any]]:
        """
        Get ratings for major countries.
        
        Returns:
            List of ratings for major economies
        """
        major_countries = [
            'United States', 'China', 'Japan', 'Germany', 'United Kingdom',
            'France', 'Italy', 'Canada', 'Australia', 'Brazil', 'India',
            'Russia', 'South Korea', 'Spain', 'Mexico'
        ]
        
        all_ratings = self.get_all_ratings()
        
        major_ratings = []
        for rating in all_ratings:
            if rating['Country'] in major_countries:
                major_ratings.append(rating)
        
        return major_ratings


# Test when run directly
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("📊 TESTING TRADING ECONOMICS CREDIT MONITOR")
    print("=" * 70)
    
    monitor = TradingEconomicsCreditMonitor()
    
    print("\n1️⃣ Testing: Get All Ratings")
    ratings = monitor.get_all_ratings()
    print(f"✅ Found {len(ratings)} country ratings")
    
    if ratings:
        print(f"\n📊 Sample Ratings:")
        for rating in ratings[:5]:
            print(f"   {rating['Country']}:")
            if rating.get('SP'):
                print(f"     S&P: {rating['SP']} ({rating.get('SP_Outlook', 'N/A')})")
            if rating.get('Moodys'):
                print(f"     Moody's: {rating['Moodys']} ({rating.get('Moodys_Outlook', 'N/A')})")
    
    print("\n2️⃣ Testing: Credit Risk Scoring")
    test_countries = ['United States', 'Germany', 'China']
    for country in test_countries:
        score = monitor.score_credit_risk(country)
        if score:
            print(f"   {country}: {score['risk_level']} risk (score: {score['composite_score']:.1f})")
        else:
            print(f"   {country}: Not found")
    
    print("\n" + "=" * 70)
    print("✅ CREDIT MONITOR TEST COMPLETE")





