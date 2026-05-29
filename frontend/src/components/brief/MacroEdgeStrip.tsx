/**
 * MacroEdgeStrip — compact horizontal strip showing key macro edge data.
 * Replaces UnifiedBriefView's 6 bloated sub-components with one clean strip.
 * Fetches /brief/master every 120s. No Groq/oracle calls.
 */
import { useMasterBrief } from '../../hooks/useMasterBrief';

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span
      className="px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-widest border"
      style={{ color, borderColor: color + '40', background: color + '15' }}
    >
      {label}
    </span>
  );
}

function Dot() {
  return <span className="text-zinc-700 text-[10px]">·</span>;
}

const SIGNAL_COLOR: Record<string, string> = {
  BEAT: '#10b981',
  IN_LINE: '#a1a1aa',
  MISS_LIKELY: '#f43f5e',
  MISS: '#f43f5e',
  BEAT_LIKELY: '#10b981',
};

export function MacroEdgeStrip() {
  const { data, loading } = useMasterBrief(120_000);

  if (loading || !data) return null;

  const regime = data.macro_regime?.regime ?? '—';
  const econ = data.economic_veto;
  const fed = data.fed_intelligence?.rate_path;
  const adp = data.adp_prediction;
  const gdp = data.gdp_nowcast;

  const nextEvent = econ?.next_event ?? null;
  const hoursAway = econ?.hours_away ?? null;
  const confidenceCap = econ?.confidence_cap ?? null;

  const nextMeeting = fed?.next_meeting ?? null;
  const daysAway = fed?.days_away ?? null;
  const pCut = fed?.may_p_cut ?? null;

  return (
    <div
      className="border-b px-4 py-2 flex items-center flex-wrap gap-x-3 gap-y-1"
      style={{
        background: 'rgba(9,9,11,0.95)',
        borderColor: 'rgba(255,255,255,0.05)',
      }}
    >
      {/* Macro regime */}
      <div className="flex items-center gap-1.5">
        <span className="text-[9px] font-black text-zinc-600 uppercase tracking-widest">Regime</span>
        <Badge label={regime} color="#22d3ee" />
      </div>

      <Dot />

      {/* Next event + countdown */}
      {nextEvent && (
        <>
          <div className="flex items-center gap-1.5">
            <span className="text-[9px] font-black text-zinc-600 uppercase tracking-widest">Next</span>
            <span className="text-[10px] font-mono text-zinc-300">{nextEvent}</span>
            {hoursAway != null && (
              <span className="text-[10px] font-mono text-zinc-500">
                ({hoursAway < 24 ? `${hoursAway}h` : `${Math.round(hoursAway / 24)}d`})
              </span>
            )}
          </div>
          <Dot />
        </>
      )}

      {/* Confidence cap */}
      {confidenceCap != null && (
        <>
          <div className="flex items-center gap-1.5">
            <span className="text-[9px] font-black text-zinc-600 uppercase tracking-widest">Cap</span>
            <span
              className="text-[10px] font-mono font-black"
              style={{ color: confidenceCap < 70 ? '#f97316' : '#a1a1aa' }}
            >
              {confidenceCap}%
            </span>
          </div>
          <Dot />
        </>
      )}

      {/* ADP signal */}
      {adp && !adp.error && (
        <>
          <div className="flex items-center gap-1.5">
            <span className="text-[9px] font-black text-zinc-600 uppercase tracking-widest">ADP</span>
            <Badge label={adp.signal} color={SIGNAL_COLOR[adp.signal] ?? '#a1a1aa'} />
            {adp.delta != null && (
              <span className="text-[10px] font-mono text-zinc-500">
                Δ{adp.delta > 0 ? '+' : ''}{adp.delta}k
              </span>
            )}
          </div>
          <Dot />
        </>
      )}

      {/* GDP signal */}
      {gdp && !gdp.error && (
        <>
          <div className="flex items-center gap-1.5">
            <span className="text-[9px] font-black text-zinc-600 uppercase tracking-widest">GDP</span>
            <Badge label={gdp.signal} color={SIGNAL_COLOR[gdp.signal] ?? '#a1a1aa'} />
            {gdp.vs_consensus != null && (
              <span className="text-[10px] font-mono text-zinc-500">
                {gdp.vs_consensus > 0 ? '+' : ''}{gdp.vs_consensus.toFixed(1)}% vs est
              </span>
            )}
          </div>
          <Dot />
        </>
      )}

      {/* Fed path */}
      {nextMeeting && (
        <div className="flex items-center gap-1.5">
          <span className="text-[9px] font-black text-zinc-600 uppercase tracking-widest">Fed</span>
          <span className="text-[10px] font-mono text-zinc-300">{nextMeeting}</span>
          {daysAway != null && (
            <span className="text-[10px] font-mono text-zinc-500">({daysAway}d)</span>
          )}
          {pCut != null && (
            <span
              className="text-[10px] font-mono font-black"
              style={{ color: pCut > 50 ? '#10b981' : '#a1a1aa' }}
            >
              cut {Math.round(pCut * 100)}%
            </span>
          )}
        </div>
      )}
    </div>
  );
}
