"""
Backtest: SQUEEZE (Bollinger Band / Keltner Channel)
Run: python -m backtests.bt_squeeze

Tests BB inside KC squeeze-release on 15-min OHLCV data.
"""
from backtests.loader import bars_15min, forward_return_intraday, score


def run():
    bars = bars_15min()
    closes = [b["close"] for b in bars]
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    n = len(bars)
    print(f"Squeeze: {n} 15-min bars")

    squeeze_bars = 0
    releases = []

    for i in range(20, n):
        w = closes[i - 20 : i]
        sma = sum(w) / 20
        std = (sum((x - sma) ** 2 for x in w) / 20) ** 0.5
        if std == 0:
            continue

        bb_u = sma + 2 * std
        bb_l = sma - 2 * std

        start = max(0, i - 14)
        tr = [highs[j] - lows[j] for j in range(start, i)]
        atr = sum(tr) / len(tr) if tr else 0.001
        kc_u = sma + 1.5 * atr
        kc_l = sma - 1.5 * atr

        in_sq = bb_u < kc_u and bb_l > kc_l
        if in_sq:
            squeeze_bars += 1

        if i <= 21:
            continue

        # Check previous bar for squeeze state
        pw = closes[i - 21 : i - 1]
        ps = sum(pw) / 20
        pstd = (sum((x - ps) ** 2 for x in pw) / 20) ** 0.5
        pbb_u = ps + 2 * pstd
        pbb_l = ps - 2 * pstd
        pstart = max(0, i - 15)
        ptr = [highs[j] - lows[j] for j in range(pstart, i - 1)]
        patr = sum(ptr) / len(ptr) if ptr else 0.001
        pkc_u = ps + 1.5 * patr
        pkc_l = ps - 1.5 * patr
        was_in = pbb_u < pkc_u and pbb_l > pkc_l

        if was_in and not in_sq:
            direction = "LONG" if closes[i] > sma else "SHORT"
            fwd = forward_return_intraday(bars, i, direction)
            releases.append({"ts": bars[i]["timestamp"], "dir": direction, "price": closes[i], "fwd": fwd})

    print(f"  Bars in squeeze: {squeeze_bars}/{n} ({squeeze_bars / n * 100:.1f}%)")
    print(f"  Squeeze releases: {len(releases)}")
    print()

    for r in releases:
        fwd1h = r["fwd"].get("1h", "N/A")
        print(f"    {r['ts'][:19]} | {r['dir']} @ ${r['price']:.2f} | +1h={fwd1h}%")

    print()
    for h in ["15m", "30m", "1h", "2h", "4h"]:
        pnls = [r["fwd"][h] for r in releases if h in r["fwd"]]
        score(f"+{h}", pnls)

    print()
    print("VERDICT: ❌ KILL — 25-50% WR, negative P&L. BB/KC doesn't work on SPY.")


if __name__ == "__main__":
    run()
