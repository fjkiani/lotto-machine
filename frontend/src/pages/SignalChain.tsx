/**
 * SignalChain — /signal-chain
 * Full A→Z lineage: raw inputs → 5 scorers → kill chain gate → reconciliation.
 * ~270 lines. No bloat. Every number traceable.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, AlertOctagon, ArrowDown } from 'lucide-react';

import type { KillShotsResponse, KillChainResult, KillChainLayerMacro } from '../components/widgets/kill-shots/types';
import { PillarCardCot }   from '../components/widgets/kill-shots/PillarCardCot';
import { PillarCardGex }   from '../components/widgets/kill-shots/PillarCardGex';
import { PillarCardBrain } from '../components/widgets/kill-shots/PillarCardBrain';
import { PillarCardFedDp } from '../components/widgets/kill-shots/PillarCardFedDp';
import { PillarCardCombined } from '../components/signal-chain/PillarCardCombined';

const API = (import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1').replace('/api/v1', '');

// ── Verdict colour map ────────────────────────────────────────────────────────
const VC: Record<string, { fg: string; bg: string; border: string }> = {
  BOOST:     { fg: '#10b981', bg: 'rgba(16,185,129,0.12)',  border: '#10b981' },
  BUY:       { fg: '#3b82f6', bg: 'rgba(59,130,246,0.12)',  border: '#3b82f6' },
  HOLD:      { fg: '#a1a1aa', bg: 'rgba(161,161,170,0.08)', border: '#52525b' },
  WATCH:     { fg: '#eab308', bg: 'rgba(234,179,8,0.10)',   border: '#eab308' },
  NEUTRAL:   { fg: '#22d3ee', bg: 'rgba(34,211,238,0.06)',  border: '#22d3ee' },
  SOFT_VETO: { fg: '#f97316', bg: 'rgba(249,115,22,0.10)',  border: '#f97316' },
  HARD_VETO: { fg: '#f43f5e', bg: 'rgba(244,63,94,0.10)',   border: '#f43f5e' },
  WAR_VETO:  { fg: '#f43f5e', bg: 'rgba(244,63,94,0.10)',   border: '#f43f5e' },
};
const vc = (v?: string) => VC[v ?? ''] ?? VC.NEUTRAL;

// ── 1. Reconciled Verdict Bar (~40 lines) ─────────────────────────────────────
function ReconciledVerdictBar({ d }: { d: KillShotsResponse }) {
  const rv = d.reconciled_verdict ?? d.verdict;
  const c = vc(rv);
  const macro = d.kill_chain?.layer_macro;
  const isManual = macro?.oil_wti_source === 'manual';
  const isWarVeto = rv === 'WAR_VETO';

  return (
    <div className="rounded-xl border p-4 mb-1" style={{ background: c.bg, borderColor: c.border }}>
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full animate-pulse" style={{ background: c.fg }} />
          <span className="text-[9px] font-black text-zinc-500 uppercase tracking-[0.4em]">Reconciled Verdict</span>
          <span className="text-2xl font-black tracking-tight" style={{ color: c.fg }}>{rv}</span>
          {d.divergence_score != null && (
            <span className="text-[10px] font-mono text-zinc-500">score={d.divergence_score}</span>
          )}
        </div>
        {isWarVeto && macro && (
          <div className="flex items-center gap-2 text-[10px] font-mono">
            <span className="text-rose-400 font-black">WAR_STATUS {macro.value}/10</span>
            <span className="text-zinc-600">·</span>
            <span className="text-zinc-400">WTI ${macro.oil_wti?.toFixed(0)} <span className="text-zinc-600">src={macro.oil_wti_source}</span></span>
            {isManual && (
              <span className="px-2 py-0.5 rounded bg-amber-500/15 border border-amber-500/30 text-amber-400 font-black text-[9px] uppercase tracking-widest">
                ⚠ MANUAL OVERRIDE
              </span>
            )}
          </div>
        )}
      </div>
      {(d.reconciliation_reasons ?? []).length > 0 && (
        <ul className="mt-2 space-y-0.5">
          {d.reconciliation_reasons!.map((r, i) => (
            <li key={i} className="text-[10px] font-mono text-zinc-400 flex items-start gap-1.5">
              <span className="text-zinc-700 mt-0.5">›</span>
              <span className={r.toLowerCase().includes('manual') ? 'text-amber-400' : ''}>{r}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── 2. Raw Inputs Strip (~60 lines) ───────────────────────────────────────────
function RawInputsStrip({ d }: { d: KillShotsResponse }) {
  const l = d.layers;
  const kc = d.kill_chain;
  const spot = l.axlfi_spot ?? l.gex_spot_price;
  const callWall = l.axlfi_call_wall;
  const putWall = l.axlfi_put_wall;
  const ptsAbove = l.pts_above_call_wall;
  const gex = l.total_gex_dollars;
  const cotSpecs = l.cot_specs_net;
  const vix = l.vix;
  const rsi = l.rsi_14;
  const qqqDelta = l.qqq_sv_delta;
  const oilWti = l.oil_wti;

  const cell = (label: string, val: string | number | null | undefined, color?: string) => (
    <div className="flex flex-col gap-0.5 min-w-[80px]">
      <span className="text-[8px] font-black text-zinc-600 uppercase tracking-widest">{label}</span>
      <span className="text-[11px] font-black font-mono" style={{ color: color ?? '#e4e4e7' }}>
        {val != null ? String(val) : '—'}
      </span>
    </div>
  );

  const aboveColor = ptsAbove != null ? (ptsAbove > 0 ? '#eab308' : '#10b981') : undefined;
  const cotColor = cotSpecs != null ? (cotSpecs < -100000 ? '#f43f5e' : cotSpecs < 0 ? '#f97316' : '#10b981') : undefined;
  const vixColor = vix != null ? (vix > 25 ? '#f43f5e' : vix > 18 ? '#f97316' : '#10b981') : undefined;

  return (
    <div className="bg-zinc-950 border border-white/5 rounded-xl p-4">
      <span className="text-[8px] font-black text-zinc-600 uppercase tracking-[0.4em] block mb-3">Raw Inputs</span>
      <div className="flex flex-wrap gap-x-6 gap-y-3">
        {cell('SPY', spot != null ? `$${spot.toFixed(2)}` : null)}
        {cell('Call Wall', callWall != null ? `$${callWall}` : null)}
        {cell('Put Wall', putWall != null ? `$${putWall}` : null)}
        {cell('Pts vs Call Wall', ptsAbove != null ? (ptsAbove > 0 ? `+${ptsAbove.toFixed(1)}` : ptsAbove.toFixed(1)) : null, aboveColor)}
        {cell('GEX Regime', l.gex_regime)}
        {cell('Total GEX', gex != null ? `$${(gex / 1e6).toFixed(1)}M` : null)}
        {cell('COT Specs Net', cotSpecs != null ? cotSpecs.toLocaleString() : null, cotColor)}
        {cell('QQQ SV Δ', qqqDelta != null ? `${qqqDelta > 0 ? '+' : ''}${qqqDelta.toFixed(1)}pp` : null)}
        {cell('VIX', vix?.toFixed(2), vixColor)}
        {cell('RSI-14', rsi?.toFixed(1))}
        {cell('WTI Oil', oilWti != null ? `$${oilWti.toFixed(1)}` : null)}
        {cell('KC Confluence', kc?.confluence)}
      </div>
    </div>
  );
}

// ── 3. Scorer Pillars (~30 lines) ─────────────────────────────────────────────
function ScorerPillars({ d }: { d: KillShotsResponse }) {
  const l = d.layers;
  const scorers = [
    { name: 'COT',      boost: l.cot_boost ?? 0 },
    { name: 'GEX',      boost: l.gex_boost ?? 0 },
    { name: 'BRAIN',    boost: l.brain_boost ?? 0 },
    { name: 'FED/DP',   boost: l.fed_dp_boost ?? 0 },
    { name: 'COMBINED', boost: l.combined_boost ?? 0 },
  ];
  const total = d.divergence_score;
  const vStyle = vc(d.verdict);

  return (
    <div className="space-y-4">
      {/* Score tally */}
      <div className="bg-zinc-950 border border-white/5 rounded-xl px-4 py-3 flex items-center gap-3 flex-wrap text-[11px] font-mono">
        <span className="text-[8px] font-black text-zinc-600 uppercase tracking-widest">Score</span>
        {scorers.map((s, i) => (
          <React.Fragment key={s.name}>
            <span className="text-zinc-500">{s.name}</span>
            <span className="font-black" style={{ color: s.boost > 0 ? '#f97316' : '#52525b' }}>+{s.boost}</span>
            {i < scorers.length - 1 && <span className="text-zinc-700">+</span>}
          </React.Fragment>
        ))}
        <span className="text-zinc-700 mx-1">=</span>
        <span className="font-black text-white">{total}</span>
        <span className="text-zinc-700">→</span>
        <span className="font-black" style={{ color: vStyle.fg }}>{d.verdict}</span>
      </div>
      {/* Pillar cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        <PillarCardCot data={l} />
        <PillarCardGex data={l} />
        <PillarCardBrain data={l} />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <PillarCardFedDp data={l} />
        <PillarCardCombined data={l} />
      </div>
    </div>
  );
}

// ── 4. Kill Chain Gate (~80 lines) ────────────────────────────────────────────
function KillChainGate({ kc }: { kc: KillChainResult }) {
  const [open, setOpen] = useState<number | null>(null);
  const layers = [kc.layer_1, kc.layer_2, kc.layer_3, kc.layer_4, kc.layer_5];
  const layerNames = ['COT Extreme', 'GEX Negative', 'DVR Distribution', 'AXLFI Call Wall', 'QQQ Reshort'];

  return (
    <div className="bg-zinc-950 border border-white/5 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-white/5 flex items-center justify-between">
        <span className="text-[8px] font-black text-zinc-600 uppercase tracking-[0.4em]">Kill Chain Gate</span>
        <div className="flex items-center gap-3 text-[10px] font-mono">
          <span className="text-zinc-500">confluence=<span className="text-white font-black">{kc.confluence}</span></span>
          <span className="text-zinc-500">score=<span className="text-white font-black">{kc.score}</span></span>
          <span className="text-zinc-500">dir=<span className="text-white font-black">{kc.direction}</span></span>
        </div>
      </div>
      {layers.map((layer, i) => {
        const isOpen = open === i;
        return (
          <div key={i} className="border-b border-white/5 last:border-0">
            <button
              onClick={() => setOpen(isOpen ? null : i)}
              className="w-full px-4 py-3 flex items-center gap-3 hover:bg-white/[0.02] transition-colors text-left"
            >
              <span className="text-sm font-black w-4" style={{ color: layer.triggered ? '#10b981' : '#52525b' }}>
                {layer.triggered ? '✓' : '✗'}
              </span>
              <span className="text-[11px] font-black text-zinc-300 w-36">{layerNames[i]}</span>
              <span className="text-[10px] font-mono text-zinc-500 flex-1">
                {layer.signal ?? '—'}
                {layer.value != null && <span className="text-zinc-600 ml-2">val={layer.value}</span>}
              </span>
              <span className="text-[9px] text-zinc-700">{isOpen ? '▲' : '▼'}</span>
            </button>
            {isOpen && (
              <div className="px-4 pb-3 pt-1 bg-black/20 text-[10px] font-mono text-zinc-500 space-y-1">
                {layer.specs_long != null && <div>specs_long={layer.specs_long?.toLocaleString()} · specs_short={layer.specs_short?.toLocaleString()}</div>}
                {layer.pts_above_call_wall != null && <div>pts_above_call_wall={layer.pts_above_call_wall?.toFixed(2)}</div>}
                {layer.report_date && <div>report_date={layer.report_date}</div>}
                {layer.symbol && <div>symbol={layer.symbol}</div>}
                {layer.raw_value != null && <div>raw_value={layer.raw_value}</div>}
              </div>
            )}
          </div>
        );
      })}
      {/* Macro row */}
      {kc.layer_macro && <MacroRow macro={kc.layer_macro} />}
      {/* Points footer */}
      <div className="px-4 py-2 bg-black/20 flex items-center gap-4 text-[9px] font-mono text-zinc-600">
        <span>bullish_pts={kc.bullish_points}</span>
        <span>bearish_pts={kc.bearish_points}</span>
        <span>triggered={kc.triggered_count}/5</span>
        <span>armed={String(kc.armed)}</span>
      </div>
    </div>
  );
}

