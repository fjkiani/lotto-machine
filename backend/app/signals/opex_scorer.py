from datetime import datetime, timedelta
import logging
from .signal_schema import SignalResult

logger = logging.getLogger(__name__)

class OpexScorer:
    """
    Computes OPEX dynamics (Days to monthly OPEX, Pin Strike proximity).
    """
    def _get_next_monthly_opex(self, from_date: datetime) -> datetime:
        # 3rd Friday of the month
        month = from_date.month
        year = from_date.year
        
        # Find 1st of month
        first_day = datetime(year, month, 1)
        # Find first Friday
        first_friday = first_day + timedelta(days=((4 - first_day.weekday()) + 7) % 7)
        # 3rd Friday
        third_friday = first_friday + timedelta(days=14)
        
        if from_date.date() > third_friday.date():
            # Roll to next month
            month += 1
            if month > 12:
                month = 1
                year += 1
            first_day = datetime(year, month, 1)
            first_friday = first_day + timedelta(days=((4 - first_day.weekday()) + 7) % 7)
            third_friday = first_friday + timedelta(days=14)
            
        return third_friday

    def evaluate(self) -> SignalResult:
        now = datetime.now()
        now_iso = now.isoformat()
        today_str = now.strftime("%Y-%m-%d")
        
        boost = 0
        reasons = []
        raw_data = {"days_to_opex": None, "pin_strike": None}
        
        try:
            next_opex = self._get_next_monthly_opex(now)
            days_to_opex = (next_opex.date() - now.date()).days
            raw_data["days_to_opex"] = days_to_opex
            
            # Simulated Pin Strike (would come from GEX max pain)
            raw_data["pin_strike"] = 6000 
            
            if days_to_opex <= 3:
                boost = 1
                reasons.append(f"OPEX Pinning window active ({days_to_opex} days out). Volatility dampened near {raw_data['pin_strike']}.")
        except Exception as e:
            logger.warning(f"OPEX module failed: {e}")

        slug = f"opex-{raw_data.get('days_to_opex', 'unk')}dte-{today_str}"

        return SignalResult(
            name="OPEX",
            slug=slug,
            boost=boost,
            active=(boost > 0),
            timestamp=now_iso,
            source_date=today_str,
            raw=raw_data,
            reasons=reasons
        )
