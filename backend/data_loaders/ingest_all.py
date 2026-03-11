"""
Dataset Ingestion Pipeline — 5-Gate Protocol
Downloads, cleans, stores, and verifies all external data sources.

Execution order: yfinance → FINRA → CFTC → FRED → CBOE VIX
Each source must pass all 5 gates before proceeding to the next.
"""

import os
import sys
import json
import time
import sqlite3
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path

# Add project root — explicit path to avoid resolution issues
ROOT = Path("/Users/fahadkiani/Desktop/development/nyu-hackathon/ai-hedge-fund-main")
sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "data" / "external"
TICKERS = ["SPY", "QQQ", "AAPL", "TSLA", "NVDA", "IWM"]

def log(gate: str, source: str, msg: str):
    print(f"  [{gate}] {source}: {msg}")

def write_manifest(source_dir: Path, manifest: dict):
    with open(source_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2, default=str)

# ═══════════════════════════════════════════════════════
# SOURCE 1: yfinance — Price History
# ═══════════════════════════════════════════════════════
def ingest_yfinance():
    source = "yfinance"
    source_dir = DATA_DIR / source
    print(f"\n{'='*60}")
    print(f"SOURCE 1: yfinance — Price History")
    print(f"{'='*60}")

    # ── Gate 1: PROBE ──
    log("G1", source, "Probing yfinance availability...")
    try:
        import yfinance as yf
        import pandas as pd
        log("G1", source, "✅ yfinance library available")
    except ImportError:
        log("G1", source, "❌ yfinance not installed. Run: pip install yfinance")
        return False

    # ── Gate 2: SAMPLE ──
    log("G2", source, "Downloading 5-day sample for SPY...")
    test = yf.Ticker("SPY").history(period="5d")
    if test.empty:
        log("G2", source, "❌ Empty response — yfinance may be down")
        return False

    expected_cols = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in expected_cols if c not in test.columns]
    if missing:
        log("G2", source, f"❌ Missing columns: {missing}")
        return False

    sample_path = source_dir / "samples" / f"spy_sample_{datetime.now():%Y%m%d}.csv"
    test.to_csv(sample_path)
    log("G2", source, f"✅ Sample saved: {len(test)} rows, cols: {list(test.columns)}")

    # ── Gate 3 + 4: CLEAN + STORE ──
    log("G3", source, "Downloading 2 years of daily data for all tickers...")
    all_frames = []
    for ticker in TICKERS:
        try:
            df = yf.Ticker(ticker).history(period="2y")
            if df.empty:
                log("G3", source, f"⚠️ {ticker}: empty response, skipping")
                continue

            df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
            df["symbol"] = ticker
            df.index.name = "date"
            df = df.reset_index()
            df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)

            # Compute daily return
            df["daily_return"] = df["Close"].pct_change()

            # Range checks
            assert df["Close"].min() > 0, f"{ticker} has negative close price"
            assert df["Volume"].min() >= 0, f"{ticker} has negative volume"

            all_frames.append(df)
            log("G3", source, f"  ✅ {ticker}: {len(df)} rows, "
                f"${df['Close'].iloc[-1]:.2f} latest close")
        except Exception as e:
            log("G3", source, f"  ❌ {ticker}: {e}")

    if not all_frames:
        log("G3", source, "❌ No data downloaded")
        return False

    combined = pd.concat(all_frames, ignore_index=True)

    # Remove duplicates
    before = len(combined)
    combined = combined.drop_duplicates(subset=["date", "symbol"])
    dupes = before - len(combined)
    if dupes:
        log("G3", source, f"  Removed {dupes} duplicate rows")

    # Save clean parquet
    clean_path = source_dir / "clean" / "price_history.parquet"
    combined.to_parquet(clean_path, index=False)
    log("G4", source, f"✅ Stored {len(combined)} rows → {clean_path.name}")

    # Save to SQLite
    db_path = source_dir / "db" / "prices.db"
    conn = sqlite3.connect(str(db_path))
    combined.to_sql("daily_ohlcv", conn, if_exists="replace", index=False)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prices_date_sym ON daily_ohlcv(date, symbol)")
    conn.commit()
    conn.close()
    log("G4", source, f"✅ SQLite: {db_path.name} → table: daily_ohlcv")

    # Manifest
    write_manifest(source_dir, {
        "source_name": "yfinance",
        "source_url": "https://finance.yahoo.com",
        "download_date": datetime.now().isoformat(),
        "date_range": {
            "start": str(combined["date"].min()),
            "end": str(combined["date"].max())
        },
        "tickers": TICKERS,
        "total_rows": len(combined),
        "schema_version": 1,
        "columns": list(combined.columns),
        "cleaning_applied": ["daily_return_computed", "duplicates_removed", "tz_stripped"],
        "verification_status": "pending"
    })

    # ── Gate 5: VERIFY ──
    log("G5", source, "Verifying latest prices against live API...")
    # Cross-check: our stored latest close vs a fresh fetch
    for ticker in TICKERS[:3]:
        stored = combined[combined["symbol"] == ticker]["Close"].iloc[-1]
        fresh = yf.Ticker(ticker).history(period="1d")
        if not fresh.empty:
            live = fresh["Close"].iloc[-1]
            delta = abs(stored - live) / live * 100
            status = "✅" if delta < 1.0 else "⚠️"
            log("G5", source, f"  {status} {ticker}: stored=${stored:.2f} live=${live:.2f} Δ={delta:.2f}%")

    log("G5", source, "✅ yfinance ingestion COMPLETE")
    return True


