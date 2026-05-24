import React, { useState } from 'react';
import { Crosshair, ChevronDown, ChevronUp, Info } from 'lucide-react';
import type { KillChainResult, KillChainLayer, KillChainLayerMacro } from '../widgets/kill-shots/types';

interface Props {
  killChain: KillChainResult;
}

// Layer definitions — what each layer IS and what triggers it
const LAYER_META: Record<string, { what: string; triggerCondition: string; source: string }> = {
  'COT Divergence': {
    what: 'CFTC Commitments of Traders — speculative (non-commercial) net futures positioning on ES (S&P 500 futures).',
    triggerCondition: 'Specs net short > 50,000 contracts',
    source: 'CFTC weekly COT report via Barchart',
  },
  'GEX Regime': {
    what: 'Dealer gamma exposure on SPX options. Negative GEX = dealers short gamma = moves amplified. Positive GEX = dealers long gamma = moves dampened.',
    triggerCondition: 'GEX regime contains NEGATIVE',
    source: 'CBOE options chain (delayed)',
  },
  'DVR': {
    what: 'Dark Volume Ratio — short volume as % of total volume from Stockgrid. >55% = distribution (institutional selling). <45% = accumulation.',
    triggerCondition: 'Short volume % > 55% (distribution threshold)',
    source: 'Stockgrid daily dark pool feed',
  },
  'AXLFI Wall Position': {
    what: 'SPY spot price position relative to the call wall (largest call OI strike). Above the call wall = dealer delta hedging creates self-reinforcing upside.',
    triggerCondition: 'SPY spot > call wall strike',
    source: 'Stockgrid AXLFI option walls',
  },
  'QQQ Reshort Spike': {
    what: 'QQQ short volume % day-over-day delta. A spike of >10pp while SPY is above the call wall = institutions re-shorting into strength = forced cover fuel.',
    triggerCondition: 'QQQ SV delta > +10pp AND SPY above call wall',
    source: 'Stockgrid QQQ short volume feed',
  },
};

const CONFLUENCE_COLOR: Record<string, string> = {
  QUINT: '#10b981',
  QUAD: '#10b981',
  TRIPLE: '#10b981',
  DOUBLE: '#f97316',
  SINGLE: '#eab308',
  WAITING: '#71717a',
  VETO: '#f43f5e',
};

const VERDICT_COLOR: Record<string, string> = {
  BOOST: '#10b981',
  NEUTRAL: '#22d3ee',
  SOFT_VETO: '#f97316',
  HARD_VETO: '#f43f5e',
  WAR_VETO: '#f43f5e',
  WATCH: '#eab308',
};

