/**
 * SignalChainView — full A→Z signal lineage.
 *
 * One file. All sub-components co-located. No separate files for each step.
 * Reuses existing PillarCard* components (COT, GEX, Brain, FedDp, Combined).
 *
 * Sections:
 *   1. ReconciledVerdictBar  — final decision + WAR_VETO warning
 *   2. HistoryStrip          — yesterday vs today delta (COT, GEX, score, verdict)
 *   3. RawInputsStrip        — all live numbers with ⓘ tooltips
 *   4. ScorerPillars         — 5 scorers + score tally
 *   5. KillChainGate         — 5 layers + macro, click-to-expand
 *   6. ReconciliationEngine  — two verdicts → reconciled + reasons
 *   7. TrainButton           — JSONL snapshot append for fine-tuning
 *
 * Data: GET /kill-shots-live (30s poll) + GET /api/snapshots?limit=2 (history)
 * No new backend endpoints for the chain itself — training.py is the only addition.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { RefreshCw, AlertOctagon, ArrowDown, Info, Database } from 'lucide-react';

import type { KillShotsResponse, KillChainResult, KillChainLayerMacro } from '../widgets/kill-shots/types';
import { PillarCardCot }      from '../widgets/kill-shots/PillarCardCot';
import { PillarCardGex }      from '../widgets/kill-shots/PillarCardGex';
import { PillarCardBrain }    from '../widgets/kill-shots/PillarCardBrain';
import { PillarCardFedDp }    from '../widgets/kill-shots/PillarCardFedDp';
import { PillarCardCombined } from './PillarCardCombined';

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

// ── Tooltip definitions ───────────────────────────────────────────────────────
// source: where the number comes from. why: why it matters for the decision.
const TIPS: Record<string, { source: string; why: string }> = {
  spy:        { source: 'CBOE AXLFI live feed',           why: 'Reference price for all wall and gamma calculations.' },
  call_wall:  { source: 'CBOE options open interest',     why: 'Strike with largest call OI — acts as dealer gamma resistance. Price tends to stall or reverse here.' },
  put_wall:   { source: 'CBOE options open interest',     why: 'Strike with largest put OI — acts as dealer gamma support. Price tends to bounce here.' },
  pts_wall:   { source: 'Derived: spot − call_wall',      why: 'Positive = above resistance (bearish gamma setup, dealers short gamma). Negative = below support.' },
  gex_regime: { source: 'CBOE net gamma exposure',        why: 'POSITIVE = dealers suppress vol (buy dips, sell rips). NEGATIVE = dealers amplify vol (momentum accelerates).' },
  total_gex:  { source: 'CBOE net gamma $M',              why: 'Size of dealer hedging obligation. Large positive GEX = strong vol suppression. Flip to negative = regime change.' },
  cot_specs:  { source: 'CFTC COT report (released Fri)', why: 'Extreme net short = crowded trade = squeeze risk. Extreme net long = distribution risk.' },
  qqq_delta:  { source: 'Stockgrid short volume data',    why: 'Rising short vol delta = institutional distribution. Spike > +5pp = reshort signal.' },
  vix:        { source: 'CBOE VIX index',                 why: '>25 = elevated fear, wider stops. >30 = crisis regime. <15 = complacency, vol compression.' },
  rsi:        { source: '14-period RSI on SPY',           why: '>70 = overbought (TECH scorer adds bearish points). <30 = oversold (potential reversal).' },
  oil_wti:    { source: 'yfinance / fallback $95 stress', why: '>90 adds +2 to war_status. >95 = WAR_VETO risk. "manual" src = env var override, not live feed.' },
  confluence: { source: 'Kill chain engine',              why: 'SINGLE=1, DOUBLE=2, TRIPLE=3, QUAD=4 layers triggered. DOUBLE+ = armed for signal.' },
  cot_boost:  { source: 'Kill chain layer 1 (COT)',       why: '+3 = extreme short positioning (>100K net short). Triggers bearish confluence.' },
  gex_boost:  { source: 'Kill chain layer 2 (GEX)',       why: '+2 = negative gamma regime. Dealers amplify moves — momentum accelerates.' },
  brain_boost:{ source: 'LangGraph alpha graph (OpenRouter Nemotron)', why: 'Composite signal from 5+ sub-agents. +4 = high conviction. Runs every 30min on Render.' },
  fed_boost:  { source: 'Fed calendar + dark pool',       why: 'Fed veto window (48h around FOMC) or DP distribution signal (short_vol_pct > 55%).' },
  comb_boost: { source: 'Confluence rules engine',        why: 'COT+GEX, COT+above-wall, QQQ reshort, politician cluster. Each rule = +1 or +2.' },
  war_status:     { source: 'Macro overlay (oil + geopolitical)', why: '0-10 scale. ≥7 = WAR_VETO overrides all long signals regardless of divergence score.' },
  score:          { source: 'Divergence scorer (sum of 5 pillars)', why: 'Total points from COT+GEX+BRAIN+FED_DP+COMBINED. Threshold determines verdict (BOOST/WATCH/VETO).' },
  dp_trend_boost: { source: 'DpTrendScorer — Stockgrid 2-day SV% delta', why: '+1 = SV% falling >5pp (accumulation). -1 = SV% rising >5pp above 55% (distribution). 0 = neutral.' },
  sv_pct_today:   { source: 'Stockgrid short volume % (today)', why: 'SPY short volume as % of total. >55% = institutions distributing. <45% = accumulation signal.' },
  sv_2d_delta:    { source: 'Stockgrid SV% delta (today − yesterday)', why: 'Rate of change. >+5pp spike = reshort signal. <-5pp drop = covering = bullish.' },
  tech_boost:     { source: 'TechScorer — RSI-14 on SPY', why: '+1 = RSI oversold (<30). -1 = RSI overbought (>70). Prevents chasing extended moves.' },
  geo_boost:      { source: 'GeoScorer — WTI oil price + geopolitical flags', why: 'Feeds war_status. High oil = macro headwind. WAR_VETO fires at war_status ≥7.' },
};

// ── Tooltip component ─────────────────────────────────────────────────────────
// Click-to-toggle (not hover) — works on mobile, no z-index fights.
// One popover open at a time via shared openTip state passed from parent.

interface TipProps {
  id: string;
  openTip: string | null;
  setOpenTip: (id: string | null) => void;
}

function Tip({ id, openTip, setOpenTip }: TipProps) {
  const tip = TIPS[id];
  if (!tip) return null;
  const isOpen = openTip === id;
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpenTip(null);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [isOpen, setOpenTip]);

  return (
    <div ref={ref} className="relative inline-flex items-center">
      <button
        onClick={(e) => { e.stopPropagation(); setOpenTip(isOpen ? null : id); }}
        className="ml-1 text-zinc-700 hover:text-cyan-500 transition-colors"
        aria-label={`Info: ${id}`}
      >
        <Info className="w-2.5 h-2.5" />
      </button>
      {isOpen && (
        <div className="absolute left-4 top-0 z-50 w-64 bg-zinc-900 border border-zinc-700 rounded-lg p-3 shadow-xl">
          <div className="text-[9px] font-black text-zinc-500 uppercase tracking-widest mb-1">Source</div>
          <div className="text-[10px] text-zinc-300 mb-2">{tip.source}</div>
          <div className="text-[9px] font-black text-zinc-500 uppercase tracking-widest mb-1">Why it matters</div>
          <div className="text-[10px] text-zinc-400 leading-relaxed">{tip.why}</div>
        </div>
      )}
    </div>
  );
}

// ── 1. Reconciled Verdict Bar ─────────────────────────────────────────────────
function ReconciledVerdictBar({ d, openTip, setOpenTip }: { d: KillShotsResponse; openTip: string | null; setOpenTip: (id: string | null) => void }) {
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
            <span className="text-[10px] font-mono text-zinc-500 flex items-center">
              score={d.divergence_score}
              <Tip id="score" openTip={openTip} setOpenTip={setOpenTip} />
            </span>
          )}
        </div>
        {isWarVeto && macro && (
          <div className="flex items-center gap-2 text-[10px] font-mono">
            <span className="text-rose-400 font-black flex items-center gap-0.5">
              WAR_STATUS {macro.value}/10
              <Tip id="war_status" openTip={openTip} setOpenTip={setOpenTip} />
            </span>
            <span className="text-zinc-600">·</span>
            <span className="text-zinc-400">
              WTI ${macro.oil_wti?.toFixed(0)}
              <Tip id="oil_wti" openTip={openTip} setOpenTip={setOpenTip} />
              <span className="text-zinc-600 ml-1">src={macro.oil_wti_source}</span>
            </span>
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

// ── 2. History Strip ──────────────────────────────────────────────────────────
// Fetches GET /api/snapshots?limit=2 — compares latest vs previous row.
// Fields: spy_price, cot_specs_net, gex_net, kill_chain_score, kill_chain_verdict.

interface SnapRow {
  captured_at: string;
  spy_price: number | null;
  cot_net: number | null;
  score: number | null;
  verdict: string | null;
  gex_net?: number | null;
}

function HistoryStrip() {
  const [rows, setRows] = useState<SnapRow[]>([]);

  useEffect(() => {
    fetch(`${API}/api/snapshots?limit=2`)
      .then(r => r.ok ? r.json() : null)
      .then(j => { if (j?.snapshots?.length >= 2) setRows(j.snapshots.slice(0, 2)); })
      .catch(() => {});
  }, []);

  if (rows.length < 2) return null;

  const [now, prev] = rows;
  const delta = (a: number | null, b: number | null, fmt: (n: number) => string) => {
    if (a == null || b == null) return null;
    const d = a - b;
    const color = d > 0 ? '#10b981' : d < 0 ? '#f43f5e' : '#71717a';
    return <span style={{ color }} className="font-black">{d > 0 ? '+' : ''}{fmt(d)}</span>;
  };

  return (
    <div className="bg-zinc-950 border border-white/5 rounded-xl px-4 py-3 flex items-center gap-6 flex-wrap text-[10px] font-mono">
      <span className="text-[8px] font-black text-zinc-600 uppercase tracking-[0.4em]">Δ vs prev snapshot</span>
      <span className="text-zinc-600">
        SPY {delta(now.spy_price, prev.spy_price, n => `$${n.toFixed(2)}`)}
      </span>
      <span className="text-zinc-600">
        COT {delta(now.cot_net, prev.cot_net, n => n.toLocaleString())}
      </span>
      <span className="text-zinc-600">
        Score {delta(now.score, prev.score, n => String(n))}
      </span>
      <span className="text-zinc-600">
        Verdict <span className="text-zinc-400">{prev.verdict ?? '—'}</span>
        <span className="text-zinc-700 mx-1">→</span>
        <span style={{ color: vc(now.verdict ?? '').fg }} className="font-black">{now.verdict ?? '—'}</span>
      </span>
      <span className="text-zinc-700 text-[8px]">
        {new Date(now.captured_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true })} ET
      </span>
    </div>
  );
}

// ── 3. Raw Inputs Strip ───────────────────────────────────────────────────────
function RawInputsStrip({ d, openTip, setOpenTip }: { d: KillShotsResponse; openTip: string | null; setOpenTip: (id: string | null) => void }) {
  const l = d.layers;
  const kc = d.kill_chain;
  const spot = l.axlfi_spot ?? l.gex_spot_price;
  const ptsAbove = l.pts_above_call_wall;
  const gex = l.total_gex_dollars;
  const cotSpecs = l.cot_specs_net;
  const vix = l.vix;
  const rsi = l.rsi_14;
  const qqqDelta = l.qqq_sv_delta;
  const oilWti = l.oil_wti;

  const aboveColor = ptsAbove != null ? (ptsAbove > 0 ? '#eab308' : '#10b981') : undefined;
  const cotColor = cotSpecs != null ? (cotSpecs < -100000 ? '#f43f5e' : cotSpecs < 0 ? '#f97316' : '#10b981') : undefined;
  const vixColor = vix != null ? (vix > 25 ? '#f43f5e' : vix > 18 ? '#f97316' : '#10b981') : undefined;

  const cell = (label: string, val: string | null | undefined, tipId: string, color?: string) => (
    <div className="flex flex-col gap-0.5 min-w-[80px]">
      <span className="text-[8px] font-black text-zinc-600 uppercase tracking-widest flex items-center gap-0.5">
        {label}
        <Tip id={tipId} openTip={openTip} setOpenTip={setOpenTip} />
      </span>
      <span className="text-[11px] font-black font-mono" style={{ color: color ?? '#e4e4e7' }}>
        {val ?? '—'}
      </span>
    </div>
  );

  return (
    <div className="bg-zinc-950 border border-white/5 rounded-xl p-4">
      <span className="text-[8px] font-black text-zinc-600 uppercase tracking-[0.4em] block mb-3">Raw Inputs</span>
      <div className="flex flex-wrap gap-x-6 gap-y-3">
        {cell('SPY',           spot != null ? `$${spot.toFixed(2)}` : null,                                                    'spy')}
        {cell('Call Wall',     l.axlfi_call_wall != null ? `$${l.axlfi_call_wall}` : null,                                     'call_wall')}
        {cell('Put Wall',      l.axlfi_put_wall != null ? `$${l.axlfi_put_wall}` : null,                                       'put_wall')}
        {cell('Pts vs Wall',   ptsAbove != null ? (ptsAbove > 0 ? `+${ptsAbove.toFixed(1)}` : ptsAbove.toFixed(1)) : null,    'pts_wall', aboveColor)}
        {cell('GEX Regime',    l.gex_regime ?? null,                                                                           'gex_regime')}
        {cell('Total GEX',     gex != null ? `$${(gex / 1e6).toFixed(1)}M` : null,                                            'total_gex')}
        {cell('COT Specs',     cotSpecs != null ? cotSpecs.toLocaleString() : null,                                            'cot_specs', cotColor)}
        {cell('QQQ SV Δ',      qqqDelta != null ? `${qqqDelta > 0 ? '+' : ''}${qqqDelta.toFixed(1)}pp` : null,                'qqq_delta')}
        {cell('VIX',           vix?.toFixed(2) ?? null,                                                                        'vix', vixColor)}
        {cell('RSI-14',        rsi?.toFixed(1) ?? null,                                                                        'rsi')}
        {cell('WTI Oil',       oilWti != null ? `$${oilWti.toFixed(1)}` : null,                                               'oil_wti')}
        {cell('KC Confluence', kc?.confluence ?? null,                                                                         'confluence')}
        {cell('DP SV%',        l.sv_pct_today != null ? `${l.sv_pct_today.toFixed(1)}%` : null,                                'sv_pct_today', l.sv_pct_today != null ? (l.sv_pct_today > 55 ? '#f43f5e' : l.sv_pct_today < 45 ? '#10b981' : undefined) : undefined)}
        {cell('SV Δ 2d',       l.sv_2d_delta != null ? `${l.sv_2d_delta > 0 ? '+' : ''}${l.sv_2d_delta.toFixed(1)}pp` : null, 'sv_2d_delta',  l.sv_2d_delta != null ? (l.sv_2d_delta > 5 ? '#f43f5e' : l.sv_2d_delta < -5 ? '#10b981' : undefined) : undefined)}
      </div>
    </div>
  );
}

// ── 4. Scorer Pillars ─────────────────────────────────────────────────────────
function ScorerPillars({ d, openTip, setOpenTip }: { d: KillShotsResponse; openTip: string | null; setOpenTip: (id: string | null) => void }) {
  const l = d.layers;
  const primaryScorers = [
    { name: 'COT',      boost: l.cot_boost ?? 0,      tipId: 'cot_boost' },
    { name: 'GEX',      boost: l.gex_boost ?? 0,      tipId: 'gex_boost' },
    { name: 'BRAIN',    boost: l.brain_boost ?? 0,    tipId: 'brain_boost' },
    { name: 'FED/DP',   boost: l.fed_dp_boost ?? 0,   tipId: 'fed_boost' },
    { name: 'COMBINED', boost: l.combined_boost ?? 0, tipId: 'comb_boost' },
  ];
  const secondaryScorers = [
    { name: 'TECH',     boost: l.tech_boost ?? 0,     tipId: 'tech_boost' },
    { name: 'GEO',      boost: l.geo_boost ?? 0,      tipId: 'geo_boost' },
    { name: 'DP_TREND', boost: l.dp_trend_boost ?? 0, tipId: 'dp_trend_boost' },
    { name: 'OPEX',     boost: l.opex_boost ?? 0,     tipId: 'comb_boost' },
    { name: 'SENTIMENT',boost: l.sentiment_boost ?? 0,tipId: 'comb_boost' },
  ];
  const total = d.divergence_score;
  const vStyle = vc(d.verdict);

  return (
    <div className="space-y-4">
      {/* Primary scorers row */}
      <div className="bg-zinc-950 border border-white/5 rounded-xl px-4 py-3 flex items-center gap-3 flex-wrap text-[11px] font-mono">
        <span className="text-[8px] font-black text-zinc-600 uppercase tracking-widest">Score</span>
        {primaryScorers.map((s, i) => (
          <React.Fragment key={s.name}>
            <span className="text-zinc-500 flex items-center">
              {s.name}
              <Tip id={s.tipId} openTip={openTip} setOpenTip={setOpenTip} />
            </span>
            <span className="font-black" style={{ color: s.boost > 0 ? '#f97316' : s.boost < 0 ? '#f43f5e' : '#52525b' }}>{s.boost > 0 ? '+' : ''}{s.boost}</span>
            {i < primaryScorers.length - 1 && <span className="text-zinc-700">+</span>}
          </React.Fragment>
        ))}
        <span className="text-zinc-700 mx-1">=</span>
        <span className="font-black text-white">{total}</span>
        <span className="text-zinc-700">→</span>
        <span className="font-black" style={{ color: vStyle.fg }}>{d.verdict}</span>
      </div>
      {/* Secondary scorers row */}
      <div className="bg-zinc-950/60 border border-white/[0.03] rounded-xl px-4 py-2.5 flex items-center gap-3 flex-wrap text-[10px] font-mono">
        <span className="text-[8px] font-black text-zinc-700 uppercase tracking-widest">Secondary</span>
        {secondaryScorers.map((s, i) => (
          <React.Fragment key={s.name}>
            <span className="text-zinc-600 flex items-center">
              {s.name}
              <Tip id={s.tipId} openTip={openTip} setOpenTip={setOpenTip} />
            </span>
            <span className="font-black" style={{ color: s.boost > 0 ? '#f97316' : s.boost < 0 ? '#f43f5e' : '#3f3f46' }}>{s.boost > 0 ? '+' : ''}{s.boost}</span>
            {i < secondaryScorers.length - 1 && <span className="text-zinc-800">+</span>}
          </React.Fragment>
        ))}
      </div>
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

