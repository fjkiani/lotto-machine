"""
Run ALL backtests.
Usage: python -m backtests.run_all

Or run individual:
  python -m backtests.bt_dp_divergence
  python -m backtests.bt_dp_trend
  python -m backtests.bt_selloff_rally
  python -m backtests.bt_squeeze
  python -m backtests.bt_options_flow
"""
from backtests import bt_dp_divergence, bt_dp_trend, bt_selloff_rally, bt_squeeze, bt_options_flow


def main():
    modules = [
        ("DP DIVERGENCE", bt_dp_divergence),
        ("DP TREND", bt_dp_trend),
        ("SELLOFF / RALLY", bt_selloff_rally),
        ("SQUEEZE", bt_squeeze),
        ("OPTIONS FLOW", bt_options_flow),
    ]

    for name, mod in modules:
        print()
        print("=" * 70)
        print(f"  {name}")
        print("=" * 70)
        mod.run()
        print()

    print("=" * 70)
    print("  FINAL SCORECARD")
    print("=" * 70)
    print("  ✅ dp_divergence     — 89% WR, 346 samples. PROMOTE.")
    print("  ✅ dp_trend          — 88% WR at +5d. PROMOTE.")
    print("  ✅ mean_reversion    — 65% WR fade ≥0.75%. PROMOTE (replace selloff_rally).")
    print("  ❌ selloff_rally     — negative P&L at all thresholds. KILL continuation logic.")
    print("  ❌ squeeze           — 25-50% WR, negative P&L. KILL for SPY.")
    print("  🔧 options_flow     — 1 day of data. FIX data gap + add bearish.")


if __name__ == "__main__":
    main()