function LayerRow({ layer, meta }: { layer: KillChainLayer; meta: { what: string; triggerCondition: string; source: string } }) {
  const [open, setOpen] = useState(false);

  const valueStr = layer.value != null
    ? typeof layer.value === 'number'
      ? layer.value > 1000 ? layer.value.toLocaleString() : layer.value.toFixed(2)
      : String(layer.value)
    : '—';

  const extraStr = layer.pts_above_call_wall != null
    ? ` · +${layer.pts_above_call_wall.toFixed(2)}pts above wall`
    : layer.report_date
    ? ` · report: ${layer.report_date}`
    : layer.label
    ? ` · ${layer.label}`
    : '';

  return (
    <div className={`border rounded-lg overflow-hidden ${layer.triggered ? 'border-orange-500/30 bg-orange-500/5' : 'border-white/5 bg-zinc-950/50'}`}>
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-white/5 transition-colors"
        onClick={() => setOpen(v => !v)}
      >
        {/* Triggered indicator */}
        <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 text-[10px] font-black ${layer.triggered ? 'bg-orange-500/20 text-orange-400' : 'bg-zinc-900 text-zinc-600'}`}>
          {layer.triggered ? '✓' : '✗'}
        </div>

        {/* Layer name */}
        <span className={`text-[11px] font-black uppercase tracking-wide flex-1 ${layer.triggered ? 'text-zinc-200' : 'text-zinc-500'}`}>
          {layer.name}
        </span>

        {/* Signal badge */}
        {layer.signal && (
          <span className={`text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded border ${
            layer.triggered
              ? 'bg-orange-500/10 border-orange-500/30 text-orange-400'
              : 'bg-zinc-900 border-zinc-800 text-zinc-600'
          }`}>
            {layer.signal}
          </span>
        )}

        {/* Value */}
        <span className={`text-[11px] font-mono font-black ${layer.triggered ? 'text-zinc-300' : 'text-zinc-600'}`}>
          {valueStr}{extraStr}
        </span>

        {/* Expand */}
        <button className="text-zinc-700 hover:text-zinc-400 transition-colors ml-1">
          {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>
      </div>

      {open && (
        <div className="px-4 pb-4 pt-1 border-t border-white/5 space-y-2">
          <div>
            <span className="text-[8px] font-black text-cyan-500 uppercase tracking-[0.3em] block mb-0.5">WHAT IS THIS</span>
            <p className="text-[11px] text-zinc-400 leading-relaxed">{meta.what}</p>
          </div>
          <div>
            <span className="text-[8px] font-black text-orange-400 uppercase tracking-[0.3em] block mb-0.5">TRIGGER CONDITION</span>
            <p className="text-[11px] text-zinc-400 leading-relaxed font-mono">{meta.triggerCondition}</p>
          </div>
          <div className="flex items-center gap-1.5 pt-1 border-t border-white/5">
            <Info className="w-2.5 h-2.5 text-zinc-600" />
            <span className="text-[9px] font-mono text-zinc-600 uppercase tracking-widest">SRC: {meta.source}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function MacroRow({ macro }: { macro: KillChainLayerMacro }) {
  const [open, setOpen] = useState(false);
  const isVeto = macro.veto_longs;
  const isManual = macro.oil_wti_source === 'manual';

  return (
    <div className={`border rounded-lg overflow-hidden ${isVeto ? 'border-rose-500/40 bg-rose-500/5' : 'border-white/5 bg-zinc-950/50'}`}>
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-white/5 transition-colors"
        onClick={() => setOpen(v => !v)}
      >
        <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 text-[10px] font-black ${isVeto ? 'bg-rose-500/20 text-rose-400' : 'bg-zinc-900 text-zinc-600'}`}>
          {isVeto ? '⚔' : '—'}
        </div>
        <span className={`text-[11px] font-black uppercase tracking-wide flex-1 ${isVeto ? 'text-rose-300' : 'text-zinc-500'}`}>
          {macro.name}
        </span>
        {isManual && (
          <span className="text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded border bg-amber-500/10 border-amber-500/30 text-amber-400">
            ⚠ MANUAL
          </span>
        )}
        <span className={`text-[9px] font-black uppercase tracking-widest px-2 py-0.5 rounded border ${isVeto ? 'bg-rose-500/10 border-rose-500/30 text-rose-400' : 'bg-zinc-900 border-zinc-800 text-zinc-600'}`}>
          {macro.signal}
        </span>
        <span className={`text-[11px] font-mono font-black ${isVeto ? 'text-rose-300' : 'text-zinc-600'}`}>
          {macro.value}/10
        </span>
        <button className="text-zinc-700 hover:text-zinc-400 transition-colors ml-1">
          {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>
      </div>

      {open && (
        <div className="px-4 pb-4 pt-1 border-t border-white/5 space-y-2">
          <div>
            <span className="text-[8px] font-black text-cyan-500 uppercase tracking-[0.3em] block mb-0.5">WAR STATUS BREAKDOWN</span>
            <p className="text-[11px] text-zinc-400 leading-relaxed font-mono">
              {macro.war_status_breakdown ?? `base=1${macro.oil_wti > 90 ? `, oil>${90}(+2)` : ''}${macro.oil_wti > 100 ? `(+1)` : ''}${macro.signal === 'WAR_PREMIUM' ? '' : ''}`}
            </p>
          </div>
          <div>
            <span className="text-[8px] font-black text-orange-400 uppercase tracking-[0.3em] block mb-0.5">OIL WTI</span>
            <p className="text-[11px] text-zinc-400 font-mono">
              ${macro.oil_wti?.toFixed(2) ?? '—'} · source: <span className={isManual ? 'text-amber-400 font-black' : 'text-zinc-400'}>{macro.oil_wti_source}</span>
            </p>
          </div>
          {macro.veto_reason && (
            <div>
              <span className="text-[8px] font-black text-rose-400 uppercase tracking-[0.3em] block mb-0.5">VETO REASON</span>
              <p className="text-[11px] text-rose-300 leading-relaxed">{macro.veto_reason}</p>
            </div>
          )}
          {isManual && macro.manual_override_warning && (
            <div className="bg-amber-500/10 border border-amber-500/20 rounded p-2">
              <p className="text-[11px] text-amber-300 leading-relaxed">⚠ {macro.manual_override_warning}</p>
            </div>
          )}
          <div className="flex items-center gap-1.5 pt-1 border-t border-white/5">
            <Info className="w-2.5 h-2.5 text-zinc-600" />
            <span className="text-[9px] font-mono text-zinc-600 uppercase tracking-widest">SRC: macro_overlay.py / env vars + yfinance CL=F</span>
          </div>
        </div>
      )}
    </div>
  );
}

