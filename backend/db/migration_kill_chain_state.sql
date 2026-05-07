-- Kill Chain State persistence table
-- Run this ONCE in Supabase SQL Editor.
-- Stores a single JSONB row (id=1) with the live kill chain position state.
-- Survives Render free-tier restarts (unlike the previous disk-based JSON file).

CREATE TABLE IF NOT EXISTS kill_chain_state (
    id          INTEGER PRIMARY KEY DEFAULT 1,
    state       JSONB NOT NULL DEFAULT '{}',
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Ensure only one row ever exists
INSERT INTO kill_chain_state (id, state)
VALUES (1, '{"triple_active": false, "last_check": null, "spy_price": 0.0, "position": {"entry_price": 0.0, "activated_at": null, "current_pnl": 0.0}}')
ON CONFLICT (id) DO NOTHING;

-- Auto-update updated_at on every write
CREATE OR REPLACE FUNCTION update_kill_chain_state_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS kill_chain_state_updated_at ON kill_chain_state;
CREATE TRIGGER kill_chain_state_updated_at
    BEFORE UPDATE ON kill_chain_state
    FOR EACH ROW EXECUTE FUNCTION update_kill_chain_state_timestamp();
