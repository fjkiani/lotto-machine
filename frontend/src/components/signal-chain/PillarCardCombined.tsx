import React from 'react';
import type { KillShotsLayers } from '../widgets/kill-shots/types';
import { PillarShell, PillarFooter, IntelligenceBriefing, DataPoint, KV } from '../widgets/kill-shots/ui';

interface Props { data: KillShotsLayers }

// The 5 confluence rules from combined_scorer.py — shown explicitly so the user
// can see which rules fired and which didn't.
interface Rule {
  id: number;
  label: string;
  condition: string;
  fired: boolean;
  pts: number;
  reason?: string;
}

export const PillarCardCombined: React.FC<Props> = ({ data }) => {
  const boost = data.combined_boost ?? 0;
  const isArmed = boost >= 2;

  const cotExtreme = (data.cot_boost ?? 0) >= 3;
  const cotMild = (data.cot_boost ?? 0) >= 1;
  const gexPositive = (data.gex_regime ?? '').includes('POSITIVE');
  const gexNegative = (data.gex_regime ?? '').includes('NEGATIVE');
  const aboveCallWall = data.axlfi_signal === 'ABOVE_CALL_WALL';
  const qqq = data.qqq_reshort_spike === true;
  const polCluster = (data.politician_cluster ?? 0) >= 3 && (data.politician_buys ?? 0) > 0;

  const rules: Rule[] = [
    {
      id: 1,
      label: 'COT extreme + GEX positive',
      condition: 'Support floor + reversal setup',
      fired: cotExtreme && gexPositive,
      pts: 2,
      reason: cotExtreme && gexPositive
        ? `GEX dampening (${data.gex_regime}) + COT Extreme → dealers suppressing vol while specs trapped short = slow grind squeeze`
        : undefined,
    },
    {
      id: 2,
      label: 'COT extreme + GEX negative',
      condition: 'Maximum squeeze velocity',
      fired: cotExtreme && gexNegative,
      pts: 3,
      reason: cotExtreme && gexNegative
        ? `GEX NEGATIVE (${data.gex_regime}) + COT Extreme → vol amplifier + crowded shorts = maximum squeeze velocity`
        : undefined,
    },
    {
      id: 3,
      label: 'COT mild + above call wall',
      condition: 'Breakout confirmation',
      fired: cotMild && aboveCallWall && !cotExtreme,
      pts: 1,
      reason: cotMild && aboveCallWall
        ? `COT shorts + SPY above call wall${data.pts_above_call_wall ? ` +${data.pts_above_call_wall.toFixed(1)}pts` : ''} → breakout confirmed, dealer hedging self-reinforcing`
        : undefined,
    },
    {
      id: 4,
      label: 'QQQ reshort spike above call wall',
      condition: 'Squeeze fuel',
      fired: qqq && aboveCallWall,
      pts: 1,
      reason: qqq && aboveCallWall
        ? `QQQ reshort spike above call wall → institutions re-shorting into strength = forced cover fuel`
        : undefined,
    },
    {
      id: 5,
      label: 'Politician cluster buy (≥3)',
      condition: 'Directional insider signal',
      fired: polCluster,
      pts: 1,
      reason: polCluster
        ? `Politician cluster (${data.politician_cluster} buys) → non-routine insider signal, 3-6 week horizon`
        : undefined,
    },
  ];

  const anchor = [
    `combined_boost=+${boost}`,
    `cot_extreme=${cotExtreme}`,
    `gex_regime=${data.gex_regime ?? 'unknown'}`,
    aboveCallWall ? `above_call_wall=+${data.pts_above_call_wall?.toFixed(1) ?? '?'}pts` : null,
    qqq ? 'qqq_reshort=true' : null,
  ].filter(Boolean).join(', ');

  return (
    <PillarShell
      isArmed={isArmed}
      label="Confluence Engine"
      title="COMBINED"
      value={`+${boost}`}
      status={isArmed ? 'ARMED' : 'WATCHING'}
    >
      {/* Status header */}
      <div className="flex items-center gap-3 bg-zinc-950 p-3 rounded-lg border border-white/5 mb-5">
        <div className="flex-1">
          <span className="text-[8px] font-bold text-zinc-600 uppercase tracking-widest block mb-1">Rules Fired</span>
          <span className="text-xs font-black uppercase" style={{ color: isArmed ? '#f97316' : '#71717a' }}>
            {rules.filter(r => r.fired).length} / {rules.length}
          </span>
        </div>
        <div className="h-8 w-px bg-zinc-800" />
        <div className="flex-1 text-right">
          <span className="text-[8px] font-bold text-zinc-600 uppercase tracking-widest block mb-1">Boost</span>
          <span className="text-xs font-black text-white">+{boost}</span>
        </div>
      </div>

      {/* Rule-by-rule breakdown */}
      <div className="space-y-1.5 mb-5">
        <span className="text-[9px] font-black text-zinc-600 uppercase tracking-widest block mb-2">Confluence Rules</span>
        {rules.map(rule => (
          <div
            key={rule.id}
            className={`flex items-start gap-2 p-2 rounded border text-[10px] ${
              rule.fired
                ? 'bg-orange-500/5 border-orange-500/20'
                : 'bg-zinc-950 border-white/5'
            }`}
          >
            <span className={`font-black mt-0.5 flex-shrink-0 ${rule.fired ? 'text-orange-400' : 'text-zinc-700'}`}>
              {rule.fired ? '✓' : '✗'}
            </span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <span className={`font-black uppercase tracking-tight ${rule.fired ? 'text-zinc-200' : 'text-zinc-600'}`}>
                  Rule {rule.id}: {rule.label}
                </span>
                <span className={`font-mono font-black flex-shrink-0 ${rule.fired ? 'text-orange-400' : 'text-zinc-700'}`}>
                  +{rule.pts}
                </span>
              </div>
              <span className={`text-[9px] ${rule.fired ? 'text-zinc-400' : 'text-zinc-700'}`}>
                {rule.fired && rule.reason ? rule.reason : rule.condition}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Key inputs */}
      <div className="space-y-0 mb-5 border-t border-white/5 pt-4">
        <DataPoint
          label="COT Extreme"
          value={cotExtreme ? 'YES' : 'NO'}
          color={cotExtreme ? '#f43f5e' : '#71717a'}
          tooltip={{
            what: 'Whether COT specs are at extreme short positioning (>100K net short contracts). This is the primary trigger for Rules 1 and 2.',
            why: cotExtreme
              ? `Specs at ${data.cot_specs_net?.toLocaleString() ?? '?'} — extreme crowded short. Maximum squeeze fuel available.`
              : `Specs at ${data.cot_specs_net?.toLocaleString() ?? '?'} — not at extreme threshold. Rules 1 and 2 cannot fire.`,
            source: 'CFTC COT report via CotScorer',
          }}
        />
        <DataPoint
          label="GEX Regime"
          value={data.gex_regime ?? '—'}
          color={gexNegative ? '#f43f5e' : gexPositive ? '#10b981' : '#71717a'}
          tooltip={{
            what: 'Dealer gamma exposure regime. POSITIVE = dealers long gamma (stabilizing). NEGATIVE = dealers short gamma (amplifying). Determines which COT+GEX rule fires.',
            why: gexPositive
              ? 'POSITIVE GEX: dealers suppress volatility. Combined with extreme COT shorts, this creates a slow grind squeeze (Rule 1, +2pts).'
              : gexNegative
              ? 'NEGATIVE GEX: dealers amplify moves. Combined with extreme COT shorts, this is maximum squeeze velocity (Rule 2, +3pts).'
              : 'Neutral GEX — neither Rule 1 nor Rule 2 can fire.',
            source: 'CBOE options chain via GexScorer',
          }}
        />
        <DataPoint
          label="Above Call Wall"
          value={aboveCallWall ? `YES +${data.pts_above_call_wall?.toFixed(1) ?? '?'}pts` : 'NO'}
          color={aboveCallWall ? '#f97316' : '#71717a'}
          tooltip={{
            what: 'Whether SPY spot price is above the call wall (largest call OI strike). Above the call wall, dealer delta hedging creates self-reinforcing upside momentum.',
            why: aboveCallWall
              ? `SPY is ${data.pts_above_call_wall?.toFixed(1) ?? '?'}pts above the call wall. Dealer hedging is now amplifying upside. Rule 3 (COT mild + above wall) can fire.`
              : 'SPY is not above the call wall. Rule 3 cannot fire.',
            source: 'Stockgrid AXLFI via enrichment block',
          }}
        />
        {data.qqq_sv_delta != null && (
          <KV
            label="QQQ SV Delta"
            value={`${data.qqq_sv_delta > 0 ? '+' : ''}${data.qqq_sv_delta.toFixed(1)}pp`}
            color={data.qqq_reshort_spike ? '#f43f5e' : '#71717a'}
          />
        )}
      </div>

      <IntelligenceBriefing content={data.explanation_COMBINED} anchor={anchor} />
      <PillarFooter src="combined-scorer/rules" slug={data.combined_slug} />
    </PillarShell>
  );
};
