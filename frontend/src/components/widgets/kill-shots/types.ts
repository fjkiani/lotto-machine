// Strict TypeScript types for /kill-shots-live `layers` response.
// DO NOT add fields not verified in the backend. Anti-slop rule enforced here.

export interface KillShotsLayers {
  // BRAIN
  brain_boost?: number;
  brain_reasons?: string[];
  brain_slug?: string;
  explanation_BRAIN?: string;
  divergence_boost?: number;
  politician_buys?: number;
  politician_sells?: number;
  hot_tickers?: string[];
  insider_net_usd?: number;

  // COT
  cot_boost?: number;
  cot_specs_net?: number;
  cot_comm_net?: number;
  cot_divergent?: boolean;
  cot_slug?: string;
  explanation_COT?: string;

  // GEX
  gex_boost?: number;
  total_gex_dollars?: number;
  gex_regime?: string;
  gex_gamma_flip?: number;
  gex_spot_price?: number;
  gex_max_pain?: number;
  gex_slug?: string;
  explanation_GEX?: string;

  // FED vs DP
  fed_dp_boost?: number;
  spy_short_vol_pct?: number;
  fed_dp_divergence?: boolean;
  fed_dp_slug?: string;
  vix?: number;
  explanation_FED_DP?: string;

  // COMBINED scorer
  combined_boost?: number;
  combined_slug?: string;
  cot_extreme?: boolean;
  gex_positive?: boolean;
  axlfi_signal?: string;
  pts_above_call_wall?: number;
  qqq_reshort_spike?: boolean;
  qqq_reshort_note?: string;
  qqq_sv_delta?: number;
  qqq_sv_latest?: number;
  qqq_sv_prev?: number;
  politician_cluster?: number;
  politician_signal?: string;
  politician_tickers?: string[];
  explanation_COMBINED?: string;

  // TECH scorer
  tech_boost?: number;
  rsi_14?: number;
  tech_slug?: string;
  explanation_TECH?: string;

  // GEO scorer
  geo_boost?: number;
  oil_wti?: number;
  geo_slug?: string;
  explanation_GEO?: string;

  // DP TREND scorer
  dp_trend_boost?: number;
  dp_trend_slug?: string;
  explanation_DP_TREND?: string;

  // OPEX scorer
  opex_boost?: number;
  opex_slug?: string;
  explanation_OPEX?: string;

  // SENTIMENT scorer
  sentiment_boost?: number;
  sentiment_slug?: string;
  explanation_SENTIMENT?: string;

  // Kill chain enrichment (written into layers by main.py)
  kill_chain_confluence?: string;
  kill_chain_bullish_pts?: number;
  kill_chain_bearish_pts?: number;
  axlfi_call_wall?: number;
  axlfi_put_wall?: number;
  axlfi_spot?: number;
  alpha_graph_verdict?: string | null;
  alpha_graph_confidence?: number | null;
  alpha_graph_thesis?: string | null;
  alpha_graph_direction?: string | null;
  alpha_graph_primary_risk?: string | null;
  alpha_graph_last_run?: string | null;
  absorption_detected?: boolean;
  absorption_price?: number;
  absorption_vol_ratio?: number;
  volume_spikes_today?: number;
  spy_session_trend?: string;
  fed_veto?: string;
  fed_veto_hours?: number;
  fed_veto_next?: string;

  // DP Signal enrichment (from DarkPoolTrend via signalsApi)
  dp_trend_velocity?: number | null;
  dp_trend_direction?: 'ACCUMULATION' | 'DISTRIBUTION' | null;
}

// ── Kill Chain Layer types ────────────────────────────────────────────────────

export interface KillChainLayer {
  name: string;
  triggered: boolean;
  value?: number;
  signal?: string;
  raw_value?: number;
  symbol?: string;
  label?: string;
  report_date?: string;
  specs_long?: number;
  specs_short?: number;
  pts_above_call_wall?: number;
  layer3_threshold_pct?: number;
}

export interface KillChainLayerMacro {
  name: string;
  triggered: boolean;
  value: number;           // war_status 0-10
  signal: string;          // WAR_PREMIUM | NEUTRAL
  veto_longs: boolean;
  veto_reason: string;
  oil_wti: number;
  oil_wti_source: string;  // manual | yfinance | yahoo_chart_v8 | alphavantage | fallback_95_stress
  war_status_breakdown?: string;
  manual_override_warning?: string;
}

export interface KillChainResult {
  score: number;
  verdict: string;
  direction: string;
  confluence: string;
  triggered_count: number;
  armed: boolean;
  bullish_points: number;
  bearish_points: number;
  verdict_score_layers_only: number;
  total_points_with_brain: number;
  layer_1: KillChainLayer;
  layer_2: KillChainLayer;
  layer_3: KillChainLayer;
  layer_4: KillChainLayer;
  layer_5: KillChainLayer;
  layer_macro?: KillChainLayerMacro;
  computed_at_utc?: string;
}

// ── Full /kill-shots-live response ───────────────────────────────────────────

export interface KillShotsResponse {
  divergence_score: number;
  verdict: string;
  reconciled_verdict?: string;
  reconciliation_reasons?: string[];
  action: string;
  action_plan?: {
    position: string;
    entry_trigger: string;
    invalidation: string;
    time_window: string;
  };
  layers: KillShotsLayers;
  reasons: string[];
  explanations: Record<string, string>;
  kill_chain?: KillChainResult;
  timestamp: string;
  error?: string;
}