function MacroRow({ macro }: { macro: KillChainLayerMacro }) {
  const [open, setOpen] = useState(false);
  const isManual = macro.oil_wti_source === 'manual';
  return (
    <div className="border-t border-white/5">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-4 py-3 flex items-center gap-3 hover:bg-white/[0.02] transition-colors text-left"
      >
        <span className="text-sm font-black w-4" style={{ color: macro.triggered ? '#f43f5e' : '#52525b' }}>
          {macro.triggered ? '✓' : '✗'}
        </span>
        <span className="text-[11px] font-black text-zinc-300 w-36">Macro / WAR</span>
        <span className="text-[10px] font-mono text-zinc-500 flex-1">
          {macro.signal} · war_status={macro.value}/10 · WTI=${macro.oil_wti?.toFixed(0)}
          {isManual && <span className="ml-2 text-amber-400 font-black">⚠ MANUAL</span>}
        </span>
        <span className="text-[9px] text-zinc-700">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="px-4 pb-3 pt-1 bg-black/20 text-[10px] font-mono space-y-1">
          <div className="text-zinc-500">veto_longs={String(macro.veto_longs)} · reason={macro.veto_reason}</div>
          {macro.war_status_breakdown && <div className="text-zinc-600">{macro.war_status_breakdown}</div>}
          {macro.manual_override_warning && <div className="text-amber-400">{macro.manual_override_warning}</div>}
          <div className="text-zinc-600">oil_src={macro.oil_wti_source}</div>
        </div>
      )}
    </div>
  );
}

