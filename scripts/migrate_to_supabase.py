"""
🚀 Supabase Migration Script
=============================
Creates tables in Supabase and migrates existing SQLite data.

Usage:
    SUPABASE_URL=... SUPABASE_KEY=... python3 scripts/migrate_to_supabase.py

Or set env vars in .env and run:
    python3 scripts/migrate_to_supabase.py
"""

import os
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

# Add project root to path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def get_supabase_client():
    """Init Supabase client from env vars."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        print("❌ Set SUPABASE_URL and SUPABASE_KEY env vars first!")
        print("   export SUPABASE_URL=https://gpirjathvfoqjurjhdxq.supabase.co")
        print("   export SUPABASE_KEY=<your_anon_key>")
        sys.exit(1)

    from supabase import create_client
    client = create_client(url, key)
    print(f"✅ Connected to Supabase: {url[:40]}...")
    return client


def create_tables_via_rpc(client):
    """
    Create tables using Supabase SQL Editor / REST.
    Since supabase-py doesn't support raw DDL, we use the
    Supabase Management API or manual SQL. This function
    will print the SQL for manual execution if RPC fails.
    """
    sql_statements = [
        # Alerts table
        """
        CREATE TABLE IF NOT EXISTS alerts (
            id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            alert_type TEXT NOT NULL DEFAULT 'signal',
            title TEXT,
            description TEXT,
            content TEXT,
            embed_json TEXT,
            source TEXT,
            symbol TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp);
        CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type);
        CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON alerts(symbol);
        """,

        # DP Interactions table
        """
        CREATE TABLE IF NOT EXISTS dp_interactions (
            id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            symbol TEXT NOT NULL,
            level_price DOUBLE PRECISION NOT NULL,
            level_volume BIGINT NOT NULL DEFAULT 0,
            level_type TEXT NOT NULL DEFAULT '',
            level_date TEXT,
            approach_price DOUBLE PRECISION,
            approach_direction TEXT,
            distance_pct DOUBLE PRECISION,
            touch_count INTEGER DEFAULT 1,
            market_trend TEXT,
            volume_vs_avg DOUBLE PRECISION,
            momentum_pct DOUBLE PRECISION,
            vix_level DOUBLE PRECISION,
            time_of_day TEXT,
            outcome TEXT DEFAULT 'PENDING',
            outcome_timestamp TIMESTAMPTZ,
            max_move_pct DOUBLE PRECISION DEFAULT 0,
            time_to_outcome_min INTEGER DEFAULT 0,
            price_at_5min DOUBLE PRECISION,
            price_at_15min DOUBLE PRECISION,
            price_at_30min DOUBLE PRECISION,
            price_at_60min DOUBLE PRECISION,
            notes TEXT
        );
        """,

        # DP Patterns table
        """
        CREATE TABLE IF NOT EXISTS dp_patterns (
            id BIGSERIAL PRIMARY KEY,
            pattern_name TEXT UNIQUE NOT NULL,
            total_samples INTEGER DEFAULT 0,
            bounce_count INTEGER DEFAULT 0,
            break_count INTEGER DEFAULT 0,
            fade_count INTEGER DEFAULT 0,
            last_updated TIMESTAMPTZ DEFAULT NOW()
        );
        """,

        # Signal Outcomes table
        """
        CREATE TABLE IF NOT EXISTS signal_outcomes (
            id BIGSERIAL PRIMARY KEY,
            signal_id TEXT UNIQUE NOT NULL,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry_price DOUBLE PRECISION NOT NULL,
            stop_pct DOUBLE PRECISION,
            target_pct DOUBLE PRECISION,
            confidence DOUBLE PRECISION,
            source TEXT,
            regime TEXT,
            bias TEXT,
            sizing DOUBLE PRECISION,
            entry_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            price_5min DOUBLE PRECISION,
            price_15min DOUBLE PRECISION,
            price_30min DOUBLE PRECISION,
            price_60min DOUBLE PRECISION,
            outcome TEXT DEFAULT 'PENDING',
            outcome_time TIMESTAMPTZ,
            exit_price DOUBLE PRECISION,
            pnl_pct DOUBLE PRECISION,
            max_favorable DOUBLE PRECISION,
            max_adverse DOUBLE PRECISION,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_outcomes_source ON signal_outcomes(source);
        CREATE INDEX IF NOT EXISTS idx_outcomes_symbol ON signal_outcomes(symbol);
        CREATE INDEX IF NOT EXISTS idx_outcomes_outcome ON signal_outcomes(outcome);
        """,
    ]

    print("\n📋 SQL statements to run in Supabase SQL Editor:")
    print("=" * 60)
    for i, sql in enumerate(sql_statements, 1):
        print(f"\n-- Statement {i}")
        print(sql.strip())
    print("=" * 60)

    # Try running via RPC (if exec_sql function exists)
    for i, sql in enumerate(sql_statements, 1):
        try:
            client.rpc("exec_sql", {"query": sql.strip()}).execute()
            print(f"✅ Statement {i} executed via RPC")
        except Exception as e:
            print(f"⚠️  Statement {i} RPC failed (run manually in SQL Editor): {e}")

    return sql_statements


def migrate_alerts(client, db_path: Path):
    """Migrate alerts from SQLite to Supabase."""
    if not db_path.exists():
        print(f"⚠️  {db_path} not found, skipping alerts migration")
        return 0

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM alerts ORDER BY timestamp")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("⚠️  No alerts to migrate")
        return 0

    print(f"📦 Migrating {len(rows)} alerts...")
    batch = []
    migrated = 0

    for row in rows:
        record = {
            "timestamp": row["timestamp"],
            "alert_type": row["alert_type"],
            "title": row["title"] or "",
            "description": row["description"] or "",
            "content": row["content"] or "",
            "embed_json": row["embed_json"] or "",
            "source": row["source"] or "",
            "symbol": row["symbol"] or "",
            "created_at": row["created_at"] if "created_at" in row.keys() else row["timestamp"],
        }
        batch.append(record)

        # Insert in batches of 50
        if len(batch) >= 50:
            try:
                client.table("alerts").insert(batch).execute()
                migrated += len(batch)
                print(f"  ✅ {migrated}/{len(rows)} alerts migrated")
            except Exception as e:
                print(f"  ❌ Batch insert failed: {e}")
                # Try one by one
                for r in batch:
                    try:
                        client.table("alerts").insert(r).execute()
                        migrated += 1
                    except Exception as e2:
                        print(f"  ⚠️  Skipped alert: {e2}")
            batch = []

    # Final batch
    if batch:
        try:
            client.table("alerts").insert(batch).execute()
            migrated += len(batch)
        except Exception as e:
            for r in batch:
                try:
                    client.table("alerts").insert(r).execute()
                    migrated += 1
                except:
                    pass

    print(f"✅ Migrated {migrated}/{len(rows)} alerts to Supabase")
    return migrated


def migrate_dp_learning(client, db_path: Path):
    """Migrate DP interactions and patterns from SQLite to Supabase."""
    if not db_path.exists():
        print(f"⚠️  {db_path} not found, skipping DP learning migration")
        return 0

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    total = 0

    # Interactions
    try:
        cursor = conn.execute("SELECT * FROM dp_interactions ORDER BY timestamp")
        rows = cursor.fetchall()
        if rows:
            print(f"📦 Migrating {len(rows)} DP interactions...")
            batch = []
            for row in rows:
                record = {k: row[k] for k in row.keys()}
                # Remove sqlite autoincrement id
                record.pop("id", None)
                batch.append(record)
                if len(batch) >= 50:
                    try:
                        client.table("dp_interactions").insert(batch).execute()
                        total += len(batch)
                    except Exception as e:
                        print(f"  ⚠️  Batch failed: {e}")
                    batch = []
            if batch:
                try:
                    client.table("dp_interactions").insert(batch).execute()
                    total += len(batch)
                except Exception as e:
                    print(f"  ⚠️  Final batch: {e}")
            print(f"  ✅ {total} DP interactions migrated")
    except Exception as e:
        print(f"  ⚠️  DP interactions migration failed: {e}")

    # Patterns
    try:
        cursor = conn.execute("SELECT * FROM dp_patterns")
        rows = cursor.fetchall()
        if rows:
            print(f"📦 Migrating {len(rows)} DP patterns...")
            for row in rows:
                record = {k: row[k] for k in row.keys()}
                record.pop("id", None)
                try:
                    client.table("dp_patterns").upsert(record, on_conflict="pattern_name").execute()
                    total += 1
                except Exception as e:
                    print(f"  ⚠️  Pattern '{record.get('pattern_name')}': {e}")
            print(f"  ✅ DP patterns migrated")
    except Exception as e:
        print(f"  ⚠️  DP patterns migration failed: {e}")

    conn.close()
    return total


def migrate_signal_outcomes(client, db_path: Path):
    """Migrate signal outcomes from SQLite to Supabase."""
    if not db_path.exists():
        print(f"⚠️  {db_path} not found, skipping outcomes migration")
        return 0

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute("SELECT * FROM signal_outcomes ORDER BY entry_time")
        rows = cursor.fetchall()
    except Exception as e:
        print(f"  ⚠️  signal_outcomes query failed: {e}")
        conn.close()
        return 0
    conn.close()

    if not rows:
        print("⚠️  No signal outcomes to migrate")
        return 0

    print(f"📦 Migrating {len(rows)} signal outcomes...")
    migrated = 0
    for row in rows:
        record = {k: row[k] for k in row.keys()}
        record.pop("id", None)
        try:
            client.table("signal_outcomes").upsert(record, on_conflict="signal_id").execute()
            migrated += 1
        except Exception as e:
            print(f"  ⚠️  Outcome '{record.get('signal_id')}': {e}")

    print(f"✅ Migrated {migrated}/{len(rows)} signal outcomes")
    return migrated


def verify_migration(client):
    """Verify data exists in Supabase tables."""
    print("\n🔍 Verification:")
    tables = ["alerts", "dp_interactions", "dp_patterns", "signal_outcomes"]
    for table in tables:
        try:
            result = client.table(table).select("*", count="exact").limit(1).execute()
            count = result.count if result.count is not None else len(result.data)
            print(f"  {table}: {count} rows")
        except Exception as e:
            print(f"  {table}: ❌ {e}")


def main():
    print("🚀 Supabase Migration for Zeta Signal Engine")
    print("=" * 50)

    client = get_supabase_client()

    # Step 1: Create tables
    print("\n📐 Step 1: Create tables")
    create_tables_via_rpc(client)

    # Step 2: Migrate data
    data_dir = ROOT / "data"
    print(f"\n📦 Step 2: Migrate data from {data_dir}")

    alerts_migrated = migrate_alerts(client, data_dir / "alerts_history.db")
    dp_migrated = migrate_dp_learning(client, data_dir / "dp_learning.db")
    outcomes_migrated = migrate_signal_outcomes(client, data_dir / "signal_outcomes_tracker.db")

    # Step 3: Verify
    print(f"\n📊 Step 3: Verify migration")
    verify_migration(client)

    print(f"\n✅ Migration complete!")
    print(f"   Alerts: {alerts_migrated}")
    print(f"   DP data: {dp_migrated}")
    print(f"   Outcomes: {outcomes_migrated}")
    print(f"\n🔧 Next steps:")
    print(f"   1. Set SUPABASE_URL and SUPABASE_KEY on Render")
    print(f"   2. Push code changes to deploy")
    print(f"   3. Verify /signals endpoint returns data")


if __name__ == "__main__":
    main()
