import React from 'react';
import { Database } from 'lucide-react';
import type { KillChainResult, KillShotsLayers } from '../widgets/kill-shots/types';

interface Props {
  killChain?: KillChainResult;
  layers: KillShotsLayers;
  spot?: number;
  callWall?: number;
  putWall?: number;
  gammaFlip?: number;
  totalGex?: number;
  gexRegime?: string;
}

interface RawCell {
  label: string;
  value: string;
  sub?: string;
  color: string;
  alert?: boolean;
}

function cell(label: string, value: string, color: string, sub?: string, alert?: boolean): RawCell {
  return { label, value, color, sub, alert };
}

export function RawInputsBar({ killChain, layers, spot, callWall, putWall, gammaFlip, totalGex, gexRegime }: Props) {
  const cells: RawCell[] = [];

  // SPY spot + wall position
  const ptsAbove = killChain?.layer_4?.pts_above_call_wall ?? layers.pts_above_call_wall;
  const axlfiSignal = killChain?.layer_4?.signal ?? layers.axlfi_signal;
  const effectiveSpot = spot ?? layers.axlfi_spot ?? layers.gex_spot_price;
  const effectiveCallWall = callWall ?? layers.axlfi_call_wall;

  if (effectiveSpot) {
    cells.push(cell('SPY Spot', `$${effectiveSpot.toFixed(2)}`, '#ffffff'));
  }

  if (ptsAbove != null && effectiveCallWall) {
    const above = ptsAbove > 0;
    cells.push(cell(
      above ? 'Above Call Wall' : 'Below Call Wall',
      `${above ? '+' : ''}${ptsAbove.toFixed(2)}pts`,
      above ? '#f97316' : '#f43f5e',
      `Wall: $${effectiveCallWall}`,
      above,
    ));
  }

  if (gammaFlip) {
    cells.push(cell('Gamma Flip', `$${gammaFlip}`, '#22d3ee', 'dealer zero'));
  }

  if (putWall) {
    cells.push(cell('Put Wall', `$${putWall}`, '#a78bfa'));
  }

  // GEX
  const effectiveGex = totalGex ?? layers.total_gex_dollars;
  const effectiveRegime = gexRegime ?? layers.gex_regime;
  if (effectiveGex != null) {
    const gexM = (effectiveGex / 1e6).toFixed(1);
    const isNeg = effectiveGex < 0;
    cells.push(cell(
      'GEX',
      `${isNeg ? '' : '+'}$${gexM}M`,
      isNeg ? '#f43f5e' : '#10b981',
      effectiveRegime ?? undefined,
    ));
  }

  // COT
  const cotNet = killChain?.layer_1?.value ?? layers.cot_specs_net;
  const cotDivergent = layers.cot_divergent;
  if (cotNet != null) {
    const isShort = cotNet < 0;
    cells.push(cell(
      'COT Specs',
      `${cotNet > 0 ? '+' : ''}${cotNet.toLocaleString()}`,
      isShort ? '#f43f5e' : '#10b981',
      isShort ? 'NET SHORT' : 'NET LONG',
      cotDivergent,
    ));
  }

  // DVR
  const dvrPct = killChain?.layer_3?.value ?? layers.spy_short_vol_pct;
  const dvrSignal = killChain?.layer_3?.signal;
  if (dvrPct != null) {
    const isHigh = dvrPct > 55;
    cells.push(cell(
      'DVR',
      `${dvrPct.toFixed(1)}%`,
      isHigh ? '#f43f5e' : dvrPct < 45 ? '#10b981' : '#71717a',
      dvrSignal ?? undefined,
    ));
  }

  // QQQ SV delta
  const qqqDelta = killChain?.layer_5?.value ?? layers.qqq_sv_delta;
  const qqqSignal = killChain?.layer_5?.signal;
  if (qqqDelta != null) {
    cells.push(cell(
      'QQQ SV Δ',
      `${qqqDelta > 0 ? '+' : ''}${qqqDelta.toFixed(1)}pp`,
      layers.qqq_reshort_spike ? '#f43f5e' : '#71717a',
      qqqSignal ?? undefined,
      layers.qqq_reshort_spike,
    ));
  }

  // VIX
  if (layers.vix != null) {
    const vix = layers.vix;
    cells.push(cell(
      'VIX',
      vix.toFixed(2),
      vix > 30 ? '#f43f5e' : vix > 20 ? '#f97316' : vix < 13 ? '#eab308' : '#71717a',
      vix > 30 ? 'EXTREME' : vix > 20 ? 'ELEVATED' : vix < 13 ? 'COMPLACENT' : 'NORMAL',
    ));
  }

  // RSI
  if (layers.rsi_14 != null) {
    const rsi = layers.rsi_14;
    cells.push(cell(
      'RSI-14',
      rsi.toFixed(1),
      rsi > 70 ? '#f43f5e' : rsi < 30 ? '#10b981' : '#71717a',
      rsi > 70 ? 'OVERBOUGHT' : rsi < 30 ? 'OVERSOLD' : 'NEUTRAL',
      rsi > 70,
    ));
  }

  if (cells.length === 0) return null;

  return (
    <div className="bg-[#09090b] border border-white/10 rounded-xl overflow-hidden shadow-[0_0_50px_rgba(0,0,0,0.5)]">
      {/* Header */}
      <div className="px-6 py-3 border-b border-white/5 flex items-center gap-3">
        <Database className="w-4 h-4 text-zinc-500" />
        <span className="text-[9px] font-black text-zinc-500 uppercase tracking-[0.3em]">Raw Inputs</span>
        <span className="text-[9px] text-zinc-700 font-mono ml-auto">
          {killChain?.computed_at_utc
            ? new Date(killChain.computed_at_utc).toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hour12: true }) + ' ET'
            : 'live'}
        </span>
      </div>

      {/* Cell grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-9 gap-px bg-white/5">
        {cells.map((c, i) => (
          <div
            key={i}
            className={`bg-[#09090b] px-4 py-3 flex flex-col gap-0.5 ${c.alert ? 'bg-orange-500/5' : ''}`}
          >
            <span className="text-[8px] font-black text-zinc-600 uppercase tracking-widest">{c.label}</span>
            <span className="text-sm font-black font-mono" style={{ color: c.color }}>{c.value}</span>
            {c.sub && (
              <span className="text-[9px] font-bold text-zinc-600 uppercase tracking-tight">{c.sub}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