export function KillChainGate({ killChain }: Props) {
  const layers = [
    { layer: killChain.layer_1, meta: LAYER_META['COT Divergence'] },
    { layer: killChain.layer_2, meta: LAYER_META['GEX Regime'] },
    { layer: killChain.layer_3, meta: LAYER_META['DVR'] },
    { layer: killChain.layer_4, meta: LAYER_META['AXLFI Wall Position'] },
    { layer: killChain.layer_5, meta: LAYER_META['QQQ Reshort Spike'] },
  ];

  const confluenceColor = CONFLUENCE_COLOR[killChain.confluence] ?? '#71717a';
  const verdictColor = VERDICT_COLOR[killChain.verdict] ?? '#71717a';

  return (
    <div className="bg-[#09090b] border border-white/10 rounded-xl overflow-hidden shadow-[0_0_50px_rgba(0,0,0,0.5)]">
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Crosshair className="w-5 h-5 text-emerald-400" />
          <div>
            <span className="text-[9px] font-black text-zinc-500 uppercase tracking-[0.3em] block">Kill Chain Gate</span>
            <span className="text-lg font-black text-white tracking-tight">5-Layer Confluence</span>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {/* Confluence badge */}
          <div className="text-right">
            <span className="text-[8px] font-black text-zinc-600 uppercase tracking-widest block">Confluence</span>
            <span className="text-sm font-black" style={{ color: confluenceColor }}>{killChain.confluence}</span>
          </div>
          <div className="h-8 w-px bg-zinc-800" />
          {/* Score */}
          <div className="text-right">
            <span className="text-[8px] font-black text-zinc-600 uppercase tracking-widest block">Score</span>
            <span className="text-sm font-black text-white">{killChain.score}/10</span>
          </div>
          <div className="h-8 w-px bg-zinc-800" />
          {/* Verdict */}
          <div className="text-right">
            <span className="text-[8px] font-black text-zinc-600 uppercase tracking-widest block">Verdict</span>
            <span className="text-sm font-black" style={{ color: verdictColor }}>{killChain.verdict}</span>
          </div>
          <div className="h-8 w-px bg-zinc-800" />
          {/* Direction */}
          <div className="text-right">
            <span className="text-[8px] font-black text-zinc-600 uppercase tracking-widest block">Direction</span>
            <span className={`text-sm font-black ${killChain.direction === 'BULLISH' ? 'text-emerald-400' : killChain.direction === 'BEARISH' ? 'text-rose-400' : 'text-zinc-400'}`}>
              {killChain.direction}
            </span>
          </div>
        </div>
      </div>

      {/* Layer rows */}
      <div className="p-4 space-y-2">
        {layers.map(({ layer, meta }) => (
          <LayerRow key={layer.name} layer={layer} meta={meta} />
        ))}

        {/* Macro overlay — separate section */}
        {killChain.layer_macro && (
          <>
            <div className="flex items-center gap-3 py-2">
              <div className="flex-1 h-px bg-zinc-800" />
              <span className="text-[9px] font-black text-zinc-600 uppercase tracking-widest">Macro Override</span>
              <div className="flex-1 h-px bg-zinc-800" />
            </div>
            <MacroRow macro={killChain.layer_macro} />
          </>
        )}
      </div>

      {/* Points breakdown */}
      <div className="px-4 pb-4">
        <div className="bg-zinc-950 rounded-lg border border-white/5 p-3 flex items-center justify-between text-[10px] font-mono">
          <span className="text-zinc-600">Bullish pts: <span className="text-emerald-400 font-black">{killChain.bullish_points}</span></span>
          <span className="text-zinc-600">Bearish pts: <span className="text-rose-400 font-black">{killChain.bearish_points}</span></span>
          <span className="text-zinc-600">Layers active: <span className="text-white font-black">{killChain.triggered_count}/5</span></span>
          <span className="text-zinc-600">Armed: <span className={`font-black ${killChain.armed ? 'text-orange-400' : 'text-zinc-500'}`}>{killChain.armed ? 'YES' : 'NO'}</span></span>
        </div>
      </div>
    </div>
  );
}