// ── 5. Reconciliation Engine (~60 lines) ──────────────────────────────────────
function ReconciliationEngine({ d }: { d: KillShotsResponse }) {
  const kc = d.kill_chain;
  const rv = d.reconciled_verdict ?? d.verdict;
  const dvStyle = vc(d.verdict);
  const kcStyle = vc(kc?.verdict);
  const rvStyle = vc(rv);

  return (
    <div className="bg-zinc-950 border border-white/5 rounded-xl p-4 space-y-4">
      <span className="text-[8px] font-black text-zinc-600 uppercase tracking-[0.4em] block">Reconciliation Engine</span>
      {/* Two verdicts side by side */}
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-lg border p-3" style={{ background: dvStyle.bg, borderColor: dvStyle.border }}>
          <div className="text-[8px] font-black text-zinc-600 uppercase tracking-widest mb-1">Divergence Scorer</div>
          <div className="text-lg font-black" style={{ color: dvStyle.fg }}>{d.verdict}</div>
          <div className="text-[9px] font-mono text-zinc-600 mt-0.5">score={d.divergence_score}</div>
        </div>
        <div className="rounded-lg border p-3" style={{ background: kcStyle.bg, borderColor: kcStyle.border }}>
          <div className="text-[8px] font-black text-zinc-600 uppercase tracking-widest mb-1">Kill Chain</div>
          <div className="text-lg font-black" style={{ color: kcStyle.fg }}>{kc?.verdict ?? '—'}</div>
          <div className="text-[9px] font-mono text-zinc-600 mt-0.5">confluence={kc?.confluence ?? '—'}</div>
        </div>
      </div>
      {/* Arrow + final */}
      <div className="flex flex-col items-center gap-2">
        <ArrowDown className="w-4 h-4 text-zinc-700" />
        <div className="rounded-xl border px-6 py-3 text-center" style={{ background: rvStyle.bg, borderColor: rvStyle.border }}>
          <div className="text-[8px] font-black text-zinc-500 uppercase tracking-widest mb-1">Reconciled</div>
          <div className="text-2xl font-black" style={{ color: rvStyle.fg }}>{rv}</div>
        </div>
      </div>
      {/* Reasons */}
      {(d.reconciliation_reasons ?? []).length > 0 && (
        <ul className="space-y-1 pt-1 border-t border-white/5">
          {d.reconciliation_reasons!.map((r, i) => (
            <li key={i} className="text-[10px] font-mono text-zinc-500 flex items-start gap-1.5">
              <span className="text-zinc-700 mt-0.5">›</span>
              <span className={r.toLowerCase().includes('manual') ? 'text-amber-400' : ''}>{r}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Chain Connector ───────────────────────────────────────────────────────────
function ChainConnector({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center py-2 gap-1">
      <div className="w-px h-4 bg-zinc-800" />
      <span className="text-[8px] font-black text-zinc-700 uppercase tracking-widest">{label}</span>
      <div className="w-px h-4 bg-zinc-800" />
      <ArrowDown className="w-3 h-3 text-zinc-700" />
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export function SignalChain() {
  const [data, setData] = useState<KillShotsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastSync, setLastSync] = useState('');

  const fetch_ = useCallback(async () => {
    try {
      const r = await fetch(`${API}/kill-shots-live`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j: KillShotsResponse = await r.json();
      if (j.error) throw new Error(j.error);
      setData(j);
      setError(null);
      setLastSync(new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true }));
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetch_(); const t = setInterval(fetch_, 30_000); return () => clearInterval(t); }, [fetch_]);

  if (loading) return (
    <div className="min-h-screen bg-[#050507] flex items-center justify-center">
      <span className="text-[10px] font-black font-mono text-zinc-600 uppercase tracking-[0.6em] animate-pulse">Building Chain…</span>
    </div>
  );

  if (error || !data) return (
    <div className="min-h-screen bg-[#050507] flex items-center justify-center gap-3">
      <AlertOctagon className="w-5 h-5 text-rose-500" />
      <span className="text-sm font-mono text-rose-500">{error ?? 'No data'}</span>
      <button onClick={fetch_} className="px-3 py-1.5 bg-zinc-900 border border-zinc-700 rounded text-xs text-zinc-400 hover:text-white">Retry</button>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#050507] text-white">
      {/* Header */}
      <div className="sticky top-0 z-40 bg-[#050507]/95 backdrop-blur border-b border-white/5 px-6 py-3 flex items-center justify-between">
        <span className="text-sm font-black tracking-tight">Signal Chain</span>
        <div className="flex items-center gap-3">
          {lastSync && <span className="text-[9px] font-mono text-zinc-700 hidden md:block">sync {lastSync}</span>}
          <button onClick={fetch_} className="p-1.5 bg-zinc-900 border border-white/5 rounded hover:bg-zinc-800 transition-colors">
            <RefreshCw className="w-3.5 h-3.5 text-zinc-500 hover:text-cyan-400" />
          </button>
        </div>
      </div>

      {/* Chain */}
      <div className="max-w-5xl mx-auto px-4 py-6 space-y-0">
        <ReconciledVerdictBar d={data} />
        <ChainConnector label="raw inputs" />
        <RawInputsStrip d={data} />
        <ChainConnector label="feeds into" />
        <ScorerPillars d={data} />
        <ChainConnector label="gated by" />
        {data.kill_chain
          ? <KillChainGate kc={data.kill_chain} />
          : <div className="bg-zinc-950 border border-white/5 rounded-xl p-6 text-center text-[10px] font-mono text-zinc-600">kill_chain not in response — check /kill-shots-live</div>
        }
        <ChainConnector label="synthesized by" />
        <ReconciliationEngine d={data} />

        {/* Footer */}
        <div className="pt-6 pb-2 text-center text-[8px] font-mono text-zinc-800 uppercase tracking-widest">
          {data.timestamp ? new Date(data.timestamp).toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hour12: true }) + ' ET' : '—'} · click any layer row to expand · ⓘ on data points to audit
        </div>
      </div>
    </div>
  );
}
