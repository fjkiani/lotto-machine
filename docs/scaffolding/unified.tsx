import React, { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Activity, 
  BrainCircuit, 
  Zap, 
  Search, 
  ShieldCheck, 
  Cpu,
  RefreshCw, 
  BarChart2, 
  ArrowRight, 
  AlertOctagon, 
  ChevronDown, 
  ChevronRight, 
  Terminal, 
  Info, 
  TrendingUp, 
  Target, 
  Layers, 
  Settings, 
  Bell, 
  ChevronUp, 
  Flame, 
  MousePointer2, 
  CircleDot, 
  CheckCircle2, 
  ClipboardList, 
  LayoutDashboard, 
  Ghost, 
  Landmark, 
  Gavel, 
  Sword, 
  Satellite, 
  LineChart, 
  DollarSign,
  Pause,
  AlertTriangle,
  Brain,
  ArrowRightCircle,
  UserCheck,
  TrendingDown,
  UserPlus,
  Maximize2,
  Lock,
  Globe,
  X,
  Sparkles,
  MessageSquareCode,
  FileSearch,
  ExternalLink,
  Users,
  Eye,
  Crosshair,
  ShieldAlert,
  Clock,
  ArrowDown,
  ArrowUp,
  Minus,
  Timer,
  LayoutTemplate,
  Unplug,
  ShieldX,
  BarChart4,
  Sun,
  Moon,
  TrendingUp as TrendingIcon,
  Sword as SwordIcon,
  History,
  Workflow
} from 'lucide-react';

/**
 * Alpha Terminal - Tactical Intelligence V8.0
 * Features:
 * - Unified Hidden Hands, Derivatives & Kill Chain Modules
 * - Adaptive Light/Dark Mode (White/Dark Mode Ready)
 * - 4-Column Data Grid + Pre-Signal Snapshots
 * - Inline Oracle Briefing Nodes
 */

// --- Configuration & Mock Data ---

const NAV_ITEMS = [
  { id: 'unified', label: "Unified Intel", icon: Zap },
  { id: 'cot', label: 'COT Positioning', icon: LayoutTemplate },
  { id: 'killchain', label: 'Kill Chain', icon: Crosshair },
  { id: 'politicians', label: 'Politicians', icon: Gavel },
];

const PRE_SIGNAL_INTEL = {
  adp: {
    slug: 'pre-adp-emp',
    title: 'ADP EMPLOYMENT',
    status: 'MISS LIKELY',
    model: '100,000',
    consensus: '150,000',
    delta: '-50,000',
    confidence: '55%',
    bullets: [
      'ICSA 4wk avg 210,750 > 210K → -10K (elevated)',
      'CCSA 1,857,000 ≤ 1.9M → normal (no adj)',
      'Feb NFP -92,000 shock (< -50K) → -30K (trend break)',
      'UNRATE 4.4%, 3mo Δ=+0.0pp → stable (no adj)',
      'Mfg employment -12,000 contracting → -10K'
    ]
  },
  gdp: {
    slug: 'pre-gdp-now',
    title: 'GDP NOWCAST Q1',
    status: 'MISS',
    model: '0.77%',
    consensus: '2.3%',
    delta: '-1.53pp',
    source: 'Atlanta Fed',
    description: 'GDPNow tracks Q1 at 0.77% vs consensus 2.3% → -1.53pp (MISS)'
  }
};

const MACRO_PRESIGNALS = [
  { slug: 'uni-cpi-now', label: 'PRE SIGNAL', title: 'CPI Now', actual: '0.62%', cons: '0.3%', delta: '+0.32%', bias: 'PRE_HOT', note: 'Monitor TLT/SPY puts', color: '#f97316' },
  { slug: 'uni-pce-now', label: 'PRE SIGNAL', title: 'Core PCE', actual: '0.47%', cons: '0.3%', delta: '+0.17%', bias: 'PRE_HOT', note: "Fed's preferred gauge", color: '#f97316' },
  { slug: 'uni-adp-miss', label: 'ADP PRESIGNAL', title: 'ADP Emp', actual: '100k', cons: '150k', delta: '-50k', bias: 'MISS_LIKELY', note: 'Position accordingly', color: '#f43f5e' },
  { slug: 'uni-gdp-miss', label: 'GDP PRESIGNAL', title: 'GDP Q1', actual: '0.77%', cons: '2.3%', delta: '-1.53pp', bias: 'MISS', note: 'Growth warning', color: '#f43f5e' },
];

const HIDDEN_HANDS = [
  { slug: 'uni-hh-1', title: 'HIDDEN HANDS', actor: 'Pol Sell', mspr: '+100', divergence: 'MAX', note: 'monitor reversal', color: '#f43f5e' },
  { slug: 'uni-hh-2', title: 'HIDDEN HANDS', actor: 'Pol Buy', mspr: '-42.01', divergence: 'HIGH', note: 'monitor reversal', color: '#f97316' },
  { slug: 'uni-hh-3', title: 'HIDDEN HANDS', actor: 'Pol Buy', mspr: '-29.87', divergence: 'DIVERGE', note: 'monitor reversal', color: '#3b82f6' },
  { slug: 'uni-hh-4', title: 'HIDDEN HANDS', actor: 'Pol Sell', mspr: '+75.2', divergence: 'MOD', note: 'monitor dist', color: '#eab308' },
];

