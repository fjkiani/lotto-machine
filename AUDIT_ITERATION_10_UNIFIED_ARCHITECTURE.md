# ITERATION 10: Unified Architecture Document

**Date:** 2025-12-05  
**Status:** COMPLETE

---

## System Architecture Overview

### Current Architecture (REALITY)

```
┌─────────────────────────────────────────────────────────────┐
│                    THREE SEPARATE SYSTEMS                    │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│  LIVE MONITORING     │  │  STREAMLIT ANALYSIS   │  │  MULTI-AGENT        │
│                      │  │                      │  │                      │
│  Entry:              │  │  Entry:              │  │  Entry:              │
│  run_lotto_machine   │  │  streamlit_app_llm   │  │  src/main.py        │
│         │            │  │         │            │  │         │            │
│         ├─> Data    │  │         ├─> Data     │  │         ├─> Agents   │
│         ├─> Signals │  │         ├─> Analysis │  │         ├─> LangGraph│
│         ├─> Trading │  │         └─> UI       │  │         └─> Output   │
│         └─> Alerts  │  │                      │  │                      │
│                      │  │                      │  │                      │
│  ✅ Production Ready │  │  ✅ Working           │  │  ✅ Working         │
└──────────────────────┘  └──────────────────────┘  └──────────────────────┘
         │                          │                          │
         └──────────────────────────┴──────────────────────────┘
                          NO INTEGRATION
```

---

## Data Flow

### Live Monitoring System

```
ChartExchange API (Tier 3)
    ↓
ultimate_chartexchange_client.py
    ↓
data_fetcher.py (caching, rate limiting)
    ↓
ultra_institutional_engine.py
    ↓
signal_generator.py
    ↓
    ├─> Narrative enrichment (optional)
    ├─> Price action filter
    ├─> Risk manager
    └─> Alert router
        ├─> Console
        ├─> CSV
        ├─> Slack
        └─> Discord

yfinance (direct)
    ↓
    ├─> price_action_filter.py
    ├─> risk_manager.py
    └─> gamma_exposure.py
```

### Streamlit System

```
YahooFinanceConnector (RapidAPI)
    ↓
    ├─> options_analyzer.py
    ├─> technical_analyzer.py
    └─> general_analyzer.py

RealTimeFinanceConnector
    ↓
    └─> analysis modules

TechnicalIndicatorsConnector
    ↓
    └─> technical_analyzer.py

All analyzers
    ↓
ui_components.py
    ↓
Streamlit UI
```

### Multi-Agent System

```
LangGraph State
    ↓
Agent Selection
    ↓
    ├─> warren_buffett.py
    ├─> technicals.py
    ├─> options_analyst.py
    └─> sentiment.py
    ↓
portfolio_manager.py (synthesis)
    ↓
Output
```

---

## Component Interaction Map

### Core Components

```
┌─────────────────────────────────────────────────────────┐
│                    SHARED CORE                           │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  core/ultra_institutional_engine.py                      │
│    └─> Builds institutional context                      │
│                                                           │
│  core/data/ultimate_chartexchange_client.py              │
│    └─> ChartExchange API client                          │
│                                                           │
│  configs/chartexchange_config.py                        │
│    └─> API configuration                                 │
│                                                           │
└─────────────────────────────────────────────────────────┘
         │
    ┌────┴────┬──────────────┬──────────────┐
    │         │              │              │
┌───▼───┐ ┌──▼───┐    ┌─────▼─────┐  ┌────▼────┐
│ Live  │ │Stream│    │ Multi-    │  │ Core    │
│Monitor│ │ lit  │    │ Agent     │  │ Systems │
└───────┘ └──────┘    └───────────┘  └─────────┘
```

### Live Monitoring Components

```
run_lotto_machine.py
    │
    ├─> DataFetcher
    │   └─> UltimateChartExchangeClient
    │
    ├─> SignalGenerator
    │   ├─> UltraInstitutionalEngine
    │   ├─> NarrativePipeline (optional)
    │   ├─> GammaExposureTracker
    │   └─> RedditSentimentAnalyzer
    │
    ├─> RiskManager
    │   └─> yfinance (ATR calculation)
    │
    ├─> PriceActionFilter
    │   └─> yfinance (price/VIX)
    │
    └─> AlertRouter
        ├─> ConsoleAlerter
        ├─> CSVLogger
        ├─> SlackAlerter
        └─> DiscordAlerter
```

---

## API Dependencies

### External APIs

| API | Purpose | Rate Limit | Status |
|-----|---------|------------|--------|
| ChartExchange (Tier 3) | Institutional data | 1000/min | ✅ Active |
| yfinance | Price/options data | ~2000/hour | ✅ Active |
| Alpaca | Trade execution | Varies | ✅ Ready |
| RapidAPI Yahoo Finance | Market data | Varies | ⚠️ Partial |
| RapidAPI Real-Time Finance | News/trends | Varies | ⚠️ Partial |
| RapidAPI Technical Indicators | Indicators | Varies | ⚠️ Partial |
| LLM APIs (OpenAI, Anthropic, Gemini) | Analysis | Varies | ✅ Active |
| Perplexity | News search | Varies | ⚠️ Optional |
| Discord | Alerts | Varies | ✅ Active |
| Slack | Alerts | Varies | ✅ Active |

---

## Configuration Requirements

### Required Environment Variables

```bash
# ChartExchange API
CHARTEXCHANGE_API_KEY=xxx

# Alpaca (for trading)
ALPACA_API_KEY=xxx
ALPACA_SECRET_KEY=xxx

# LLM APIs (for analysis)
OPENAI_API_KEY=xxx
ANTHROPIC_API_KEY=xxx
GOOGLE_API_KEY=xxx

# Optional
PERPLEXITY_API_KEY=xxx
RAPIDAPI_KEY=xxx
DISCORD_WEBHOOK_URL=xxx
SLACK_WEBHOOK_URL=xxx
```

### Configuration Files

1. **`live_monitoring/config/monitoring_config.py`**
   - Trading parameters
   - Alert settings
   - Feature flags

2. **`configs/chartexchange_config.py`**
   - API key
   - Tier level

---

## Ideal Architecture (FUTURE)

```
┌─────────────────────────────────────────────────────────────┐
│                    UNIFIED SYSTEM                            │
└─────────────────────────────────────────────────────────────┘

                    ┌──────────────┐
                    │  Data Layer  │
                    │  (Unified)   │
                    └──────┬───────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────▼──────┐  ┌────────▼────────┐  ┌──────▼──────┐
│   Signals    │  │    Analysis     │  │   Agents    │
│  Generator   │  │   (Shared)      │  │  (Optional) │
└──────┬───────┘  └────────┬────────┘  └──────┬──────┘
       │                  │                  │
       └──────────────────┼──────────────────┘
                          │
              ┌────────────┴────────────┐
              │                         │
      ┌───────▼──────┐        ┌────────▼────────┐
      │   Trading   │        │   UI/Dashboard  │
      │   Engine    │        │   (Unified)     │
      └──────────────┘        └─────────────────┘
```

---

## Recommendations

1. **Create unified data layer** - Single access point
2. **Create shared analysis library** - Reuse across systems
3. **Build integration layer** - Connect systems
4. **Create unified UI** - Single dashboard
5. **Document interfaces** - Clear API contracts

---

**Deliverable:** ✅ Unified architecture document