// ── 5. Kill Chain Gate ────────────────────────────────────────────────────────
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
      {kc.layer_macro && <MacroRow macro={kc.layer_macro} />}
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

// ── 6. Reconciliation Engine ──────────────────────────────────────────────────
function ReconciliationEngine({ d }: { d: KillShotsResponse }) {
  const kc = d.kill_chain;
  const rv = d.reconciled_verdict ?? d.verdict;
  const dvStyle = vc(d.verdict);
  const kcStyle = vc(kc?.verdict);
  const rvStyle = vc(rv);

  return (
    <div className="bg-zinc-950 border border-white/5 rounded-xl p-4 space-y-4">
      <span className="text-[8px] font-black text-zinc-600 uppercase tracking-[0.4em] block">Reconciliation Engine</span>
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
      <div className="flex flex-col items-center gap-2">
        <ArrowDown className="w-4 h-4 text-zinc-700" />
        <div className="rounded-xl border px-6 py-3 text-center" style={{ background: rvStyle.bg, borderColor: rvStyle.border }}>
          <div className="text-[8px] font-black text-zinc-500 uppercase tracking-widest mb-1">Reconciled</div>
          <div className="text-2xl font-black" style={{ color: rvStyle.fg }}>{rv}</div>
        </div>
      </div>
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

// ── 7. Train Button ───────────────────────────────────────────────────────────
type TrainState = 'idle' | 'saving' | 'saved' | 'error';

function TrainButton({ d }: { d: KillShotsResponse }) {
  const [state, setState] = useState<TrainState>('idle');
  const [total, setTotal] = useState<number | null>(null);
  const [errMsg, setErrMsg] = useState('');

  const save = async () => {
    setState('saving');
    try {
      const res = await fetch(`${API}/api/v1/training/snapshot`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          payload: d,
          label: d.reconciled_verdict ?? d.verdict,
          note: 'Manual label from operator',
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const j = await res.json();
      setTotal(j.total_records ?? null);
      setState('saved');
      setTimeout(() => setState('idle'), 5000);
    } catch (e: any) {
      setErrMsg(e.message || 'Save failed');
      setState('error');
      setTimeout(() => setState('idle'), 4000);
    }
  };

  return (
    <div className="flex items-center justify-between flex-wrap gap-3 pt-4 border-t border-white/5">
      <div className="flex items-center gap-2">
        <Database className="w-3.5 h-3.5 text-zinc-600" />
        <span className="text-[9px] font-black text-zinc-600 uppercase tracking-widest">Training Pipeline</span>
      </div>
      <div className="flex items-center gap-3">
        {state === 'saved' && total != null && (
          <span className="text-[10px] font-mono text-emerald-400">
            Snapshot saved ({total} total){total >= 50 ? ' — ready to export' : ` — ${50 - total} more to go`}
          </span>
        )}
        {state === 'error' && (
          <span className="text-[10px] font-mono text-rose-400">{errMsg}</span>
        )}
        <button
          onClick={save}
          disabled={state === 'saving'}
          className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900 border border-zinc-700 rounded-lg text-[10px] font-black text-zinc-400 hover:text-cyan-400 hover:border-cyan-500/40 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {state === 'saving' ? (
            <><RefreshCw className="w-3 h-3 animate-spin" /> Saving…</>
          ) : state === 'saved' ? (
            <><span className="text-emerald-400">✓</span> Saved</>
          ) : (
            <><Database className="w-3 h-3" /> Train LLM on this snapshot</>
          )}
        </button>
        {total != null && total >= 50 && (
          <a
            href={`${API}/api/v1/training/export`}
            download="kill_chain_snapshots.jsonl"
            className="px-3 py-1.5 bg-zinc-900 border border-emerald-500/30 rounded-lg text-[10px] font-black text-emerald-400 hover:bg-emerald-500/10 transition-all"
          >
            Export JSONL
          </a>
        )}
      </div>
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

// ── Main export ───────────────────────────────────────────────────────────────
export function SignalChainView() {
  const [data, setData] = useState<KillShotsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastSync, setLastSync] = useState('');
  const [openTip, setOpenTip] = useState<string | null>(null);

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
        <ReconciledVerdictBar d={data} openTip={openTip} setOpenTip={setOpenTip} />
        <ChainConnector label="history" />
        <HistoryStrip />
        <ChainConnector label="raw inputs" />
        <RawInputsStrip d={data} openTip={openTip} setOpenTip={setOpenTip} />
        <ChainConnector label="feeds into" />
        <ScorerPillars d={data} openTip={openTip} setOpenTip={setOpenTip} />
        <ChainConnector label="gated by" />
        {data.kill_chain
          ? <KillChainGate kc={data.kill_chain} />
          : <div className="bg-zinc-950 border border-white/5 rounded-xl p-6 text-center text-[10px] font-mono text-zinc-600">kill_chain not in response — check /kill-shots-live</div>
        }
        <ChainConnector label="synthesized by" />
        <ReconciliationEngine d={data} />
        <TrainButton d={data} />

        <div className="pt-6 pb-2 text-center text-[8px] font-mono text-zinc-800 uppercase tracking-widest">
          {data.timestamp ? new Date(data.timestamp).toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hour12: true }) + ' ET' : '—'} · click ⓘ on any value to audit source · click layer rows to expand
        </div>
      </div>
    </div>
  );
}