const HIDDEN_HANDS_OVERVIEW = {
  count: 9,
  tickers: ['IBP', 'CVX', 'FITB', 'HD', 'MPC', 'RPM', 'PH', 'LRCX'],
  insiderNet: '$0',
  spouseAlerts: 0,
  fedTone: 'DOVISH',
  boost: '+2 BOOST'
};

const DERIVATIVES_DATA = {
  gexRegime: 'NEGATIVE',
  totalGex: '-9.8M',
  putWall: '$640',
  callWall: '$655',
  spySpot: '$655.90',
  cotSpecs: '-113,057 SHORT ⚠️ DIVERGENT',
  cotSummary: 'Specs NET SHORT (-113,057), Commercials NET LONG (+19,120) — smart money divergence'
};

const KILL_CHAIN_REPORT = {
  alertLevel: 'RED',
  layersActive: '5/5',
  confidenceCap: '55%',
  capReason: 'ADP Employment Change Weekly 14.4h',
  mismatches: 2,
  reportText: 'KILL CHAIN REPORT — 2026-03-23 21:48:38 Alert: RED | Layers: 5/5 active 📊 FED: Fed Funds Rate: 3.66% (range: 3.50-3.75%) Market Outlook: Market pricing 2bp of hikes (0.1 moves) through Dec 16-17 So'
};

const COT_DATA = [
  { id: 'es', slug: 'cot-es-0317', name: 'ES', date: '2026-03-17', oi: '2,330,659', nonRep: '94K', ratio: '-5%', specsNet: '-113K', commNet: '+19K', specsLong: 35, commLong: 65, signal: 'DIV', summary: 'Specs NET SHORT (-113,057), Commercials NET LONG (+19,120) — smart money divergence' },
];

// --- Specialized Components ---

const MetricBadge = ({ label, value, color = "text-zinc-500 dark:text-zinc-400" }) => (
  <div className="flex flex-col gap-0.5">
    <span className="text-[7px] font-black text-zinc-400 dark:text-zinc-500 uppercase tracking-widest leading-none">{label}</span>
    <span className={`text-[11px] font-mono font-bold ${color}`}>{value}</span>
  </div>
);

