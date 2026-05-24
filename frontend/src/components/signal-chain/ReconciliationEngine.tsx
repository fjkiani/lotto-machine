import React from 'react';
import { GitMerge, AlertTriangle, CheckCircle } from 'lucide-react';

interface Props {
  divergenceVerdict: string;
  divergenceScore: number;
  killChainVerdict: string;
  killChainConfluence: string;
  reconciledVerdict: string;
  reconciliationReasons: string[];
}

const VERDICT_STYLES: Record<string, { color: string; bg: string; border: string; label: string }> = {
  BOOST:     { color: '#10b981', bg: 'rgba(16,185,129,0.08)',  border: 'rgba(16,185,129,0.3)',  label: 'BOOST — Deploy capital' },
  BUY:       { color: '#3b82f6', bg: 'rgba(59,130,246,0.08)',  border: 'rgba(59,130,246,0.3)',  label: 'BUY — Partial position' },
  HOLD:      { color: '#a1a1aa', bg: 'rgba(161,161,170,0.08)', border: 'rgba(161,161,170,0.3)', label: 'HOLD — Wait for alignment' },
  WATCH:     { color: '#eab308', bg: 'rgba(234,179,8,0.08)',   border: 'rgba(234,179,8,0.3)',   label: 'WATCH — Suppressed' },
  NEUTRAL:   { color: '#22d3ee', bg: 'rgba(34,211,238,0.05)',  border: 'rgba(34,211,238,0.2)',  label: 'NEUTRAL — No edge' },
  SOFT_VETO: { color: '#f97316', bg: 'rgba(249,115,22,0.08)',  border: 'rgba(249,115,22,0.3)',  label: 'SOFT VETO — Reduce size' },
  HARD_VETO: { color: '#f43f5e', bg: 'rgba(244,63,94,0.08)',   border: 'rgba(244,63,94,0.3)',   label: 'HARD VETO — No trade' },
  WAR_VETO:  { color: '#f43f5e', bg: 'rgba(244,63,94,0.08)',   border: 'rgba(244,63,94,0.3)',   label: 'WAR VETO — LONG suppressed' },
};

const RULE_LABELS: Record<string, string> = {
  'WAR_VETO': 'Rule 1: WAR_VETO always wins',
  'RSI': 'Rule 2: RSI overbought (>70) downgrades BOOST → HOLD',
  'DOUBLE': 'Rule 3: Kill chain DOUBLE (need TRIPLE for full BOOST)',
  'VETO': 'Rule 3: Kill chain VETO confluence',
  'WAITING': 'Rule 4: Kill chain WAITING contradicts BOOST',
  'SINGLE': 'Rule 4: Kill chain SINGLE contradicts BOOST',
};

function detectRule(reasons: string[]): string {
  if (!reasons.length) return 'No override — verdicts aligned';
  const r = reasons[0];
  if (r.includes('WAR_VETO')) return RULE_LABELS['WAR_VETO'];
  if (r.includes('RSI') || r.includes('overbought')) return RULE_LABELS['RSI'];
  if (r.includes('DOUBLE')) return RULE_LABELS['DOUBLE'];
  if (r.includes('VETO confluence')) return RULE_LABELS['VETO'];
  if (r.includes('WAITING')) return RULE_LABELS['WAITING'];
  if (r.includes('SINGLE')) return RULE_LABELS['SINGLE'];
  return 'Reconciliation applied';
}

function isManualOilWarning(reason: string): boolean {
  return reason.toLowerCase().includes('manual') || reason.toLowerCase().includes('env var');
}

