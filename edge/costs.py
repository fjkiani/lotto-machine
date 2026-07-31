"""
edge/costs.py — realistic round-trip cost model for SPY/QQQ equity trades.

Components (round trip, as % of notional):
  - half-spread x2   : SPY/QQQ are extremely liquid; ~0.01% half-spread
  - slippage         : market/limit fill uncertainty
  - fees/commission  : ~0 for modern brokers on liquid ETFs, small regulatory

We provide a conservative default and a stress case. All values in percent.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    name: str
    half_spread_pct: float
    slippage_pct: float
    fees_pct: float

    @property
    def round_trip_pct(self) -> float:
        # two sides (entry+exit): 2*(half_spread + slippage) + fees
        return 2.0 * (self.half_spread_pct + self.slippage_pct) + self.fees_pct


# Conservative base case for liquid ETFs
BASE = CostModel(name="base", half_spread_pct=0.005, slippage_pct=0.010, fees_pct=0.001)
#   round_trip = 2*(0.005+0.010)+0.001 = 0.031%

# Stress case (worse fills, fast market)
STRESS = CostModel(name="stress", half_spread_pct=0.010, slippage_pct=0.030, fees_pct=0.002)
#   round_trip = 2*(0.010+0.030)+0.002 = 0.082%

# Zero-cost floor (upper bound on any edge; if it fails here it fails everywhere)
ZERO = CostModel(name="zero", half_spread_pct=0.0, slippage_pct=0.0, fees_pct=0.0)