const InlineOracleBriefing = ({ item }) => {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchBriefing = async () => {
      setLoading(true);
      try {
        const systemPrompt = "Act as a senior quantitative macro analyst. Explain technical significance and identify catalysts. Keep it extremely concise and formatted with bullet points.";
        const userQuery = `Analyze Signal: ${item.title || item.actor || item.label || 'Tactical Module'}. Metric: ${item.delta || item.mspr || item.value || item.model || 'N/A'}. Bias: ${item.bias || item.status || 'N/A'}. Slug: ${item.slug || 'Node'}`;

        const apiUrl = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key=`;
        const payload = {
          contents: [{ parts: [{ text: userQuery }] }],
          tools: [{ "google_search": {} }],
          systemInstruction: { parts: [{ text: systemPrompt }] },
        };

        const response = await fetch(apiUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        const result = await response.json();
        setAnalysis(result.candidates?.[0]?.content?.parts?.[0]?.text);
      } catch (err) {
        setAnalysis("Uplink protocol failed.");
      } finally {
        setLoading(false);
      }
    };
    fetchBriefing();
  }, [item.slug]);

  return (
    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
      <div className="pt-4 border-t border-zinc-200 dark:border-zinc-800 mt-3 space-y-2">
        {loading ? (
          <div className="flex items-center gap-2 py-1">
            <RefreshCw className="w-3 h-3 text-cyan-500 animate-spin" />
            <span className="text-[9px] font-black text-cyan-500 uppercase tracking-widest animate-pulse">Running Scan...</span>
          </div>
        ) : (
          <div className="bg-cyan-50 dark:bg-cyan-950/20 p-4 rounded-xl border border-cyan-200 dark:border-cyan-800 text-[10px] text-zinc-600 dark:text-zinc-300 leading-relaxed font-medium whitespace-pre-wrap font-sans">
            <div className="flex items-center gap-1.5 mb-2">
              <Brain className="w-3.5 h-3.5 text-cyan-500" />
              <span className="text-[9px] font-black text-cyan-600 dark:text-cyan-400 uppercase tracking-widest">Oracle Brief</span>
            </div>
            {analysis}
          </div>
        )}
      </div>
    </motion.div>
  );
};

// --- Macro Command Primitives ---

const CommandBlock = ({ label, value, sub, color = "text-zinc-900 dark:text-white" }) => (
  <div className="flex flex-col gap-0.5">
    <span className="text-[8px] font-bold text-zinc-500 dark:text-zinc-500 uppercase tracking-widest">{label}</span>
    <span className={`text-sm font-black uppercase tracking-tight ${color}`}>{value}</span>
    {sub && <span className="text-[9px] font-bold text-zinc-400 dark:text-zinc-600">{sub}</span>}
  </div>
);

const MacroCommandBar = () => (
  <div className="bg-white dark:bg-zinc-900/50 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-6 shadow-2xl flex items-center justify-between mb-8 overflow-hidden relative">
     <div className="absolute top-0 left-0 w-1 h-full bg-blue-500" />
     <div className="flex items-center gap-12">
        <CommandBlock label="Macro Regime" value="Neutral" color="text-zinc-500 dark:text-zinc-400" />
        <div className="h-10 w-px bg-zinc-200 dark:bg-zinc-800" />
        <CommandBlock label="Next Event" value="ADP Employment Change Weekly" sub="Countdown: 14.5h" />
     </div>
     <div className="flex items-center gap-12 text-right">
        <CommandBlock label="Confidence Cap" value="55%" color="text-yellow-600 dark:text-yellow-500" />
        <CommandBlock label="System Scan" value="23.8s" color="text-zinc-400 dark:text-zinc-600" />
     </div>
  </div>
);

const StrategyCard = ({ title, icon: Icon, children, slug, onToggle, isExpanded }) => (
  <div 
    onClick={() => onToggle(slug)}
    className={`bg-white dark:bg-zinc-900 border p-6 rounded-2xl transition-all cursor-pointer shadow-xl relative overflow-hidden group ${isExpanded ? 'border-blue-500/30 ring-1 ring-blue-500/10' : 'border-zinc-200 dark:border-zinc-800 hover:border-zinc-300 dark:hover:border-zinc-700'}`}
  >
     <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-8 rounded-lg bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 flex items-center justify-center shadow-inner">
           <Icon className="w-4 h-4 text-zinc-500 dark:text-zinc-400" />
        </div>
        <h3 className="text-xs font-black text-zinc-900 dark:text-white uppercase tracking-widest">{title}</h3>
     </div>
     {children}
     <AnimatePresence>{isExpanded && <InlineOracleBriefing item={{ slug, title }} />}</AnimatePresence>
  </div>
);

// --- Hidden Hands / Derivatives / Kill Chain (New Module) ---

const TacticalBriefingSection = ({ expandedSlug, onToggle }) => (
  <div className="space-y-6 mb-12">
    {/* Hidden Hands Bar */}
    <div 
      onClick={() => onToggle('overview-hh')}
      className={`bg-white dark:bg-zinc-900 border p-8 rounded-2xl transition-all cursor-pointer shadow-xl relative overflow-hidden group ${expandedSlug === 'overview-hh' ? 'border-purple-500/30 ring-1 ring-purple-500/10' : 'border-zinc-200 dark:border-zinc-800 hover:border-zinc-300 dark:hover:border-zinc-700'}`}
    >
       <div className="flex items-center gap-3 mb-8 border-b border-zinc-100 dark:border-zinc-800 pb-4">
          <Ghost className="w-5 h-5 text-purple-400" />
          <h2 className="text-sm font-black text-zinc-900 dark:text-white uppercase tracking-widest">Hidden Hands</h2>
       </div>
       <div className="flex justify-between items-start">
          <div className="space-y-4">
             <div className="flex flex-col">
                <span className="text-3xl font-black text-zinc-900 dark:text-white">{HIDDEN_HANDS_OVERVIEW.count}</span>
                <span className="text-[9px] font-bold text-zinc-400 dark:text-zinc-600 uppercase tracking-widest">Politician Trades</span>
             </div>
             <div className="flex flex-wrap gap-2 max-w-sm">
                {HIDDEN_HANDS_OVERVIEW.tickers.map(t => (
                  <div key={t} className="px-2 py-1 bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800 text-[9px] font-black text-emerald-600 dark:text-emerald-500 rounded">
                    {t}
                  </div>
                ))}
             </div>
          </div>
          <div className="flex flex-col items-center gap-4 text-center px-12 border-x border-zinc-100 dark:border-zinc-800">
             <div className="flex flex-col">
                <span className="text-xl font-black text-emerald-500">{HIDDEN_HANDS_OVERVIEW.insiderNet}</span>
                <span className="text-[8px] font-bold text-zinc-400 dark:text-zinc-600 uppercase">Insider Net</span>
             </div>
             <div className="flex flex-col">
                <span className="text-xl font-black text-zinc-900 dark:text-white">{HIDDEN_HANDS_OVERVIEW.spouseAlerts}</span>
                <span className="text-[8px] font-bold text-zinc-400 dark:text-zinc-600 uppercase">Spouse Alerts</span>
             </div>
          </div>
          <div className="flex flex-col items-end gap-2">
             <span className="text-2xl font-black text-zinc-900 dark:text-white uppercase tracking-tight">{HIDDEN_HANDS_OVERVIEW.fedTone}</span>
             <span className="text-[8px] font-bold text-zinc-400 dark:text-zinc-600 uppercase">Fed Tone</span>
             <div className="flex items-center gap-2 mt-2">
                <Workflow className="w-4 h-4 text-yellow-500" />
                <span className="px-2 py-0.5 bg-yellow-500/10 border border-yellow-500/20 text-[10px] font-black text-yellow-600 uppercase rounded">{HIDDEN_HANDS_OVERVIEW.boost}</span>
             </div>
          </div>
       </div>
       <AnimatePresence>{expandedSlug === 'overview-hh' && <InlineOracleBriefing item={{ slug: 'hh-overview', title: 'Hidden Hands Intelligence' }} />}</AnimatePresence>
    </div>

    <div className="grid grid-cols-2 gap-6">
       {/* Derivatives Module */}
       <div 
        onClick={() => onToggle('overview-deriv')}
        className={`bg-white dark:bg-zinc-900 border p-8 rounded-2xl transition-all cursor-pointer shadow-xl relative group ${expandedSlug === 'overview-deriv' ? 'border-blue-500/30 ring-1 ring-blue-500/10' : 'border-zinc-200 dark:border-zinc-800 hover:border-zinc-300 dark:hover:border-zinc-700'}`}
       >
          <div className="flex items-center gap-3 mb-10 border-b border-zinc-100 dark:border-zinc-800 pb-4">
             <LineChart className="w-5 h-5 text-blue-400" />
             <h2 className="text-sm font-black text-zinc-900 dark:text-white uppercase tracking-widest">Derivatives</h2>
          </div>
          <div className="grid grid-cols-2 gap-x-12 gap-y-8 mb-8">
             <div className="flex flex-col gap-1">
                <span className="text-[8px] font-black text-zinc-400 dark:text-zinc-600 uppercase">GEX Regime</span>
                <span className="text-lg font-black text-rose-500">{DERIVATIVES_DATA.gexRegime}</span>
             </div>
             <div className="flex flex-col gap-1">
                <span className="text-[8px] font-black text-zinc-400 dark:text-zinc-600 uppercase">Total GEX</span>
                <span className="text-lg font-black text-zinc-900 dark:text-white">{DERIVATIVES_DATA.totalGex}</span>
             </div>
             <div className="flex flex-col gap-1">
                <span className="text-[8px] font-black text-zinc-400 dark:text-zinc-600 uppercase">Put Wall</span>
                <span className="text-lg font-black text-zinc-900 dark:text-white">{DERIVATIVES_DATA.putWall}</span>
             </div>
             <div className="flex flex-col gap-1">
                <span className="text-[8px] font-black text-zinc-400 dark:text-zinc-600 uppercase">Call Wall</span>
                <span className="text-lg font-black text-zinc-900 dark:text-white">{DERIVATIVES_DATA.callWall}</span>
             </div>
             <div className="flex flex-col gap-1 col-span-2">
                <span className="text-[8px] font-black text-zinc-400 dark:text-zinc-600 uppercase">SPY Spot</span>
                <span className="text-lg font-black text-zinc-900 dark:text-white">{DERIVATIVES_DATA.spySpot}</span>
             </div>
          </div>
          <div className="pt-6 border-t border-zinc-100 dark:border-zinc-800">
             <div className="flex justify-between items-center mb-1">
                <span className="text-[9px] font-black text-blue-500 dark:text-blue-400">COT ES Specs: <span className="text-blue-400 dark:text-blue-500">{DERIVATIVES_DATA.cotSpecs}</span></span>
             </div>
             <p className="text-[10px] text-zinc-400 dark:text-zinc-600 font-medium italic leading-relaxed">{DERIVATIVES_DATA.cotSummary}</p>
          </div>
          <AnimatePresence>{expandedSlug === 'overview-deriv' && <InlineOracleBriefing item={{ slug: 'deriv-overview', title: 'Derivatives Structure' }} />}</AnimatePresence>
       </div>

       {/* Kill Chain Module */}
       <div 
        onClick={() => onToggle('overview-kc')}
        className={`bg-white dark:bg-zinc-900 border p-8 rounded-2xl transition-all cursor-pointer shadow-xl relative group ${expandedSlug === 'overview-kc' ? 'border-emerald-500/30 ring-1 ring-emerald-500/10' : 'border-zinc-200 dark:border-zinc-800 hover:border-zinc-300 dark:hover:border-zinc-700'}`}
       >
          <div className="flex items-center gap-3 mb-10 border-b border-zinc-100 dark:border-zinc-800 pb-4">
             <SwordIcon className="w-5 h-5 text-emerald-400" />
             <h2 className="text-sm font-black text-zinc-900 dark:text-white uppercase tracking-widest">Kill Chain</h2>
          </div>
          <div className="grid grid-cols-2 gap-x-12 gap-y-8 mb-10">
             <div className="flex flex-col gap-1">
                <span className="text-[8px] font-black text-zinc-400 dark:text-zinc-600 uppercase">Alert Level</span>
                <span className="text-lg font-black text-rose-500">{KILL_CHAIN_REPORT.alertLevel}</span>
             </div>
             <div className="flex flex-col gap-1">
                <span className="text-[8px] font-black text-zinc-400 dark:text-zinc-600 uppercase">Layers Active</span>
                <span className="text-lg font-black text-zinc-900 dark:text-white">{KILL_CHAIN_REPORT.layersActive}</span>
             </div>
             <div className="flex flex-col gap-1">
                <span className="text-[8px] font-black text-zinc-400 dark:text-zinc-600 uppercase">Confidence Cap</span>
                <span className="text-lg font-black text-yellow-500">{KILL_CHAIN_REPORT.confidenceCap}</span>
             </div>
             <div className="flex flex-col gap-1">
                <span className="text-[8px] font-black text-zinc-400 dark:text-zinc-600 uppercase">Cap Reason</span>
                <span className="text-[10px] font-black text-zinc-800 dark:text-zinc-300 leading-tight">{KILL_CHAIN_REPORT.capReason}</span>
             </div>
             <div className="flex flex-col gap-1">
                <span className="text-[8px] font-black text-zinc-400 dark:text-zinc-600 uppercase">Mismatches</span>
                <span className="text-lg font-black text-rose-500">{KILL_CHAIN_REPORT.mismatches}</span>
             </div>
          </div>
          <div className="bg-zinc-50 dark:bg-zinc-950 p-4 rounded-xl border border-zinc-100 dark:border-zinc-800">
             <div className="flex items-start gap-3">
                <History className="w-4 h-4 text-zinc-400 dark:text-zinc-600 mt-0.5" />
                <p className="text-[10px] text-zinc-500 dark:text-zinc-500 leading-relaxed font-medium italic">
                   {KILL_CHAIN_REPORT.reportText}
                </p>
             </div>
          </div>
          <AnimatePresence>{expandedSlug === 'overview-kc' && <InlineOracleBriefing item={{ slug: 'kc-overview', title: 'Kill Chain Report' }} />}</AnimatePresence>
       </div>
    </div>
  </div>
);

const PreSignalSection = ({ onToggle, expandedSlug }) => {
  return (
    <div className="bg-white dark:bg-zinc-900/40 border border-zinc-200 dark:border-zinc-800 rounded-2xl p-8 mb-12 shadow-2xl relative overflow-hidden">
      <div className="flex items-center gap-3 mb-8 border-b border-zinc-100 dark:border-zinc-800 pb-6">
        <Zap className="w-5 h-5 text-yellow-500" />
        <h2 className="text-sm font-black text-zinc-900 dark:text-white uppercase tracking-widest">Pre-Signal Intelligence</h2>
      </div>

      <div className="grid grid-cols-2 gap-10">
        {/* ADP Card */}
        <div 
          onClick={() => onToggle(PRE_SIGNAL_INTEL.adp.slug)}
          className={`bg-zinc-50 dark:bg-zinc-950/50 border rounded-2xl p-8 transition-all cursor-pointer ${expandedSlug === PRE_SIGNAL_INTEL.adp.slug ? 'border-rose-500/30 ring-1 ring-rose-500/10' : 'border-zinc-100 dark:border-zinc-800 hover:border-zinc-200 dark:hover:border-zinc-700'}`}
        >
          <div className="flex justify-between items-start mb-8">
            <div className="flex items-center gap-3">
              <div className="w-3.5 h-3.5 rounded-full bg-rose-500 shadow-[0_0_12px_#f43f5e]" />
              <h3 className="text-[11px] font-black text-zinc-800 dark:text-zinc-300 uppercase tracking-widest">{PRE_SIGNAL_INTEL.adp.title}</h3>
            </div>
            <span className="text-[10px] font-black text-rose-500 uppercase tracking-widest">{PRE_SIGNAL_INTEL.adp.status}</span>
          </div>
          <div className="grid grid-cols-2 gap-8 mb-8 border-b border-zinc-100 dark:border-zinc-800/50 pb-8">
            <div className="flex flex-col gap-1 border-r border-zinc-200 dark:border-zinc-800 pr-8">
              <div className="flex flex-col">
                <span className="text-[8px] font-bold text-zinc-500 dark:text-zinc-500 uppercase">Model Output</span>
                <span className="text-xl font-black text-zinc-900 dark:text-white font-mono">{PRE_SIGNAL_INTEL.adp.model}</span>
              </div>
              <div className="flex flex-col mt-4">
                <span className="text-[8px] font-bold text-zinc-500 dark:text-zinc-500 uppercase">Delta (Miss)</span>
                <span className="text-xl font-black text-rose-500 font-mono">{PRE_SIGNAL_INTEL.adp.delta}</span>
              </div>
            </div>
            <div className="flex flex-col gap-1 pl-4">
              <div className="flex flex-col">
                <span className="text-[8px] font-bold text-zinc-500 dark:text-zinc-500 uppercase">Consensus</span>
                <span className="text-xl font-black text-zinc-900 dark:text-white font-mono">{PRE_SIGNAL_INTEL.adp.consensus}</span>
              </div>
              <div className="flex flex-col mt-4">
                <span className="text-[8px] font-bold text-zinc-500 dark:text-zinc-500 uppercase">System Confidence</span>
                <span className="text-xl font-black text-zinc-900 dark:text-white font-mono">{PRE_SIGNAL_INTEL.adp.confidence}</span>
              </div>
            </div>
          </div>
          <div className="space-y-2">
            {PRE_SIGNAL_INTEL.adp.bullets.map((b, i) => (
              <p key={i} className="text-[10px] text-zinc-500 dark:text-zinc-500 font-medium italic leading-relaxed">· {b}</p>
            ))}
          </div>
          <AnimatePresence>{expandedSlug === PRE_SIGNAL_INTEL.adp.slug && <InlineOracleBriefing item={PRE_SIGNAL_INTEL.adp} />}</AnimatePresence>
        </div>

        {/* GDP Card */}
        <div 
          onClick={() => onToggle(PRE_SIGNAL_INTEL.gdp.slug)}
          className={`bg-zinc-50 dark:bg-zinc-950/50 border rounded-2xl p-8 transition-all cursor-pointer ${expandedSlug === PRE_SIGNAL_INTEL.gdp.slug ? 'border-rose-500/30 ring-1 ring-rose-500/10' : 'border-zinc-100 dark:border-zinc-800 hover:border-zinc-200 dark:hover:border-zinc-700'}`}
        >
          <div className="flex justify-between items-start mb-8">
            <div className="flex items-center gap-3">
              <div className="w-3.5 h-3.5 rounded-full bg-rose-500 shadow-[0_0_12px_#f43f5e]" />
              <h3 className="text-[11px] font-black text-zinc-800 dark:text-zinc-300 uppercase tracking-widest">{PRE_SIGNAL_INTEL.gdp.title}</h3>
            </div>
            <span className="text-[10px] font-black text-rose-500 uppercase tracking-widest">{PRE_SIGNAL_INTEL.gdp.status}</span>
          </div>
          <div className="grid grid-cols-2 gap-8 mb-10 border-b border-zinc-100 dark:border-zinc-800/50 pb-8">
            <div className="flex flex-col gap-1 border-r border-zinc-200 dark:border-zinc-800 pr-8">
              <div className="flex flex-col">
                <span className="text-[8px] font-bold text-zinc-500 dark:text-zinc-500 uppercase">GDPNow Forecast</span>
                <span className="text-xl font-black text-zinc-900 dark:text-white font-mono">{PRE_SIGNAL_INTEL.gdp.model}</span>
              </div>
              <div className="flex flex-col mt-4">
                <span className="text-[8px] font-bold text-zinc-500 dark:text-zinc-500 uppercase">Growth Delta</span>
                <span className="text-xl font-black text-rose-500 font-mono">{PRE_SIGNAL_INTEL.gdp.delta}</span>
              </div>
            </div>
            <div className="flex flex-col gap-1 pl-4">
              <div className="flex flex-col">
                <span className="text-[8px] font-bold text-zinc-500 dark:text-zinc-500 uppercase">Consensus Target</span>
                <span className="text-xl font-black text-zinc-900 dark:text-white font-mono">{PRE_SIGNAL_INTEL.gdp.consensus}</span>
              </div>
              <div className="flex flex-col mt-4">
                <span className="text-[8px] font-bold text-zinc-500 dark:text-zinc-500 uppercase">Source Attribution</span>
                <span className="text-[11px] font-black text-zinc-800 dark:text-white uppercase mt-1">{PRE_SIGNAL_INTEL.gdp.source}</span>
              </div>
            </div>
          </div>
          <p className="text-[11px] text-zinc-500 dark:text-zinc-500 font-medium leading-relaxed italic">
            · {PRE_SIGNAL_INTEL.gdp.description}
          </p>
          <AnimatePresence>{expandedSlug === PRE_SIGNAL_INTEL.gdp.slug && <InlineOracleBriefing item={PRE_SIGNAL_INTEL.gdp} />}</AnimatePresence>
        </div>
      </div>

      <div className="mt-8 text-right border-t border-zinc-100 dark:border-zinc-800 pt-4">
        <span className="text-[9px] font-black text-zinc-400 dark:text-zinc-700 uppercase tracking-widest">Oracle Sync: 05:45 PM ET</span>
      </div>
    </div>
  );
};

// --- Main Grid Snapshot Cards ---

const MacroSnapshotCard = ({ item, isExpanded, onToggle }) => (
  <div 
    onClick={() => onToggle(item.slug)}
    className={`bg-white dark:bg-zinc-950 border p-5 rounded-xl transition-all cursor-pointer shadow-xl relative overflow-hidden group h-full flex flex-col justify-between ${isExpanded ? 'border-cyan-500/30 ring-1 ring-cyan-500/10' : 'border-zinc-200 dark:border-zinc-800 hover:border-zinc-300 dark:hover:border-zinc-700'}`}
  >
    <div>
      <div className="flex justify-between items-start mb-4">
        <div className="flex items-center gap-3">
           <div className="w-8 h-8 rounded-lg bg-zinc-50 dark:bg-zinc-900 border border-zinc-100 dark:border-zinc-800 flex items-center justify-center shadow-inner">
              <Zap className="w-4 h-4 text-orange-500" />
           </div>
           <div className="flex flex-col min-w-0">
              <span className="text-[8px] font-black text-zinc-400 dark:text-zinc-600 uppercase tracking-widest truncate">{item.label}</span>
              <h3 className="text-sm font-black text-zinc-900 dark:text-white group-hover:text-cyan-500 transition-colors uppercase tracking-tight truncate">{item.title}</h3>
           </div>
        </div>
        <div className={`px-2 py-0.5 rounded text-[8px] font-black uppercase flex-shrink-0 ${item.bias.includes('HOT') || item.bias.includes('MISS') ? 'bg-rose-500/10 text-rose-500' : 'bg-emerald-500/10 text-emerald-500'}`}>{item.bias}</div>
      </div>
      <div className="grid grid-cols-3 gap-1 py-3 border-y border-zinc-100 dark:border-zinc-800">
         <MetricBadge label="NOW" value={item.actual} color="text-zinc-900 dark:text-white" />
         <MetricBadge label="CONS" value={item.cons} />
         <MetricBadge label="DELT" value={item.delta} color={item.delta.includes('+') ? 'text-rose-500' : 'text-emerald-500'} />
      </div>
    </div>
    <div className="mt-4 flex justify-between items-center">
       <p className="text-[9px] text-zinc-400 dark:text-zinc-500 font-bold uppercase truncate pr-4">{item.note}</p>
       <ChevronDown className={`w-4 h-4 text-zinc-300 dark:text-zinc-700 transition-all ${isExpanded ? 'rotate-180 text-cyan-500' : ''}`} />
    </div>
    <AnimatePresence>{isExpanded && <InlineOracleBriefing item={item} />}</AnimatePresence>
  </div>
);

const HiddenHandsCard = ({ item, isExpanded, onToggle }) => (
  <div 
    onClick={() => onToggle(item.slug)}
    className={`bg-white dark:bg-zinc-950 border p-5 rounded-xl transition-all cursor-pointer shadow-xl relative overflow-hidden group h-full flex flex-col justify-between ${isExpanded ? 'border-purple-500/30 ring-1 ring-purple-500/10' : 'border-zinc-200 dark:border-zinc-800 hover:border-zinc-300 dark:hover:border-zinc-700'}`}
  >
    <div>
      <div className="flex justify-between items-start mb-4">
        <div className="flex items-center gap-3">
           <div className="w-8 h-8 rounded-lg bg-zinc-50 dark:bg-zinc-900 border border-zinc-100 dark:border-zinc-800 flex items-center justify-center shadow-inner">
              <BarChart4 className="w-4 h-4 text-blue-500" />
           </div>
           <div className="flex flex-col min-w-0">
              <span className="text-[8px] font-black text-zinc-400 dark:text-zinc-600 uppercase tracking-widest truncate">{item.title}</span>
              <h3 className="text-sm font-black text-zinc-900 dark:text-white group-hover:text-purple-500 transition-colors uppercase tracking-tight truncate">{item.actor}</h3>
           </div>
        </div>
        <div className={`px-2 py-0.5 rounded text-[8px] font-black uppercase bg-zinc-100 dark:bg-zinc-900 text-zinc-500 dark:text-zinc-400 border border-zinc-200 dark:border-zinc-800`}>{item.divergence}</div>
      </div>
      <div className="grid grid-cols-2 gap-2 py-3 border-y border-zinc-100 dark:border-zinc-800">
         <MetricBadge label="MSPR" value={item.mspr} color={parseFloat(item.mspr) < 0 ? 'text-rose-500' : 'text-emerald-500'} />
         <MetricBadge label="STAT" value="DIV_ACTIVE" color="text-zinc-900 dark:text-white" />
      </div>
    </div>
    <div className="mt-4 flex justify-between items-center">
       <p className="text-[9px] text-zinc-400 dark:text-zinc-500 font-bold uppercase truncate pr-4">{item.note}</p>
       <ChevronDown className={`w-4 h-4 text-zinc-300 dark:text-zinc-700 transition-all ${isExpanded ? 'rotate-180 text-purple-500' : ''}`} />
    </div>
    <AnimatePresence>{isExpanded && <InlineOracleBriefing item={item} />}</AnimatePresence>
  </div>
);

// --- Main Application ---

export default function App() {
  const [activePage, setActivePage] = useState('unified'); 
  const [loading, setLoading] = useState(true);
  const [expandedSlug, setExpandedSlug] = useState(null);
  const [isDarkMode, setIsDarkMode] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setLoading(false), 1200);
    return () => clearTimeout(timer);
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-50 dark:bg-[#050506] flex items-center justify-center font-mono">
        <div className="flex flex-col items-center gap-6">
          <Activity className="w-12 h-12 text-cyan-500 animate-pulse" />
          <span className="text-[10px] text-zinc-600 font-black uppercase tracking-[0.6em]">Establish Node Sync</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`${isDarkMode ? 'dark' : ''} min-h-screen transition-colors duration-500`}>
    <div className="min-h-screen bg-zinc-50 dark:bg-[#050506] text-zinc-900 dark:text-white font-sans selection:bg-cyan-500/20 overflow-hidden flex flex-col">
      
      <nav className="h-14 border-b border-zinc-200 dark:border-white/5 bg-white dark:bg-[#08080a] flex items-center justify-between px-8 z-[200]">
        <div className="flex items-center gap-4">
          <div className="w-8 h-8 bg-blue-600/10 rounded flex items-center justify-center border border-blue-500/20 shadow-inner">
            <Globe className="w-4 h-4 text-blue-500" />
          </div>
          <span className="text-[10px] font-black uppercase tracking-[0.4em] text-zinc-900 dark:text-white">Alpha <span className="text-blue-500">Terminal</span></span>
        </div>
        <div className="flex items-center gap-4">
          {NAV_ITEMS.map((item) => (
            <button key={item.id} onClick={() => { setActivePage(item.id); setExpandedSlug(null); }} className={`flex items-center gap-2.5 px-3 py-1.5 rounded-lg transition-all ${activePage === item.id ? 'bg-zinc-100 dark:bg-white/5 text-blue-600 dark:text-cyan-400' : 'text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-300'}`}>
              <item.icon className="w-3.5 h-3.5" />
              <span className="text-[9px] font-black uppercase tracking-widest">{item.label}</span>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-4">
          <button 
            onClick={() => setIsDarkMode(!isDarkMode)}
            className="w-8 h-8 rounded-lg border border-zinc-200 dark:border-zinc-800 flex items-center justify-center hover:bg-zinc-50 dark:hover:bg-zinc-900 transition-all text-zinc-500"
          >
            {isDarkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>
          <div className="flex items-center gap-4 text-[10px] font-black text-zinc-400 dark:text-zinc-700 uppercase tracking-widest pl-4 border-l border-zinc-200 dark:border-zinc-800">
             <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" /> Uplink_Live
          </div>
        </div>
      </nav>

      <main className="flex-1 p-10 overflow-y-auto scrollbar-hide relative">
        <AnimatePresence mode="wait">
          
          {activePage === 'unified' && (
            <motion.div key="unified-node" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="max-w-full mx-auto space-y-10 pb-20 px-4">
              
              {/* BREACH ALERT */}
              <div className="bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-500/30 rounded-2xl p-10 flex items-center justify-between relative overflow-hidden shadow-2xl">
                 <div className="absolute top-0 left-0 w-1.5 h-full bg-rose-500 shadow-[0_0_20px_#f43f5e]" />
                 <div className="flex items-center gap-10">
                    <AlertOctagon className="w-16 h-16 text-rose-500 animate-pulse" />
                    <div className="space-y-1">
                       <h1 className="text-5xl font-black text-zinc-900 dark:text-white leading-none tracking-tighter uppercase italic">Wall Breach</h1>
                       <h3 className="text-md font-black text-rose-600 dark:text-rose-500 uppercase tracking-widest">SPY BELOW CALL WALL — RISK OFF PROTOCOL ACTIVE</h3>
                       <p className="text-[10px] font-bold text-zinc-500 dark:text-zinc-700 uppercase tracking-[0.2em]">Detected 05:07 PM ET · System confirmed · Reduce Exposure</p>
                    </div>
                 </div>
              </div>

              {/* COMMAND STACK: MACRO BAR -> STRATEGY CARDS -> PRE-SIGNAL LAYER -> TACTICAL OVERVIEW */}
              <MacroCommandBar />

              <div className="grid grid-cols-3 gap-6">
                 <StrategyCard title="Regime" icon={Satellite} slug="strat-regime" onToggle={setExpandedSlug} isExpanded={expandedSlug === 'strat-regime'}>
                    <div className="flex gap-10">
                       <MetricBadge label="Inflation Score" value="0.519" color="text-rose-500" />
                       <MetricBadge label="Growth Score" value="0.017" color="text-emerald-500" />
                    </div>
                 </StrategyCard>
                 <StrategyCard title="Fed Path" icon={Landmark} slug="strat-fed" onToggle={setExpandedSlug} isExpanded={expandedSlug === 'strat-fed'}>
                    <div className="flex items-baseline gap-4">
                       <span className="text-2xl font-black text-zinc-900 dark:text-white font-mono">3.5–3.75%</span>
                       <span className="text-[10px] font-bold text-zinc-400 dark:text-zinc-600 uppercase">May 6-7 (45d)</span>
                    </div>
                    <div className="flex gap-2 mt-4">
                       {['May 17.2%', 'Jun 100%', 'Jul 100%', 'Sep 100%'].map(p => (
                         <div key={p} className="flex-1 px-2 py-1.5 bg-zinc-50 dark:bg-zinc-950 border border-zinc-100 dark:border-zinc-800 rounded text-[8px] font-black text-center text-zinc-500">
                            {p}
                         </div>
                       ))}
                    </div>
                 </StrategyCard>
                 <StrategyCard title="Economic Edge" icon={LineChart} slug="strat-edge" onToggle={setExpandedSlug} isExpanded={expandedSlug === 'strat-edge'}>
                    <div className="grid grid-cols-3 gap-4 mb-6">
                       <MetricBadge label="CPI MoM" value="0.62%" />
                       <MetricBadge label="PCE MoM" value="0.47%" />
                       <MetricBadge label="CPI YoY" value="3.02%" />
                    </div>
                    <div className="space-y-1.5">
                       <div className="flex justify-between text-[8px] font-bold text-zinc-400 dark:text-zinc-600 uppercase border-b border-zinc-100 dark:border-zinc-800 pb-1">
                          <span>Dynamic Thresholds</span>
                          <span>Oracle Value</span>
                       </div>
                       <div className="flex justify-between text-[10px] font-mono font-bold text-zinc-500">
                          <span>CORE PCE</span>
                          <span className="text-rose-500">0.4438</span>
                       </div>
                    </div>
                 </StrategyCard>
              </div>

              {/* NEW TACTICAL BRIEFING LAYER (HIDDEN HANDS / DERIVS / KILL CHAIN) */}
              <TacticalBriefingSection expandedSlug={expandedSlug} onToggle={setExpandedSlug} />

              <PreSignalSection expandedSlug={expandedSlug} onToggle={setExpandedSlug} />

              {/* TACTICAL GRID FOOTER */}
              <div className="space-y-12 pt-12 border-t border-zinc-200 dark:border-zinc-800">
                <section className="space-y-4">
                   <div className="flex items-center gap-2 px-1">
                      <Activity className="w-5 h-5 text-blue-500" />
                      <h3 className="text-[11px] font-black text-zinc-900 dark:text-white uppercase tracking-[0.3em]">Execution Forecast Grid</h3>
                   </div>
                   <div className="grid grid-cols-4 gap-4">
                      {MACRO_PRESIGNALS.map((item) => (
                         <MacroSnapshotCard key={item.slug} item={item} isExpanded={expandedSlug === item.slug} onToggle={setExpandedSlug} />
                      ))}
                   </div>
                </section>
                <section className="space-y-4">
                   <div className="flex items-center gap-2 px-1">
                      <Layers className="w-5 h-5 text-purple-500" />
                      <h3 className="text-[11px] font-black text-zinc-900 dark:text-white uppercase tracking-[0.3em]">Institutional Divergence Grid</h3>
                   </div>
                   <div className="grid grid-cols-4 gap-4">
                      {HIDDEN_HANDS.map((item) => (
                         <HiddenHandsCard key={item.slug} item={item} isExpanded={expandedSlug === item.slug} onToggle={setExpandedSlug} />
                      ))}
                   </div>
                </section>
              </div>
            </motion.div>
          )}

          {/* ... COT Page remains unchanged ... */}
        </AnimatePresence>
      </main>

      <footer className="h-10 border-t border-zinc-200 dark:border-white/5 bg-white dark:bg-[#08080a] flex items-center justify-between px-8 text-[8px] font-mono text-zinc-500 dark:text-zinc-600 uppercase tracking-widest relative z-[100]">
        <div className="flex gap-10">
          <span className="flex items-center gap-2 tracking-tighter"><Lock className="w-2.5 h-2.5" /> SECURE_UPLINK_v8</span>
          <span className="flex items-center gap-2 tracking-tighter"><Activity className="w-2.5 h-2.5" /> LATENCY: 0.7ms</span>
        </div>
        <span>&copy; 2026 ALPHA TERMINAL // UPLINK_ACTIVE_V8</span>
      </footer>
    </div>
    </div>
  );
}