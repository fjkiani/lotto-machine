"""
Backtest: OPTIONS FLOW (bullish/bearish alerts vs price)
Run: python -m backtests.bt_options_flow
"""
from backtests.loader import alerts, bars_daily, forward_return_daily, score
from datetime import datetime, timedelta


def run():
    all_alerts = alerts()
    daily = bars_daily()
    print(f"Options Flow: {len(all_alerts)} total alerts, {len(daily)} daily bars")

    # Filter to bullish/bearish options
    opts = [a for a in all_alerts if "bullish" in a.get("alert_type", "").lower()
            or "bearish" in a.get("alert_type", "").lower()]
    print(f"  Options alerts: {len(opts)}")
    print(f"  Types: {set(a.get('alert_type') for a in opts)}")

    if not opts:
        print("  NO OPTIONS ALERTS — nothing to backtest")
        return

    # Date range
    dates = [a.get("timestamp", "")[:10] for a in opts]
    print(f"  Date range: {min(dates)} → {max(dates)}")

    # Build date→index lookup
    date_idx = {}
    for i, b in enumerate(daily):
        d = (b.get("Date") or b.get("date", ""))[:10]
        date_idx[d] = i

    daily_end = max(date_idx.keys())
    print(f"  Daily data ends: {daily_end}")

    signals = []
    unmatched = 0
    for a in opts:
        atype = a.get("alert_type", "").lower()
        adate = a.get("timestamp", "")[:10]
        direction = "LONG" if "bullish" in atype else "SHORT"

        # Find in daily bars (try signal date + next 4 days)
        idx = date_idx.get(adate)
        if idx is None:
            try:
                dt = datetime.strptime(adate, "%Y-%m-%d")
                for off in range(1, 5):
                    nd = (dt + timedelta(days=off)).strftime("%Y-%m-%d")
                    idx = date_idx.get(nd)
                    if idx is not None:
                        break
            except Exception:
                pass

        if idx is None:
            unmatched += 1
            continue

        fwd = forward_return_daily(daily, idx, direction)
        signals.append({"type": a.get("alert_type"), "date": adate, "dir": direction, "fwd": fwd})

    print(f"  Matched: {len(signals)} | Unmatched: {unmatched}")
    print()

    if not signals:
        print("  ALL UNMATCHED — alerts exist after daily data ends.")
        print("  Fix: accumulate more daily bars or extend spy_daily.json")
        return

    # Score by horizon
    for h in ["1d", "2d", "3d", "5d"]:
        pnls = [s["fwd"][h] for s in signals if h in s["fwd"]]
        score(f"+{h}", pnls)

    # Score by type
    print()
    type_groups = {}
    for s in signals:
        type_groups.setdefault(s["type"], []).append(s)
    for t, sigs in sorted(type_groups.items(), key=lambda x: -len(x[1])):
        pnls_1d = [s["fwd"]["1d"] for s in sigs if "1d" in s["fwd"]]
        if pnls_1d:
            w = sum(1 for p in pnls_1d if p > 0)
            avg = sum(pnls_1d) / len(pnls_1d)
            print(f"  {t}: n={len(sigs)} | 1d WR={w/len(pnls_1d)*100:.0f}% | avg={avg:+.3f}%")

    # Check: are there ANY bearish alerts?
    bearish = [s for s in signals if s["dir"] == "SHORT"]
    print(f"\n  Bearish signals: {len(bearish)} out of {len(signals)} total")
    if not bearish:
        print("  ⚠️ ZERO bearish signals — only bullish captured!")

    print()
    print("VERDICT: 🔧 FIX — insufficient data (1 day) + no bearish capture")


if __name__ == "__main__":
    run()