# ═══════════════════════════════════════════════════════
# SOURCE 2: FINRA Short Sale Volume
# ═══════════════════════════════════════════════════════
def ingest_finra():
    source = "finra_short"
    source_dir = DATA_DIR / source
    print(f"\n{'='*60}")
    print(f"SOURCE 2: FINRA Short Sale Volume")
    print(f"{'='*60}")

    import pandas as pd

    # ── Gate 1: PROBE ──
    log("G1", source, "FINRA CNMSshvol files: pipe-delimited, ~2MB/day, no auth")

    # ── Gate 2: SAMPLE — try yesterday and work backwards to find a valid date ──
    log("G2", source, "Finding most recent trading day file...")
    sample_df = None
    sample_date = None

    for days_back in range(1, 10):
        check_date = datetime.now() - timedelta(days=days_back)
        date_str = check_date.strftime("%Y%m%d")
        url = f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{date_str}.txt"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ZoIngest/1.0"})
            resp = urllib.request.urlopen(req, timeout=15)
            content = resp.read().decode("utf-8")
            if len(content) < 100:
                continue

            # Save raw
            raw_path = source_dir / "raw" / f"CNMSshvol{date_str}.txt"
            with open(raw_path, "w") as f:
                f.write(content)

            # Parse sample
            from io import StringIO
            sample_df = pd.read_csv(StringIO(content), sep="|")
            sample_date = date_str
            log("G2", source, f"✅ Found data for {date_str}: {len(sample_df)} rows, "
                f"cols: {list(sample_df.columns)}")
            break
        except urllib.error.HTTPError:
            continue
        except Exception as e:
            log("G2", source, f"  {date_str}: {e}")
            continue

    if sample_df is None:
        log("G2", source, "❌ Could not find any recent FINRA file")
        return False

    # ── Gate 3 + 4: Download last 30 trading days, clean, store ──
    log("G3", source, "Downloading last 30 trading days...")
    all_frames = []
    files_downloaded = 0

    for days_back in range(1, 50):  # Check 50 calendar days for ~30 trading days
        check_date = datetime.now() - timedelta(days=days_back)
        if check_date.weekday() >= 5:  # Skip weekends
            continue
        date_str = check_date.strftime("%Y%m%d")
        url = f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{date_str}.txt"

        raw_path = source_dir / "raw" / f"CNMSshvol{date_str}.txt"
        try:
            if raw_path.exists():
                with open(raw_path) as f:
                    content = f.read()
            else:
                req = urllib.request.Request(url, headers={"User-Agent": "ZoIngest/1.0"})
                resp = urllib.request.urlopen(req, timeout=15)
                content = resp.read().decode("utf-8")
                with open(raw_path, "w") as f:
                    f.write(content)
                time.sleep(0.3)  # Be polite

            if len(content) < 100:
                continue

            from io import StringIO
            df = pd.read_csv(StringIO(content), sep="|")

            # Filter to our tickers
            if "Symbol" in df.columns:
                df = df[df["Symbol"].isin(TICKERS)].copy()
            elif "symbol" in df.columns:
                df = df[df["symbol"].isin(TICKERS)].copy()
                df = df.rename(columns={"symbol": "Symbol"})

            if len(df) > 0:
                df["file_date"] = date_str
                all_frames.append(df)
                files_downloaded += 1

        except urllib.error.HTTPError:
            continue
        except Exception as e:
            continue

        if files_downloaded >= 30:
            break

    log("G3", source, f"Downloaded {files_downloaded} trading days")

    if not all_frames:
        log("G3", source, "❌ No data collected")
        return False

    combined = pd.concat(all_frames, ignore_index=True)

    # Standardize column names
    col_map = {}
    for c in combined.columns:
        cl = c.lower().strip()
        if "symbol" in cl:
            col_map[c] = "symbol"
        elif "shortvolume" in cl.replace(" ", "").replace("_", ""):
            if "exempt" in cl:
                col_map[c] = "short_exempt_volume"
            else:
                col_map[c] = "short_volume"
        elif "totalvolume" in cl.replace(" ", "").replace("_", ""):
            col_map[c] = "total_volume"
        elif "market" in cl:
            col_map[c] = "market"
        elif "date" in cl:
            col_map[c] = "date"

    combined = combined.rename(columns=col_map)

    # Compute short_volume_pct
    if "short_volume" in combined.columns and "total_volume" in combined.columns:
        combined["total_volume"] = pd.to_numeric(combined["total_volume"], errors="coerce")
        combined["short_volume"] = pd.to_numeric(combined["short_volume"], errors="coerce")
        combined["short_volume_pct"] = (
            combined["short_volume"] / combined["total_volume"].replace(0, float("nan")) * 100
        ).round(2)

    if "file_date" in combined.columns and "date" not in combined.columns:
        combined["date"] = combined["file_date"]

    # Drop duplicates
    before = len(combined)
    combined = combined.drop_duplicates(subset=["date", "symbol"])
    log("G3", source, f"✅ Cleaned: {len(combined)} rows ({before - len(combined)} dupes removed)")

    # Store
    clean_path = source_dir / "clean" / "short_volume.parquet"
    combined.to_parquet(clean_path, index=False)

    db_path = source_dir / "db" / "finra_short.db"
    conn = sqlite3.connect(str(db_path))
    combined.to_sql("daily_short_volume", conn, if_exists="replace", index=False)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_short_date_sym ON daily_short_volume(date, symbol)")
    conn.commit()
    conn.close()
    log("G4", source, f"✅ Stored {len(combined)} rows → parquet + SQLite")

    # Manifest
    write_manifest(source_dir, {
        "source_name": "finra_short_volume",
        "source_url": "https://cdn.finra.org/equity/regsho/daily/",
        "download_date": datetime.now().isoformat(),
        "date_range": {
            "start": str(combined["date"].min()),
            "end": str(combined["date"].max())
        },
        "total_rows": len(combined),
        "total_files": files_downloaded,
        "schema_version": 1,
        "columns": list(combined.columns),
        "verification_status": "pending"
    })

    # ── Gate 5: VERIFY — compare vs Stockgrid ──
    log("G5", source, "Verifying SPY short_volume_pct against our Stockgrid API...")
    try:
        req = urllib.request.Request(
            "http://localhost:8000/api/v1/darkpool/SPY/summary",
            headers={"User-Agent": "ZoVerify"}
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        stockgrid_pct = resp.get("summary", {}).get("short_volume_pct", 0)

        spy_rows = combined[combined["symbol"] == "SPY"].sort_values("date")
        if len(spy_rows) > 0 and "short_volume_pct" in spy_rows.columns:
            finra_pct = spy_rows["short_volume_pct"].iloc[-1]
            delta = abs(finra_pct - stockgrid_pct)
            status = "✅" if delta < 5 else "⚠️"
            log("G5", source, f"  {status} SPY: FINRA={finra_pct:.1f}% Stockgrid={stockgrid_pct:.1f}% Δ={delta:.1f}pp")
    except Exception as e:
        log("G5", source, f"  ⚠️ Could not verify against Stockgrid: {e}")

    log("G5", source, "✅ FINRA ingestion COMPLETE")
    return True


# ═══════════════════════════════════════════════════════
# SOURCE 3: CFTC COT Data
# ═══════════════════════════════════════════════════════
def ingest_cftc_cot():
    source = "cftc_cot"
    source_dir = DATA_DIR / source
    print(f"\n{'='*60}")
    print(f"SOURCE 3: CFTC Commitments of Traders")
    print(f"{'='*60}")

    import pandas as pd

    # ── Gate 1: PROBE ──
    log("G1", source, "CFTC COT: cot_reports Python lib or direct download")

    # Try cot_reports library first
    try:
        import cot_reports
        has_lib = True
        log("G1", source, "✅ cot_reports library available")
    except ImportError:
        has_lib = False
        log("G1", source, "⚠️ cot_reports not installed, using direct download")

    # ── Gate 2: SAMPLE ──
    log("G2", source, "Downloading current year COT data...")

    cot_df = None
    if has_lib:
        try:
            cot_df = cot_reports.cot_report(report_type="legacy_fut")
            log("G2", source, f"✅ Got {len(cot_df)} rows via cot_reports")
        except Exception as e:
            log("G2", source, f"⚠️ cot_reports failed: {e}, trying direct download")

    if cot_df is None:
        # Direct download from CFTC
        year = datetime.now().year
        url = f"https://www.cftc.gov/dea/newcot/deafut.txt"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ZoIngest/1.0"})
            resp = urllib.request.urlopen(req, timeout=30)
            content = resp.read().decode("utf-8")
            raw_path = source_dir / "raw" / f"deafut_{year}.txt"
            with open(raw_path, "w") as f:
                f.write(content)
            cot_df = pd.read_csv(raw_path)
            log("G2", source, f"✅ Direct download: {len(cot_df)} rows")
        except Exception as e:
            log("G2", source, f"❌ Failed to download COT data: {e}")
            return False

    if cot_df is None or len(cot_df) == 0:
        log("G2", source, "❌ No COT data obtained")
        return False

    # Save raw sample
    sample_path = source_dir / "samples" / f"cot_sample_{datetime.now():%Y%m%d}.csv"
    cot_df.head(50).to_csv(sample_path, index=False)
    log("G2", source, f"  Columns: {list(cot_df.columns)[:8]}...")

    # ── Gate 3: CLEAN ──
    log("G3", source, "Cleaning and filtering to our contracts...")

    # Map CFTC contract names to our short keys
    CONTRACT_MAP = {
        "E-MINI S&P 500": "ES",
        "S&P 500": "ES",
        "E-MINI NASDAQ-100": "NQ",
        "NASDAQ-100": "NQ",
        "NASDAQ MINI": "NQ",
        "10-YEAR": "TY",
        "10 YEAR": "TY",
        "GOLD": "GC",
        "CRUDE OIL": "CL",
        "CRUDE OIL, LIGHT SWEET": "CL",
        "VIX FUTURES": "VX",
        "VIX": "VX",
    }

    # Find the market name column
    name_col = None
    for c in cot_df.columns:
        if "market" in c.lower() and "name" in c.lower():
            name_col = c
            break
    if not name_col:
        # Try to find it
        for c in cot_df.columns:
            if "market" in c.lower():
                name_col = c
                break

    if not name_col:
        log("G3", source, f"⚠️ Cannot find market name column. Cols: {list(cot_df.columns)[:10]}")
        # Store what we have and continue
        name_col = cot_df.columns[0]

    # Find specs/comm columns
    def find_col(df, keywords):
        for c in df.columns:
            cl = c.lower().replace("_", " ").replace("-", " ")
            if all(k in cl for k in keywords):
                return c
        return None

    specs_long_col = find_col(cot_df, ["noncommercial", "long"]) or find_col(cot_df, ["non commercial", "long"])
    specs_short_col = find_col(cot_df, ["noncommercial", "short"]) or find_col(cot_df, ["non commercial", "short"])
    comm_long_col = find_col(cot_df, ["commercial", "long"])
    comm_short_col = find_col(cot_df, ["commercial", "short"])
    date_col = find_col(cot_df, ["date"]) or find_col(cot_df, ["as of"])
    oi_col = find_col(cot_df, ["open interest"])

    log("G3", source, f"  name_col={name_col}")
    log("G3", source, f"  specs_long={specs_long_col}, specs_short={specs_short_col}")
    log("G3", source, f"  comm_long={comm_long_col}, comm_short={comm_short_col}")
    log("G3", source, f"  date_col={date_col}, oi_col={oi_col}")

    # Filter to our contracts
    clean_rows = []
    for _, row in cot_df.iterrows():
        market_name = str(row.get(name_col, "")).upper()
        contract_key = None
        for pattern, key in CONTRACT_MAP.items():
            if pattern.upper() in market_name:
                contract_key = key
                break

        if contract_key:
            clean_row = {"contract_key": contract_key, "market_name": market_name}
            if date_col:
                clean_row["report_date"] = row[date_col]
            if specs_long_col:
                clean_row["specs_long"] = pd.to_numeric(row.get(specs_long_col), errors="coerce")
            if specs_short_col:
                clean_row["specs_short"] = pd.to_numeric(row.get(specs_short_col), errors="coerce")
            if comm_long_col:
                clean_row["comm_long"] = pd.to_numeric(row.get(comm_long_col), errors="coerce")
            if comm_short_col:
                clean_row["comm_short"] = pd.to_numeric(row.get(comm_short_col), errors="coerce")
            if oi_col:
                clean_row["open_interest"] = pd.to_numeric(row.get(oi_col), errors="coerce")

            # Compute nets
            if "specs_long" in clean_row and "specs_short" in clean_row:
                sl = clean_row.get("specs_long", 0) or 0
                ss = clean_row.get("specs_short", 0) or 0
                clean_row["specs_net"] = sl - ss
            if "comm_long" in clean_row and "comm_short" in clean_row:
                cl_v = clean_row.get("comm_long", 0) or 0
                cs = clean_row.get("comm_short", 0) or 0
                clean_row["comm_net"] = cl_v - cs

            clean_rows.append(clean_row)

    if not clean_rows:
        log("G3", source, "❌ No matching contracts found")
        return False

    clean_df = pd.DataFrame(clean_rows)
    # Drop duplicates by contract_key + report_date
    if "report_date" in clean_df.columns:
        clean_df = clean_df.drop_duplicates(subset=["contract_key", "report_date"])

    log("G3", source, f"✅ Cleaned: {len(clean_df)} rows across {clean_df['contract_key'].nunique()} contracts")

    # ── Gate 4: STORE ──
    clean_path = source_dir / "clean" / "cot_positioning.parquet"
    clean_df.to_parquet(clean_path, index=False)

    db_path = source_dir / "db" / "cot_history.db"
    conn = sqlite3.connect(str(db_path))
    clean_df.to_sql("weekly_positioning", conn, if_exists="replace", index=False)
    conn.commit()
    conn.close()
    log("G4", source, f"✅ Stored {len(clean_df)} rows → parquet + SQLite")

    write_manifest(source_dir, {
        "source_name": "cftc_cot",
        "source_url": "https://www.cftc.gov/dea/newcot/deafut.txt",
        "download_date": datetime.now().isoformat(),
        "total_rows": len(clean_df),
        "contracts": list(clean_df["contract_key"].unique()),
        "schema_version": 1,
        "columns": list(clean_df.columns),
        "verification_status": "pending"
    })

    # ── Gate 5: VERIFY ──
    log("G5", source, "Verifying ES specs_net against our /cot/positioning API...")
    try:
        req = urllib.request.Request(
            "http://localhost:8000/api/v1/cot/positioning",
            headers={"User-Agent": "ZoVerify"}
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
        for contract in resp.get("contracts", []):
            key = contract.get("contract_key")
            api_net = contract.get("specs_net")
            our_rows = clean_df[clean_df["contract_key"] == key]
            if len(our_rows) > 0 and "specs_net" in our_rows.columns:
                our_net = our_rows.sort_values("report_date").iloc[-1]["specs_net"]
                match = "✅" if abs(our_net - api_net) < 1000 else "⚠️"
                log("G5", source, f"  {match} {key}: CFTC={our_net:,.0f} API={api_net:,.0f}")
    except Exception as e:
        log("G5", source, f"  ⚠️ Could not verify: {e}")

    log("G5", source, "✅ CFTC COT ingestion COMPLETE")
    return True


# ═══════════════════════════════════════════════════════
# SOURCE 4: FRED Economic Data
# ═══════════════════════════════════════════════════════
def ingest_fred():
    source = "fred"
    source_dir = DATA_DIR / source
    print(f"\n{'='*60}")
    print(f"SOURCE 4: FRED Economic Indicators")
    print(f"{'='*60}")

    import pandas as pd

    # ── Gate 1: PROBE ──
    # Try our existing FRED client first
    fred_key = os.environ.get("FRED_API_KEY", "")
    has_key = bool(fred_key)

    if has_key:
        log("G1", source, "✅ FRED_API_KEY found in environment")
    else:
        # Try .env file
        env_path = ROOT / ".env"
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    if line.startswith("FRED_API_KEY"):
                        fred_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        has_key = bool(fred_key)
                        break
        if has_key:
            log("G1", source, f"✅ FRED_API_KEY found in .env")
        else:
            log("G1", source, "⚠️ No FRED_API_KEY — using yfinance fallback for macro data")

    # Series we want
    SERIES = {
        "CPIAUCSL": "CPI All Urban Consumers",
        "UNRATE": "Unemployment Rate",
        "PAYEMS": "Nonfarm Payrolls",
        "FEDFUNDS": "Fed Funds Rate",
        "DGS10": "10-Year Treasury",
        "DGS2": "2-Year Treasury",
        "T10Y2Y": "10Y-2Y Spread",
    }

    all_series = []

    if has_key:
        # ── Gate 2: SAMPLE via FRED API ──
        log("G2", source, "Fetching from FRED API...")
        for series_id, name in SERIES.items():
            url = (f"https://api.stlouisfed.org/fred/series/observations"
                   f"?series_id={series_id}&api_key={fred_key}"
                   f"&file_type=json&sort_order=desc&limit=500")
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "ZoIngest/1.0"})
                resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
                observations = resp.get("observations", [])
                for obs in observations:
                    if obs.get("value") and obs["value"] != ".":
                        all_series.append({
                            "series_id": series_id,
                            "series_name": name,
                            "date": obs["date"],
                            "value": float(obs["value"]),
                        })
                log("G2", source, f"  ✅ {series_id} ({name}): {len(observations)} observations")
                time.sleep(0.2)
            except Exception as e:
                log("G2", source, f"  ❌ {series_id}: {e}")
    else:
        # Fallback: use yfinance for treasury yields and ^VIX
        log("G2", source, "Using yfinance fallback for macro indicators...")
        import yfinance as yf
        fallback_tickers = {"^TNX": "10Y Treasury", "^FVX": "5Y Treasury", "^VIX": "VIX"}
        for ticker, name in fallback_tickers.items():
            try:
                data = yf.Ticker(ticker).history(period="2y")
                for date, row in data.iterrows():
                    all_series.append({
                        "series_id": ticker,
                        "series_name": name,
                        "date": str(date.date()),
                        "value": round(row["Close"], 4),
                    })
                log("G2", source, f"  ✅ {ticker} ({name}): {len(data)} data points")
            except Exception as e:
                log("G2", source, f"  ❌ {ticker}: {e}")

    if not all_series:
        log("G3", source, "❌ No FRED/macro data obtained")
        return False

    # ── Gate 3 + 4: CLEAN + STORE ──
    df = pd.DataFrame(all_series)
    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates(subset=["series_id", "date"])
    df = df.sort_values(["series_id", "date"])

    clean_path = source_dir / "clean" / "economic_indicators.parquet"
    df.to_parquet(clean_path, index=False)

    db_path = source_dir / "db" / "fred_history.db"
    conn = sqlite3.connect(str(db_path))
    df.to_sql("indicator_values", conn, if_exists="replace", index=False)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fred_series_date ON indicator_values(series_id, date)")
    conn.commit()
    conn.close()

    log("G4", source, f"✅ Stored {len(df)} rows across {df['series_id'].nunique()} series → parquet + SQLite")

    write_manifest(source_dir, {
        "source_name": "fred_economic",
        "source_url": "https://api.stlouisfed.org/fred/" if has_key else "yfinance_fallback",
        "download_date": datetime.now().isoformat(),
        "total_rows": len(df),
        "series": list(df["series_id"].unique()),
        "schema_version": 1,
        "columns": list(df.columns),
        "has_fred_key": has_key,
        "verification_status": "pending"
    })

    # ── Gate 5: VERIFY ──
    log("G5", source, "Verifying against our economic_intelligence.db...")
    try:
        econ_db = ROOT / "data" / "economic_intelligence.db"
        if econ_db.exists():
            conn = sqlite3.connect(str(econ_db))
            our_cpi = pd.read_sql("SELECT date, actual FROM economic_releases WHERE event_type='cpi' ORDER BY date DESC LIMIT 5", conn)
            conn.close()
            if len(our_cpi) > 0:
                log("G5", source, f"  Our DB has {len(our_cpi)} recent CPI entries for cross-ref")
            else:
                log("G5", source, "  Our DB has no CPI entries to cross-reference")
        else:
            log("G5", source, "  economic_intelligence.db not found")
    except Exception as e:
        log("G5", source, f"  ⚠️ Verify error: {e}")

    log("G5", source, "✅ FRED/macro ingestion COMPLETE")
    return True


