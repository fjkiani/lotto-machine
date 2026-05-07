from datetime import datetime, timedelta
import logging
from .signal_schema import SignalResult

logger = logging.getLogger(__name__)

class OpexScorer:
    """
    Computes OPEX dynamics (Days to monthly OPEX, Pin Strike from GEX max_pain).
    """
    def _get_next_monthly_opex(self, from_date: datetime) -> datetime:
        # 3rd Friday of the month
        month = from_date.month
        year = from_date.year

        first_day = datetime(year, month, 1)
        first_friday = first_day + timedelta(days=((4 - first_day.weekday()) + 7) % 7)
        third_friday = first_friday + timedelta(days=14)

        if from_date.date() > third_friday.date():
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
            raw_data["next_opex_date"] = next_opex.strftime("%Y-%m-%d")

            # Pull real max_pain from GEX calculator
            try:
                from live_monitoring.enrichment.apis.gex_calculator import GEXCalculator
                gex_calc = GEXCalculator(cache_ttl=300)
                gex_result = gex_calc.compute_gex("SPY")
                if gex_result and gex_result.max_pain:
                    raw_data["pin_strike"] = round(gex_result.max_pain, 1)
                    raw_data["gamma_flip"] = round(gex_result.gamma_flip, 1) if gex_result.gamma_flip else None
            except Exception as _gex_e:
                logger.debug(f"OPEX: GEX max_pain fetch failed: {_gex_e}")

            if days_to_opex <= 3:
                pin = raw_data.get("pin_strike", "N/A")
                boost = 1
                reasons.append(
                    f"OPEX pinning window: {days_to_opex} days to {next_opex.strftime('%b %d')} OPEX. "
                    f"Max pain / pin strike: {pin}. Vol dampened near pin."
                )
            elif days_to_opex <= 7:
                reasons.append(
                    f"OPEX approaching: {days_to_opex} days out. "
                    f"Watch for gamma pinning near {raw_data.get('pin_strike', 'N/A')}."
                )

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
