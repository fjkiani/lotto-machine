"""
Trading Economics Markets Data Extractor
========================================

Extracts market data from Trading Economics API:
- Commodities
- Currencies
- Stock Indices
- Bonds

Each asset has 34 data fields including prices, changes, and historical comparisons.
"""

import logging
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional
import time

logger = logging.getLogger(__name__)


class TradingEconomicsMarketsClient:
    """
    Extract market data from Trading Economics API.
    
    Supports: Commodities, Currencies, Indices, Bonds
    Each endpoint returns 34 fields per asset.
    """
    
    API_BASE_URL = "https://api.tradingeconomics.com"
    
    def __init__(self, api_credentials: str = "guest:guest"):
        """
        Initialize markets client.
        
        Args:
            api_credentials: API credentials (format: "key:secret" or "guest:guest")
        """
        self.credentials = api_credentials
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        logger.info("✅ TradingEconomicsMarketsClient initialized")
    
    def get_commodities(self) -> List[Dict[str, Any]]:
        """
        Get commodity market data.
        
        Returns:
            List of commodities with 34 fields each
        """
        url = f"{self.API_BASE_URL}/markets/commodities"
        params = {'c': self.credentials}
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching commodities: {e}")
            return []
    
    def get_currencies(self) -> List[Dict[str, Any]]:
        """
        Get currency pair market data.
        
        Returns:
            List of currency pairs with 34 fields each
        """
        url = f"{self.API_BASE_URL}/markets/currency"
        params = {'c': self.credentials}
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching currencies: {e}")
            return []
    
    def get_indices(self) -> List[Dict[str, Any]]:
        """
        Get stock index market data.
        
        Returns:
            List of stock indices with 34 fields each
        """
        url = f"{self.API_BASE_URL}/markets/index"
        params = {'c': self.credentials}
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching indices: {e}")
            return []
    
    def get_bonds(self) -> List[Dict[str, Any]]:
        """
        Get bond yield market data.
        
        Returns:
            List of bonds with 34 fields each
        """
        url = f"{self.API_BASE_URL}/markets/bond"
        params = {'c': self.credentials}
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching bonds: {e}")
            return []
    
    def get_all_markets(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all market data (commodities, currencies, indices, bonds).
        
        Returns:
            Dictionary with keys: commodities, currencies, indices, bonds
        """
        return {
            'commodities': self.get_commodities(),
            'currencies': self.get_currencies(),
            'indices': self.get_indices(),
            'bonds': self.get_bonds()
        }
    
    def find_asset(self, symbol: str, asset_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Find a specific asset by symbol.
        
        Args:
            symbol: Asset symbol (e.g., "SPX", "EURUSD", "GC1")
            asset_type: Optional asset type filter (commodities, currencies, indices, bonds)
        
        Returns:
            Asset data or None if not found
        """
        if asset_type:
            markets = {asset_type: getattr(self, f'get_{asset_type}')()}
        else:
            markets = self.get_all_markets()
        
        for asset_class, assets in markets.items():
            for asset in assets:
                if asset.get('Symbol', '').upper() == symbol.upper() or \
                   asset.get('Ticker', '').upper() == symbol.upper():
                    return asset
        
        return None
    
    def get_market_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics for all markets.
        
        Returns:
            Summary statistics
        """
        all_markets = self.get_all_markets()
        
        summary = {}
        
        for asset_class, assets in all_markets.items():
            if not assets:
                continue
            
            # Calculate aggregate statistics
            daily_changes = [a.get('DailyPercentualChange', 0) for a in assets if a.get('DailyPercentualChange')]
            weekly_changes = [a.get('WeeklyPercentualChange', 0) for a in assets if a.get('WeeklyPercentualChange')]
            
            summary[asset_class] = {
                'count': len(assets),
                'avg_daily_change': sum(daily_changes) / len(daily_changes) if daily_changes else 0,
                'avg_weekly_change': sum(weekly_changes) / len(weekly_changes) if weekly_changes else 0,
                'positive_daily': sum(1 for c in daily_changes if c > 0),
                'negative_daily': sum(1 for c in daily_changes if c < 0),
            }
        
        return summary


class MarketRegimeDetector:
    """
    Detect market regimes from Trading Economics market data.
    
    Regimes:
    - RISK_ON: Risk assets up, safe havens down
    - RISK_OFF: Risk assets down, safe havens up
    - INFLATION_FEAR: Commodities up, bonds down
    - DEFLATION_WORRY: Commodities down, bonds up
    """
    
    def __init__(self, markets_client: TradingEconomicsMarketsClient):
        self.markets = markets_client
    
    def detect_regime(self) -> Dict[str, Any]:
        """
        Detect current market regime.
        
        Returns:
            Dict with regime, confidence, and indicators
        """
        all_markets = self.markets.get_all_markets()
        
        # Calculate trends
        commodity_trend = self._calculate_trend(all_markets['commodities'])
        bond_trend = self._calculate_trend(all_markets['bonds'])
        index_trend = self._calculate_trend(all_markets['indices'])
        currency_trend = self._calculate_trend(all_markets['currencies'])
        
        # Classify regime
        if commodity_trend > 0.5 and bond_trend < -0.1 and index_trend > 0.5:
            regime = 'RISK_ON'
            confidence = 0.75
        elif commodity_trend < -0.5 and bond_trend > 0.1 and index_trend < -0.5:
            regime = 'RISK_OFF'
            confidence = 0.75
        elif commodity_trend > 0.5 and bond_trend < -0.1:
            regime = 'INFLATION_FEAR'
            confidence = 0.70
        elif commodity_trend < -0.5 and bond_trend > 0.1:
            regime = 'DEFLATION_WORRY'
            confidence = 0.70
        else:
            regime = 'NEUTRAL'
            confidence = 0.50
        
        return {
            'regime': regime,
            'confidence': confidence,
            'indicators': {
                'commodities': commodity_trend,
                'bonds': bond_trend,
                'indices': index_trend,
                'currencies': currency_trend
            },
            'timestamp': datetime.now().isoformat()
        }
    
    def _calculate_trend(self, assets: List[Dict[str, Any]]) -> float:
        """Calculate aggregate trend from asset list"""
        if not assets:
            return 0.0
        
        changes = [
            a.get('DailyPercentualChange', 0) 
            for a in assets 
            if a.get('DailyPercentualChange') is not None
        ]
        
        return sum(changes) / len(changes) if changes else 0.0


class CrossAssetCorrelationEngine:
    """
    Calculate correlations between Trading Economics assets.
    """
    
    def __init__(self, markets_client: TradingEconomicsMarketsClient):
        self.markets = markets_client
    
    def calculate_correlations(self) -> Dict[str, float]:
        """
        Calculate correlations between asset classes.
        
        Returns:
            Dictionary of correlation coefficients
        """
        all_markets = self.markets.get_all_markets()
        
        correlations = {}
        
        # Commodities vs Indices
        if all_markets['commodities'] and all_markets['indices']:
            comm_changes = [
                c.get('DailyPercentualChange', 0) 
                for c in all_markets['commodities']
                if c.get('DailyPercentualChange') is not None
            ]
            idx_changes = [
                i.get('DailyPercentualChange', 0) 
                for i in all_markets['indices']
                if i.get('DailyPercentualChange') is not None
            ]
            
            if len(comm_changes) > 0 and len(idx_changes) > 0:
                # Use minimum length
                min_len = min(len(comm_changes), len(idx_changes))
                corr = self._pearson_correlation(
                    comm_changes[:min_len],
                    idx_changes[:min_len]
                )
                correlations['commodities_vs_indices'] = corr
        
        # Bonds vs Indices (inverse correlation expected)
        if all_markets['bonds'] and all_markets['indices']:
            bond_changes = [
                b.get('DailyPercentualChange', 0) 
                for b in all_markets['bonds']
                if b.get('DailyPercentualChange') is not None
            ]
            idx_changes = [
                i.get('DailyPercentualChange', 0) 
                for i in all_markets['indices']
                if i.get('DailyPercentualChange') is not None
            ]
            
            if len(bond_changes) > 0 and len(idx_changes) > 0:
                min_len = min(len(bond_changes), len(idx_changes))
                corr = self._pearson_correlation(
                    bond_changes[:min_len],
                    idx_changes[:min_len]
                )
                correlations['bonds_vs_indices'] = corr
        
        return correlations
    
    def _pearson_correlation(self, x: List[float], y: List[float]) -> float:
        """Calculate Pearson correlation coefficient"""
        try:
            import numpy as np
            
            if len(x) != len(y) or len(x) < 2:
                return 0.0
            
            x_arr = np.array(x)
            y_arr = np.array(y)
            
            return float(np.corrcoef(x_arr, y_arr)[0, 1])
        except:
            # Fallback to simple correlation
            if len(x) != len(y) or len(x) < 2:
                return 0.0
            
            x_mean = sum(x) / len(x)
            y_mean = sum(y) / len(y)
            
            numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(len(x)))
            x_var = sum((x[i] - x_mean) ** 2 for i in range(len(x)))
            y_var = sum((y[i] - y_mean) ** 2 for i in range(len(y)))
            
            denominator = (x_var * y_var) ** 0.5
            
            return numerator / denominator if denominator > 0 else 0.0


# Test when run directly
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("📊 TESTING TRADING ECONOMICS MARKETS CLIENT")
    print("=" * 70)
    
    client = TradingEconomicsMarketsClient()
    
    print("\n1️⃣ Testing: Commodities")
    commodities = client.get_commodities()
    print(f"✅ Found {len(commodities)} commodities")
    if commodities:
        print(f"   Sample: {commodities[0].get('Name')} - {commodities[0].get('Last')}")
    
    print("\n2️⃣ Testing: Currencies")
    currencies = client.get_currencies()
    print(f"✅ Found {len(currencies)} currency pairs")
    if currencies:
        print(f"   Sample: {currencies[0].get('Name')} - {currencies[0].get('Last')}")
    
    print("\n3️⃣ Testing: Stock Indices")
    indices = client.get_indices()
    print(f"✅ Found {len(indices)} indices")
    if indices:
        print(f"   Sample: {indices[0].get('Name')} - {indices[0].get('Last')}")
    
    print("\n4️⃣ Testing: Bonds")
    bonds = client.get_bonds()
    print(f"✅ Found {len(bonds)} bonds")
    if bonds:
        print(f"   Sample: {bonds[0].get('Name')} - {bonds[0].get('Last')}")
    
    print("\n5️⃣ Testing: Market Regime Detection")
    regime_detector = MarketRegimeDetector(client)
    regime = regime_detector.detect_regime()
    print(f"✅ Current Regime: {regime['regime']} (confidence: {regime['confidence']:.0%})")
    print(f"   Indicators: {regime['indicators']}")
    
    print("\n6️⃣ Testing: Cross-Asset Correlations")
    correlation_engine = CrossAssetCorrelationEngine(client)
    correlations = correlation_engine.calculate_correlations()
    print(f"✅ Correlations calculated:")
    for pair, corr in correlations.items():
        print(f"   {pair}: {corr:.3f}")
    
    print("\n" + "=" * 70)
    print("✅ MARKETS CLIENT TEST COMPLETE")


