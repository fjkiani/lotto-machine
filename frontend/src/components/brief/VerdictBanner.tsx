/**
 * VerdictBanner — Giant, color-coded verdict.
 * First thing a trader sees. "Trade or not?"
 */

interface VerdictBannerProps {
  verdict: string;
  summary: string;
  wallBreached: boolean;
  wallBreachDetails?: {
    spy_price: number;
    call_wall: number;
    delta: number;
    breach_time: string;
  } | null;
}

const VERDICT_STYLES: Record<string, { bg: string; border: string; text: string; glow: string; label: string }> = {
  // Morning brief vocabulary
  STRONG_BUY: { bg: 'rgba(16, 185, 129, 0.15)', border: 'rgba(16, 185, 129, 0.4)', text: '#10b981', glow: '0 0 40px rgba(16, 185, 129, 0.3)', label: 'Strong edge — deploy capital' },
  BUY:        { bg: 'rgba(52, 211, 153, 0.12)', border: 'rgba(52, 211, 153, 0.3)', text: '#34d399', glow: '0 0 30px rgba(52, 211, 153, 0.2)', label: 'Edge present — trade approved names' },
  NEUTRAL:    { bg: 'rgba(148, 163, 184, 0.1)', border: 'rgba(148, 163, 184, 0.2)', text: '#94a3b8', glow: 'none', label: 'No clear edge today' },
  CAUTION:    { bg: 'rgba(251, 191, 36, 0.12)', border: 'rgba(251, 191, 36, 0.3)', text: '#fbbf24', glow: '0 0 30px rgba(251, 191, 36, 0.2)', label: 'Mixed signals — reduced size or sit out' },
  SELL:       { bg: 'rgba(239, 68, 68, 0.15)', border: 'rgba(239, 68, 68, 0.4)', text: '#ef4444', glow: '0 0 40px rgba(239, 68, 68, 0.3)', label: 'Risk off — no new longs' },
  // Kill chain vocabulary (reconciled_verdict from /kill-shots-live)
  BOOST:      { bg: 'rgba(16, 185, 129, 0.15)', border: 'rgba(16, 185, 129, 0.4)', text: '#10b981', glow: '0 0 40px rgba(16, 185, 129, 0.3)', label: 'All layers aligned — high conviction long' },
  HOLD:       { bg: 'rgba(148, 163, 184, 0.1)', border: 'rgba(148, 163, 184, 0.2)', text: '#94a3b8', glow: 'none', label: 'Conflicting signals — wait for alignment' },
  WATCH:      { bg: 'rgba(234, 179, 8, 0.12)',  border: 'rgba(234, 179, 8, 0.3)',  text: '#eab308', glow: '0 0 30px rgba(234, 179, 8, 0.2)', label: 'Kill chain override — monitor before entry' },
  SOFT_VETO:  { bg: 'rgba(249, 115, 22, 0.12)', border: 'rgba(249, 115, 22, 0.3)', text: '#f97316', glow: '0 0 30px rgba(249, 115, 22, 0.2)', label: 'Soft veto — reduce size, no new longs' },
  HARD_VETO:  { bg: 'rgba(239, 68, 68, 0.15)',  border: 'rgba(239, 68, 68, 0.4)',  text: '#ef4444', glow: '0 0 40px rgba(239, 68, 68, 0.3)', label: 'Hard veto — risk off, no new positions' },
  WAR_VETO:   { bg: 'rgba(239, 68, 68, 0.15)',  border: 'rgba(239, 68, 68, 0.4)',  text: '#ef4444', glow: '0 0 40px rgba(239, 68, 68, 0.3)', label: 'WAR_VETO active — macro override, all longs suppressed' },
};

export function VerdictBanner({ verdict, summary, wallBreached, wallBreachDetails }: VerdictBannerProps) {
  const vs = wallBreached
    ? VERDICT_STYLES.SELL
    : (VERDICT_STYLES[verdict] || VERDICT_STYLES.NEUTRAL);

  return (
    <>
      {/* Wall breach alert */}
      {wallBreached && wallBreachDetails && (
        <div className="wall-breach-alert">
          <div className="wall-breach-alert__title">⚠️ SPY WALL BREACH</div>
          <div className="wall-breach-alert__details">
            SPY at ${wallBreachDetails.spy_price} — ${Math.abs(wallBreachDetails.delta).toFixed(2)} below call wall ${wallBreachDetails.call_wall} — detected {
              new Date(wallBreachDetails.breach_time + (wallBreachDetails.breach_time.endsWith('Z') ? '' : 'Z'))
                .toLocaleTimeString('en-US', {
                  timeZone: 'America/New_York',
                  hour: '2-digit',
                  minute: '2-digit',
                  hour12: true,
                })
            } ET
          </div>
        </div>
      )}

      {/* Verdict */}
      <div
        className="verdict-banner"
        style={{
          background: vs.bg,
          borderColor: vs.border,
          boxShadow: vs.glow,
        }}
      >
        <div className="verdict-text" style={{ color: vs.text }}>
          {wallBreached ? '⚠️ BREACH' : verdict}
        </div>
        <div className="verdict-label" style={{ color: vs.text }}>
          {wallBreached ? 'SPY below call wall — risk off' : vs.label}
        </div>
        <div className="verdict-summary">{summary}</div>
        <div style={{ color: vs.text, opacity: 0.7, fontSize: '11px', fontStyle: 'italic', marginTop: '6px', lineHeight: '1.5' }}>
          {wallBreached && 'SPY has broken below the call wall. Dealers are no longer selling into strength — the ceiling is gone. This is a mechanical shift, not an opinion. Reduce exposure or hedge.'}
          {!wallBreached && verdict === 'STRONG_BUY' && 'Multiple data layers agree: GEX, dark pool, COT, and vol regime all point the same direction. High-conviction setups are rare — size up when they appear.'}
          {!wallBreached && verdict === 'BUY' && 'The edge is present but not overwhelming. Trade the approved names from the scanner with normal position sizing.'}
          {!wallBreached && verdict === 'NEUTRAL' && 'No clear edge today. The data is conflicting or flat. Sitting out IS a trade. Preserve capital for when the setup is obvious.'}
          {!wallBreached && verdict === 'BOOST' && 'All kill chain layers aligned. COT, GEX, and dark pool all point the same direction. High-conviction setup — size up on approved names.'}
          {!wallBreached && verdict === 'HOLD' && 'Kill chain signals are conflicting. Divergence scorer says go but confluence is not there yet. Wait for alignment before committing capital.'}
          {!wallBreached && verdict === 'WATCH' && 'Kill chain override in effect. Morning brief and live signal chain disagree. Check Signal Chain for the specific layer causing the divergence.'}
          {!wallBreached && verdict === 'SOFT_VETO' && 'Soft veto conditions. One or more layers are flashing red. Reduce position size to 50% or sit out until the veto clears.'}
          {!wallBreached && (verdict === 'HARD_VETO' || verdict === 'WAR_VETO') && 'Hard veto or macro override active. No new longs. If positioned, tighten stops to breakeven immediately.'}
          {!wallBreached && verdict === 'CAUTION' && 'Signals are mixed. Some layers say go, others say wait. If you trade, cut position size in half. The market is deciding — let it decide before you commit.'}
          {!wallBreached && verdict === 'SELL' && 'Risk-off conditions. The data says reduce exposure. No new longs. If you are already positioned, tighten stops to breakeven.'}
        </div>
      </div>
    </>
  );
}
