"""
🧹 Trade Normalizers — Per-Source Parsing
==========================================
Each source (CapitolTrades, OpenInsider) has its own normalizer.
One method: normalize(raw_trade) → clean dict ready for DB save.

Verified against real scraper output (March 9 2026).
"""

import re
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class CapitolTradesNormalizer:
    """
    Normalizes raw CapitolTrades BS4 output into clean DB-ready dicts.

    Real columns (verified):
      'Politician':     'Byron DonaldsRepublicanHouseFL'
      'Traded Issuer':  'Brown & Brown IncBRO:US'
      'Owner':          'Spouse' | 'Undisclosed' | 'Joint' | 'Self'
      'Type':           'buy' | 'sell'
      'Size':           '1K–15K'
      'Traded':         '10 Feb2026'
      'Published':      '13:20Today'
    """

    # Regex for concatenated politician string
    _POL_PATTERN = re.compile(
        r'^(.+?)(Republican|Democrat|Independent)(House|Senate)([A-Z]{2})$'
    )
    # Regex for ticker extraction from "Brown & Brown IncBRO:US"
    _TICKER_PATTERN = re.compile(r'([A-Z]{1,5})(?::US)?$')

    def normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Convert raw CapitolTrades row → clean dict for DB."""
        pol_name, party, chamber, state = self._parse_politician(
            raw.get('Politician', 'Unknown')
        )
        ticker = self._extract_ticker(raw.get('Traded Issuer', ''))
        owner = raw.get('Owner', 'Self')

        clean = {
            "politician_name": f"{pol_name} ({party}-{state})" if state else pol_name,
            "ticker": ticker,
            "transaction_type": raw.get('Type', 'unknown'),
            "trade_size": raw.get('Size', '0'),
            "trade_date": raw.get('Traded', ''),
            "filing_date": raw.get('Published', ''),
            "url": "https://www.capitoltrades.com/trades",
            "owner": owner,
        }

        if owner.lower() == 'spouse':
            logger.warning(
                f"SPOUSE TRADE: {pol_name}'s spouse traded {ticker} "
                f"({raw.get('Type', '?')})"
            )

        return clean

    def _parse_politician(self, raw: str) -> Tuple[str, str, str, str]:
        """'Byron DonaldsRepublicanHouseFL' → ('Byron Donalds', 'R', 'House', 'FL')"""
        m = self._POL_PATTERN.match(raw)
        if m:
            return m.group(1).strip(), m.group(2)[0], m.group(3), m.group(4)
        return raw, '?', '', ''

    def _extract_ticker(self, raw_issuer: str) -> str:
        """'Brown & Brown IncBRO:US' → 'BRO'"""
        m = self._TICKER_PATTERN.search(raw_issuer)
        return m.group(1) if m else raw_issuer


class OpenInsiderNormalizer:
    """
    Normalizes raw OpenInsider BS4 output (cluster buys page) into clean DB-ready dicts.

    Real columns (verified):
      'X':              '' or 'M'
      'Filing Date':    '2026-03-09 16:32:46'
      'Trade Date':     '2026-03-09'
      'Ticker':         'HOG'
      'Company Name':   'Harley-Davidson, Inc.'
      'Industry':       'Motorcycles, Bicycles & Parts'
      'Ins':            '3'  (number of insiders in cluster, NOT a name)
      'Trade Type':     'P - Purchase' | 'S - Sale'
      'Price':          '$18.92'
      'Qty':            '+21,775'
      'Value':          '+$411,996'
    """

    def normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Convert raw OpenInsider row → clean dict for DB."""
        # Normalize non-breaking spaces in keys
        clean = {k.replace('\xa0', ' ').strip(): v for k, v in raw.items()}

        val_usd = self._parse_value(clean.get('Value', '0'))
        tx_type = self._parse_trade_type(clean.get('Trade Type', 'unknown'))

        company = clean.get('Company Name', 'Unknown')
        insider_count = clean.get('Ins', '1')

        return {
            "executive_name": f"{insider_count} insiders at {company}",
            "company": company,
            "ticker": clean.get('Ticker', 'UNKNOWN').strip(),
            "transaction_type": tx_type,
            "trade_value_usd": val_usd,
            "trade_date": clean.get('Trade Date', '').strip(),
            "filing_date": clean.get('Filing Date', '').strip(),
        }

    @staticmethod
    def _parse_value(raw: str) -> float:
        """'+$411,996' → 411996.0"""
        cleaned = raw.replace('$', '').replace('+', '').replace(',', '').strip()
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    @staticmethod
    def _parse_trade_type(raw: str) -> str:
        """'P - Purchase' → 'Purchase', 'S - Sale' → 'Sale'"""
        lower = raw.lower().strip()
        if 'p -' in lower or 'purchase' in lower:
            return 'Purchase'
        if 's -' in lower or 'sale' in lower:
            return 'Sale'
        return raw.strip() or 'unknown'