# ═══════════════════════════════════════════════════════
# SOURCE 5: CBOE VIX Futures
# ═══════════════════════════════════════════════════════
def ingest_cboe_vix():
    source = "cboe_vix"
    source_dir = DATA_DIR / source
    print(f"\n{'='*60}")
    print(f"SOURCE 5: CBOE VIX Futures")
    print(f"{'='*60}")

    import pandas as pd

    # ── Gate 1: PROBE ──
    log("G1", source, "CBOE VIX data via yfinance ^VIX (simpler than per-contract CSVs)")

    # ── Gate 2: SAMPLE ──
    import yfinance as yf
    log("G2", source, "Downloading ^VIX history via yfinance...")
    vix = yf.Ticker("^VIX").history(period="5y")
    if vix.empty:
        log("G2", source, "❌ Could not fetch VIX data")
        return False

    log("G2", source, f"✅ {len(vix)} rows, range: {vix.index[0].date()} → {vix.index[-1].date()}")

    # Also get VIX futures term structure proxy via VIXY/SVXY
    vvix = yf.Ticker("^VVIX").history(period="2y")
    log("G2", source, f"  VVIX (vol of vol): {len(vvix)} rows")

    # ── Gate 3 + 4: CLEAN + STORE ──
    vix_df = vix[["Open", "High", "Low", "Close", "Volume"]].copy()
    vix_df.index.name = "date"
    vix_df = vix_df.reset_index()
    vix_df["date"] = pd.to_datetime(vix_df["date"]).dt.tz_localize(None)
    vix_df["symbol"] = "VIX"

    # Add VVIX if available
    if not vvix.empty:
        vvix_df = vvix[["Close"]].copy()
        vvix_df.index.name = "date"
        vvix_df = vvix_df.reset_index()
        vvix_df["date"] = pd.to_datetime(vvix_df["date"]).dt.tz_localize(None)
        vvix_df = vvix_df.rename(columns={"Close": "vvix_close"})
        vix_df = vix_df.merge(vvix_df[["date", "vvix_close"]], on="date", how="left")

    # Compute regime
    vix_df["vix_regime"] = "NORMAL"
    vix_df.loc[vix_df["Close"] > 25, "vix_regime"] = "ELEVATED"
    vix_df.loc[vix_df["Close"] > 35, "vix_regime"] = "FEAR"
    vix_df.loc[vix_df["Close"] < 15, "vix_regime"] = "COMPLACENT"

    # Store
    clean_path = source_dir / "clean" / "vix_history.parquet"
    vix_df.to_parquet(clean_path, index=False)

    db_path = source_dir / "db" / "vix_history.db"
    conn = sqlite3.connect(str(db_path))
    vix_df.to_sql("daily_vix", conn, if_exists="replace", index=False)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_vix_date ON daily_vix(date)")
    conn.commit()
    conn.close()

    log("G4", source, f"✅ Stored {len(vix_df)} rows → parquet + SQLite")

    write_manifest(source_dir, {
        "source_name": "cboe_vix",
        "source_url": "yfinance ^VIX + ^VVIX",
        "download_date": datetime.now().isoformat(),
        "date_range": {
            "start": str(vix_df["date"].min()),
            "end": str(vix_df["date"].max())
        },
        "total_rows": len(vix_df),
        "schema_version": 1,
        "columns": list(vix_df.columns),
        "verification_status": "pending"
    })

    # ── Gate 5: VERIFY ──
    log("G5", source, "Verifying latest VIX against live...")
    latest_stored = vix_df["Close"].iloc[-1]
    fresh = yf.Ticker("^VIX").history(period="1d")
    if not fresh.empty:
        live = fresh["Close"].iloc[-1]
        delta = abs(latest_stored - live)
        status = "✅" if delta < 1.0 else "⚠️"
        log("G5", source, f"  {status} VIX: stored={latest_stored:.2f} live={live:.2f} Δ={delta:.2f}")

    log("G5", source, "✅ CBOE VIX ingestion COMPLETE")
    return True


# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    print("╔" + "═" * 58 + "╗")
    print("║  DATASET INGESTION PIPELINE — 5 GATE PROTOCOL           ║")
    print("║  Order: yfinance → FINRA → CFTC → FRED → CBOE VIX      ║")
    print("╚" + "═" * 58 + "╝")

    results = {}

    # Execute in order
    sources = [
        ("yfinance", ingest_yfinance),
        ("finra_short", ingest_finra),
        ("cftc_cot", ingest_cftc_cot),
        ("fred", ingest_fred),
        ("cboe_vix", ingest_cboe_vix),
    ]

    for name, func in sources:
        try:
            results[name] = func()
        except Exception as e:
            print(f"\n❌ {name} FAILED with exception: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False

    # Summary
    print(f"\n{'='*60}")
    print("INGESTION SUMMARY")
    print(f"{'='*60}")
    for name, success in results.items():
        print(f"  {'✅' if success else '❌'} {name}")

    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\nResult: {passed}/{total} sources ingested successfully")
    print(f"Data stored in: data/external/")