export function ReconciliationEngine({
  divergenceVerdict,
  divergenceScore,
  killChainVerdict,
  killChainConfluence,
  reconciledVerdict,
  reconciliationReasons,
}: Props) {
  const divStyle = VERDICT_STYLES[divergenceVerdict] ?? VERDICT_STYLES.NEUTRAL;
  const kcStyle = VERDICT_STYLES[killChainVerdict] ?? VERDICT_STYLES.NEUTRAL;
  const recStyle = VERDICT_STYLES[reconciledVerdict] ?? VERDICT_STYLES.NEUTRAL;

  const wasOverridden = reconciledVerdict !== divergenceVerdict;
  const ruleLabel = detectRule(reconciliationReasons);
  const hasManualWarning = reconciliationReasons.some(isManualOilWarning);

  return (
    <div className="bg-[#09090b] border border-white/10 rounded-xl overflow-hidden shadow-[0_0_50px_rgba(0,0,0,0.5)]">
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/5 flex items-center gap-3">
        <GitMerge className="w-5 h-5 text-purple-400" />
        <div>
          <span className="text-[9px] font-black text-zinc-500 uppercase tracking-[0.3em] block">Synthesis</span>
          <span className="text-lg font-black text-white tracking-tight">Reconciliation Engine</span>
        </div>
        {wasOverridden ? (
          <div className="ml-auto flex items-center gap-2 px-3 py-1 bg-amber-500/10 border border-amber-500/20 rounded-lg">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
            <span className="text-[10px] font-black text-amber-400 uppercase tracking-widest">Override Applied</span>
          </div>
        ) : (
          <div className="ml-auto flex items-center gap-2 px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
            <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-[10px] font-black text-emerald-400 uppercase tracking-widest">Verdicts Aligned</span>
          </div>
        )}
      </div>

      <div className="p-6 space-y-6">
        {/* Two-verdict comparison */}
        <div className="grid grid-cols-2 gap-4">
          {/* Divergence verdict */}
          <div
            className="rounded-xl border p-5"
            style={{ backgroundColor: divStyle.bg, borderColor: divStyle.border }}
          >
            <span className="text-[9px] font-black text-zinc-500 uppercase tracking-[0.3em] block mb-2">
              Divergence Score
            </span>
            <div className="flex items-baseline gap-3 mb-1">
              <span className="text-3xl font-black tracking-tighter" style={{ color: divStyle.color }}>
                {divergenceVerdict}
              </span>
              <span className="text-sm font-mono font-black text-zinc-500">score={divergenceScore}</span>
            </div>
            <p className="text-[10px] text-zinc-500">{divStyle.label}</p>
            <p className="text-[9px] text-zinc-700 mt-2 font-mono">
              Source: 5-scorer sum (COT+GEX+BRAIN+FED_DP+COMBINED)
            </p>
          </div>

          {/* Kill chain verdict */}
          <div
            className="rounded-xl border p-5"
            style={{ backgroundColor: kcStyle.bg, borderColor: kcStyle.border }}
          >
            <span className="text-[9px] font-black text-zinc-500 uppercase tracking-[0.3em] block mb-2">
              Kill Chain Gate
            </span>
            <div className="flex items-baseline gap-3 mb-1">
              <span className="text-3xl font-black tracking-tighter" style={{ color: kcStyle.color }}>
                {killChainVerdict}
              </span>
              <span className="text-sm font-mono font-black text-zinc-500">{killChainConfluence}</span>
            </div>
            <p className="text-[10px] text-zinc-500">{kcStyle.label}</p>
            <p className="text-[9px] text-zinc-700 mt-2 font-mono">
              Source: 5-layer confluence gate + macro overlay
            </p>
          </div>
        </div>

        {/* Rule applied */}
        {wasOverridden && (
          <div className="bg-zinc-950 border border-white/5 rounded-xl p-4">
            <span className="text-[9px] font-black text-purple-400 uppercase tracking-[0.3em] block mb-2">
              Rule Applied
            </span>
            <p className="text-[12px] font-black text-zinc-200">{ruleLabel}</p>
          </div>
        )}

        {/* Reconciliation reasons */}
        {reconciliationReasons.length > 0 && (
          <div className="space-y-2">
            <span className="text-[9px] font-black text-zinc-600 uppercase tracking-[0.3em] block">
              Reasoning Chain
            </span>
            {reconciliationReasons.map((reason, i) => {
              const isWarning = isManualOilWarning(reason);
              return (
                <div
                  key={i}
                  className={`flex items-start gap-3 p-3 rounded-lg border text-[11px] leading-relaxed ${
                    isWarning
                      ? 'bg-amber-500/10 border-amber-500/20 text-amber-300'
                      : 'bg-zinc-950 border-white/5 text-zinc-400'
                  }`}
                >
                  <span className={`flex-shrink-0 font-black mt-0.5 ${isWarning ? 'text-amber-400' : 'text-zinc-600'}`}>
                    {isWarning ? '⚠' : '·'}
                  </span>
                  <span>{reason}</span>
                </div>
              );
            })}
          </div>
        )}

        {/* Manual oil warning banner */}
        {hasManualWarning && (
          <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-[11px] font-black text-amber-300 mb-1">Manual Override Active</p>
              <p className="text-[11px] text-amber-400/80 leading-relaxed">
                The WAR_VETO is driven by <code className="font-mono bg-amber-500/20 px-1 rounded">MANUAL_OIL_PRICE</code> env var, not a live WTI feed.
                Remove this env var on Render to let the system fetch live CL=F prices.
                At live WTI ~$70-80, war_status would be 1-3 (no veto threshold of 7).
              </p>
            </div>
          </div>
        )}

        {/* Final reconciled verdict */}
        <div
          className="rounded-xl border-2 p-6 text-center"
          style={{ backgroundColor: recStyle.bg, borderColor: recStyle.border }}
        >
          <span className="text-[9px] font-black text-zinc-500 uppercase tracking-[0.3em] block mb-3">
            Reconciled Verdict
          </span>
          <span className="text-5xl font-black tracking-tighter" style={{ color: recStyle.color }}>
            {reconciledVerdict}
          </span>
          <p className="text-[11px] mt-3" style={{ color: recStyle.color }}>
            {recStyle.label}
          </p>
        </div>
      </div>
    </div>
  );
}
