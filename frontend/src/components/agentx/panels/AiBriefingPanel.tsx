/**
 * AiBriefingPanel — Slide-in oracle overlay
 *
 * Calls backend POST /api/v1/agents/signal-brief (Groq, server-side key).
 */

import { useState, useEffect } from 'react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

export interface BriefableItem {
  /** For UnifiedSignal */
  action?: string;
  tickers?: string[];
  source?: string;
  detail?: string;
  id?: string;
  /** For trade items */
  name?: string;
  ticker?: string;
  type?: string;
  size?: string;
  slug?: string;
  /** For convergence cards */
  signal?: string;
  logic?: string;
  meaning?: string;
}

interface AiBriefingPanelProps {
  item: BriefableItem;
  onClose: () => void;
}

export function AiBriefingPanel({ item, onClose }: AiBriefingPanelProps) {
  const [analysis, setAnalysis] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!item) return;

    const fetchBriefing = async () => {
      setLoading(true);
      setAnalysis(null);

      try {
        const response = await fetch(`${API_URL}/agents/signal-brief`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            action: item.action,
            type: item.type,
            signal: item.signal,
            ticker: item.ticker,
            tickers: item.tickers,
            name: item.name,
            source: item.source,
            detail: item.detail,
            logic: item.logic,
            meaning: item.meaning,
            size: item.size,
            slug: item.slug,
            id: item.id,
          }),
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          const msg =
            typeof data.detail === 'string'
              ? data.detail
              : Array.isArray(data.detail)
                ? data.detail.map((d: { msg?: string }) => d.msg).join('; ')
                : response.statusText;
          setAnalysis(`BRIEFING_ENGINE_OFFLINE: ${msg || response.status}`);
          return;
        }
        if (data.analysis) {
          setAnalysis(data.analysis);
        } else {
          setAnalysis('No analysis returned — check backend GROQ_API_KEY.');
        }
      } catch {
        setAnalysis('BRIEFING_ENGINE_OFFLINE: Connection to API failed.');
      } finally {
        setLoading(false);
      }
    };

    fetchBriefing();
  }, [item]);

  const displayTicker = item.ticker || (item.tickers ? item.tickers[0] : '—');
  const displayAction = item.action || item.type || item.signal || '—';
  const isBuy = displayAction.toLowerCase().includes('buy') || displayAction.includes('CONVERGENCE');

  return (
    <div className="oracle-panel">
      {/* Header */}
      <div className="oracle-panel__header">
        <div className="oracle-panel__title-group">
          <span className="oracle-panel__subtitle">Tactical Oracle</span>
          <span className="oracle-panel__title">AI_BRIEFING_NODE</span>
        </div>
        <button onClick={onClose} className="oracle-panel__close">✕</button>
      </div>

      {/* Body */}
      <div className="oracle-panel__body">
        {loading ? (
          <div className="oracle-panel__loading">
            <div className="oracle-panel__spinner" />
            <span className="oracle-panel__loading-text">Scanning Grid</span>
          </div>
        ) : (
          <>
            {/* Signal metadata */}
            <section className="oracle-panel__section">
              <span className="oracle-panel__section-title">Signal Metadata</span>
              <div className="oracle-panel__metadata">
                <div className="oracle-panel__meta-row">
                  <div>
                    <span className="oracle-panel__meta-label">Entity</span>
                    <span className="oracle-panel__meta-value">{item.name || item.source || 'Institutional'}</span>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <span className="oracle-panel__meta-label">Status</span>
                    <span className={`oracle-panel__status ${isBuy ? 'oracle-panel__status--buy' : 'oracle-panel__status--sell'}`}>
                      {displayAction}
                    </span>
                  </div>
                </div>
                <div className="oracle-panel__meta-row">
                  <span className="oracle-panel__ticker">${displayTicker}</span>
                  <span className="oracle-panel__slug">ID: {item.slug || item.id || '—'}</span>
                </div>
              </div>
            </section>

            {/* Analysis */}
            <section className="oracle-panel__section">
              <span className="oracle-panel__section-title">Intelligence Analysis</span>
              <div className="oracle-panel__analysis">{analysis}</div>
            </section>
          </>
        )}
      </div>
    </div>
  );
}
