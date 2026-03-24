"""
🏛️ Atlanta Fed GDPNow — Real-Time GDP Tracker

Scrapes the Atlanta Fed GDPNow model estimate for current-quarter GDP.
Replaces stale FRED A191RL1Q225SBEA (quarterly lag).

Source: https://www.atlantafed.org/cqer/research/gdpnow
Updates: After each major data release (typically 6-7x per month)

Wire into:
  - macro_regime_detector as real-time GDP input
  - /brief/master as gdp_nowcast layer
  - PreSignalAlertEngine as GDP_PRESIGNAL alert
"""
import logging
import re
import requests
from datetime import datetime

logger = logging.getLogger(__name__)


class AtlantaFedGDPNow:
    """
    Scrapes the Atlanta Fed GDPNow real-time GDP tracking estimate.
    """

    URL = "https://www.atlantafed.org/cqer/research/gdpnow"
    GDP_CONSENSUS = 2.3  # Q1 2026 consensus estimate

    def get_estimate(self) -> dict:
        """
        Fetch current GDPNow estimate by scraping the public tracking page.

        Returns:
            {
                'gdp_estimate': 2.1,
                'as_of': '2026-03-23',
                'source': 'Atlanta Fed GDPNow',
                'consensus': 2.3,
                'vs_consensus': -0.2,
                'signal': 'MISS' | 'BEAT' | 'IN_LINE',
                'edge': 'GDPNow tracks Q1 at 2.1% vs consensus 2.3% → -0.2pp (MISS)'
            }
        """
        try:
            resp = requests.get(
                self.URL,
                timeout=15,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                                  "Chrome/120.0.0.0 Safari/537.36"
                },
            )
            resp.raise_for_status()
            text = resp.text

            # Try multiple regex patterns to extract the estimate
            estimate = None

            # Pattern 1: "GDPNow model estimate for real GDP growth ... is X.X percent"
            match = re.search(
                r"GDPNow\s+model\s+estimate.*?([+-]?\d+\.?\d*)\s*percent",
                text,
                re.IGNORECASE | re.DOTALL,
            )
            if match:
                estimate = float(match.group(1))

            # Pattern 2: "Latest estimate: X.X percent"
            if estimate is None:
                match = re.search(
                    r"Latest\s+estimate[:\s]+([+-]?\d+\.?\d*)\s*percent",
                    text,
                    re.IGNORECASE,
                )
                if match:
                    estimate = float(match.group(1))

            # Pattern 3: Look for a prominent percentage near "GDP"
            if estimate is None:
                match = re.search(
                    r"([+-]?\d+\.\d+)\s*percent.*?GDP",
                    text,
                    re.IGNORECASE,
                )
                if match:
                    estimate = float(match.group(1))

            # Pattern 4: JSON-LD or structured data
            if estimate is None:
                match = re.search(
                    r'"gdpNowEstimate"\s*:\s*"?([+-]?\d+\.?\d*)"?',
                    text,
                )
                if match:
                    estimate = float(match.group(1))

            if estimate is None:
                logger.warning("GDPNow: could not extract estimate from page")
                return {
                    "error": "Could not parse GDPNow estimate from page",
                    "source": "Atlanta Fed GDPNow",
                    "page_length": len(text),
                }

            # Extract date if available
            as_of = datetime.utcnow().date().isoformat()
            date_match = re.search(
                r"(?:as of|updated)\s+(\w+\s+\d{1,2},?\s+\d{4})",
                text,
                re.IGNORECASE,
            )
            if date_match:
                as_of = date_match.group(1)

            vs_consensus = round(estimate - self.GDP_CONSENSUS, 2)
            if estimate > self.GDP_CONSENSUS + 0.3:
                signal = "BEAT_LIKELY"
            elif estimate < self.GDP_CONSENSUS - 0.3:
                signal = "MISS_LIKELY"
            else:
                signal = "IN_LINE"

            sign = "+" if vs_consensus > 0 else ""
            return {
                "gdp_estimate": estimate,
                "as_of": as_of,
                "source": "Atlanta Fed GDPNow",
                "consensus": self.GDP_CONSENSUS,
                "vs_consensus": vs_consensus,
                "signal": signal,
                "edge": (
                    f"GDPNow tracks Q1 at {estimate}% vs consensus "
                    f"{self.GDP_CONSENSUS}% → {sign}{vs_consensus}pp ({signal})"
                ),
            }

        except Exception as e:
            logger.warning(f"GDPNow fetch failed: {e}")
            return {"error": str(e), "source": "Atlanta Fed GDPNow"}


# ─── Standalone Test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO)
    gdp = AtlantaFedGDPNow()
    result = gdp.get_estimate()
    print(json.dumps(result, indent=2))
