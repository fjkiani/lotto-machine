# 🔧 ALPHA TERMINAL - Frontend Plumber Tasks

> **Mission:** Build Bloomberg's replacement in 10 weeks
> **Reference:** `.cursor/rules/alpha-terminal-frontend-plan.mdc`

---

## 📋 MASTER TASK LIST

### Phase 0: Codebase Understanding (BEFORE Phase 1)

**CRITICAL:** Before writing ANY code, you MUST understand the existing backend. This is NOT a greenfield project!

#### 0.1 Study Existing Architecture
- [ ] **P0-001:** Read `.cursor/rules/alpha-terminal-frontend-plan.mdc` section "EXISTING CODEBASE INTEGRATION"
- [ ] **P0-002:** Study `live_monitoring/orchestrator/unified_monitor.py` - understand how it orchestrates everything
- [ ] **P0-003:** Study `live_monitoring/core/signal_generator.py` - understand signal generation logic
- [ ] **P0-004:** Study `core/data/ultimate_chartexchange_client.py` - understand data source
- [ ] **P0-005:** Study `live_monitoring/orchestrator/checkers/` - understand all checker types
- [ ] **P0-006:** Review existing signal types in `live_monitoring/core/lottery_signals.py`

#### 0.2 Understand Data Flow
- [ ] **P0-007:** Trace how a signal is generated: API → SignalGenerator → Checker → Alert
- [ ] **P0-008:** Understand how `UnifiedAlphaMonitor` runs (it's already in production!)
- [ ] **P0-009:** Understand the alert system (`alert_manager.py`) - you'll bridge this
- [ ] **P0-010:** Review existing WebSocket usage (if any) in the codebase

#### 0.3 Set Up Development Environment
- [ ] **P0-011:** Clone the repository and set up Python environment
- [ ] **P0-012:** Install all Python dependencies (`pip install -r requirements.txt`)
- [ ] **P0-013:** Set up `.env` file with `CHARTEXCHANGE_API_KEY` (get from Alpha)
- [ ] **P0-014:** Test that you can import and use `UltimateChartExchangeClient`
- [ ] **P0-015:** Test that you can import and use `SignalGenerator`
- [ ] **P0-016:** Run existing monitor locally (if possible) to see it in action

#### 0.4 Create Integration Test Scripts
- [ ] **P0-017:** Create `backend/tests/integration/test_chartexchange_client.py` - test data fetching
- [ ] **P0-018:** Create `backend/tests/integration/test_signal_generator.py` - test signal generation
- [ ] **P0-019:** Create `backend/tests/integration/test_monitor_bridge.py` - test bridge pattern
- [ ] **P0-020:** Document any issues or questions in `INTEGRATION_NOTES.md`

**Acceptance Criteria:**
- ✅ You can successfully import and use all key classes
- ✅ You understand the data flow from API → Signal → Alert
- ✅ You know which classes to use for each widget
- ✅ You've tested data fetching with real API keys
- ✅ You've created at least 3 integration test scripts

**Time Estimate:** 2-3 days (before starting Phase 1)

---

### Phase 1: Foundation (Week 1-2)

#### 1.1 Project Setup
- [ ] **P1-001:** Initialize Next.js 14 project with App Router
  ```bash
  npx create-next-app@latest alpha-terminal --typescript --tailwind --eslint --app
  ```
- [ ] **P1-002:** Install core dependencies
  ```bash
  npm install @radix-ui/react-* lucide-react framer-motion zustand socket.io-client
  npm install recharts lightweight-charts date-fns
  npm install -D @types/node
  ```
- [ ] **P1-003:** Set up shadcn/ui
  ```bash
  npx shadcn-ui@latest init
  npx shadcn-ui@latest add button card badge input tabs tooltip
  ```
- [ ] **P1-004:** Configure Tailwind with custom design tokens (see MDC for colors)
- [ ] **P1-005:** Set up fonts (JetBrains Mono, Inter, Space Grotesk)

#### 1.2 Design System
- [ ] **P1-006:** Create `styles/themes/dark.css` with CSS variables
- [ ] **P1-007:** Build base UI components:
  - [ ] `Card` with header/footer pattern
  - [ ] `Badge` with color variants (bullish, bearish, neutral)
  - [ ] `Gauge` component for percentages
  - [ ] `Sparkline` mini chart component
  - [ ] `DataTable` sortable table component
- [ ] **P1-008:** Create `GlowEffect` animation component
- [ ] **P1-009:** Set up Framer Motion variants for consistent animations

#### 1.3 Layout Structure
- [ ] **P1-010:** Build `Header` component with:
  - Logo
  - Quick stats (SPY, QQQ prices)
  - System status indicator
  - User menu
- [ ] **P1-011:** Build `Sidebar` component with:
  - Navigation links
  - Active indicator
  - Collapse/expand
- [ ] **P1-012:** Build `WidgetGrid` component with:
  - Responsive grid layout
  - Drag-and-drop (optional)
  - Widget resize handles
- [ ] **P1-013:** Create dashboard layout (`app/(dashboard)/layout.tsx`)

#### 1.4 Backend API Setup
- [ ] **P1-014:** Initialize FastAPI project structure (see MDC section "Backend API Layer")
- [ ] **P1-015:** Create `app/integrations/unified_monitor_bridge.py` - bridge to existing monitor
  - Reference: MDC section "Key Classes You'll Interact With" → MonitorBridge example
- [ ] **P1-016:** Create `app/core/data_formatters.py` - convert Python objects to JSON
  - Functions: `signal_to_dict()`, `level_to_dict()`, `alert_to_dict()`
- [ ] **P1-017:** Set up PostgreSQL with TimescaleDB
- [ ] **P1-018:** Set up Redis (Upstash or local) for caching
- [ ] **P1-019:** Create database models and migrations (see MDC "Database Schema")
- [ ] **P1-020:** Implement basic health check endpoint
- [ ] **P1-021:** Set up CORS and security middleware
- [ ] **P1-022:** Create first API endpoint: `GET /api/market/{symbol}/quote`
  - Reference: MDC "Code Examples" → Market Data Endpoint
  - Use existing `RegimeDetector` and `yfinance`
- [ ] **P1-023:** Create second API endpoint: `GET /api/signals`
  - Reference: MDC "Code Examples" → Signals Endpoint with Caching
  - Use existing `SignalGenerator` and `UltraInstitutionalEngine`

---

### Phase 2: Core Widgets (Week 3-4)

#### 2.1 Market Overview Widget
- [ ] **P2-001:** Create `MarketOverview` component shell
- [ ] **P2-002:** Integrate TradingView Lightweight Charts
- [ ] **P2-003:** Implement candlestick chart with:
  - Multiple timeframes (1m, 5m, 15m, 1h, 1d)
  - Volume bars
  - Crosshair with price label
- [ ] **P2-004:** Add DP level overlays (horizontal lines)
- [ ] **P2-005:** Add gamma flip level indicator
- [ ] **P2-006:** Add VWAP line
- [ ] **P2-007:** Create regime indicator badge
- [ ] **P2-008:** Build quote panel (price, change, volume)
- [ ] **P2-009:** **API:** `GET /api/market/{symbol}/quote`
- [ ] **P2-010:** **API:** `GET /api/market/{symbol}/candles`

#### 2.2 Signals Center Widget
- [ ] **P2-011:** Create `SignalsCenter` component shell
- [ ] **P2-012:** Build `SignalCard` component with:
  - Color-coded border (bullish/bearish)
  - Confidence meter
  - Entry/Stop/Target display
  - Reasoning expandable section
  - Master signal badge
- [ ] **P2-013:** Implement signal list with filters:
  - By type (squeeze, gamma, DP, etc.)
  - By confidence (master only toggle)
  - By symbol
- [ ] **P2-014:** Add signal countdown timer (for time-sensitive)
- [ ] **P2-015:** **API:** `GET /api/signals`
- [ ] **P2-016:** **API:** `GET /api/signals/master`

#### 2.3 Dark Pool Flow Widget
- [ ] **P2-017:** Create `DarkPoolFlow` component shell
- [ ] **P2-018:** Build horizontal bar chart for DP levels
- [ ] **P2-019:** Color code levels (support=green, resistance=red, battleground=gold)
- [ ] **P2-020:** Add current price indicator line
- [ ] **P2-021:** Build buy/sell pressure gauge
- [ ] **P2-022:** Create recent prints feed (scrolling list)
- [ ] **P2-023:** Show distance to nearest levels
- [ ] **P2-024:** **API:** `GET /api/darkpool/{symbol}/levels`
- [ ] **P2-025:** **API:** `GET /api/darkpool/{symbol}/summary`

#### 2.4 WebSocket Infrastructure
- [ ] **P2-026:** Create `ConnectionManager` class (backend)
  - Reference: MDC "WebSocket Integration Pattern" → UnifiedWebSocketManager
- [ ] **P2-027:** Implement Redis pub/sub for scaling
- [ ] **P2-028:** Create `UnifiedWebSocketManager` that intercepts monitor alerts
  - Reference: MDC "WebSocket Integration Pattern" → Backend example
  - Hook into `alert_manager.send_discord` to broadcast via WebSocket
- [ ] **P2-029:** Create `useUnifiedWebSocket` hook (frontend)
  - Reference: MDC "WebSocket Integration Pattern" → Frontend example
- [ ] **P2-030:** Implement channel subscription system
- [ ] **P2-031:** Add reconnection logic with exponential backoff
- [ ] **P2-032:** Create connection status indicator
- [ ] **P2-033:** **WS:** `/ws/unified` - unified stream (all alerts)
- [ ] **P2-034:** **WS:** `/ws/market/{symbol}` - price stream
- [ ] **P2-035:** **WS:** `/ws/signals` - signal stream

---

### Phase 3: Advanced Widgets (Week 5-6)

#### 3.1 Gamma Tracker Widget
- [ ] **P3-001:** Create `GammaTracker` component shell
- [ ] **P3-002:** Build gamma exposure chart (strike vs GEX)
- [ ] **P3-003:** Add max pain indicator with distance
- [ ] **P3-004:** Create P/C ratio gauge
- [ ] **P3-005:** Add gamma flip level line
- [ ] **P3-006:** Build OI heatmap by strike
- [ ] **P3-007:** Add expiration selector tabs
- [ ] **P3-008:** Show dealer position indicator
- [ ] **P3-009:** **API:** `GET /api/gamma/{symbol}`
- [ ] **P3-010:** **API:** `GET /api/gamma/{symbol}/expirations`

#### 3.2 Squeeze Scanner Widget
- [ ] **P3-011:** Create `SqueezeScanner` component shell
- [ ] **P3-012:** Build sortable data table with columns:
  - Symbol
  - Score (with color gradient)
  - Short Interest %
  - Borrow Fee %
  - Days to Cover
  - FTD Spike
  - DP Support
  - 5D Change (sparkline)
- [ ] **P3-013:** Add filter controls (min score, min SI%, etc.)
- [ ] **P3-014:** Create expandable row for full analysis
- [ ] **P3-015:** Add "Scan Now" button with loading state
- [ ] **P3-016:** **API:** `GET /api/squeeze/candidates`
- [ ] **P3-017:** **API:** `GET /api/squeeze/{symbol}`

#### 3.3 Options Flow Widget
- [ ] **P3-018:** Create `OptionsFlow` component shell
- [ ] **P3-019:** Build P/C ratio gauge with historical comparison
- [ ] **P3-020:** Create max pain vs current price visualization
- [ ] **P3-021:** Build unusual activity feed (scrolling)
- [ ] **P3-022:** Create OI by strike heatmap
- [ ] **P3-023:** Add volume vs OI chart
- [ ] **P3-024:** Build sentiment indicator
- [ ] **P3-025:** **API:** `GET /api/options/{symbol}/flow`
- [ ] **P3-026:** **API:** `GET /api/options/{symbol}/unusual`

#### 3.4 Reddit Sentiment Widget
- [ ] **P3-027:** Create `RedditSentiment` component shell
- [ ] **P3-028:** Build mention count with trend arrow
- [ ] **P3-029:** Create sentiment gauge (-100 to +100)
- [ ] **P3-030:** Add velocity sparkline
- [ ] **P3-031:** Build signal type badge
- [ ] **P3-032:** Add DP synthesis indicator
- [ ] **P3-033:** Create top mentioned tickers list
- [ ] **P3-034:** **API:** `GET /api/reddit/{symbol}`
- [ ] **P3-035:** **API:** `GET /api/reddit/trending`

---

### Phase 4: Intelligence Layer (Week 7-8)

#### 4.1 Macro Intelligence Widget
- [ ] **P4-001:** Create `MacroIntel` component shell
- [ ] **P4-002:** Build event calendar with countdown
- [ ] **P4-003:** Create Fed sentiment indicator
- [ ] **P4-004:** Build Trump activity feed
- [ ] **P4-005:** Create economic surprise chart
- [ ] **P4-006:** Add sector impact indicators
- [ ] **P4-007:** **API:** `GET /api/macro/summary`
- [ ] **P4-008:** **API:** `GET /api/macro/economic`

#### 4.2 Narrative Brain Widget
- [ ] **P4-009:** Create `NarrativeBrain` component shell
- [ ] **P4-010:** Build large narrative text block with typewriter effect
- [ ] **P4-011:** Create confidence meter
- [ ] **P4-012:** Build key factors breakdown (weighted list)
- [ ] **P4-013:** Create recommendation card
- [ ] **P4-014:** Add alert badges
- [ ] **P4-015:** Implement "Ask AI" input
- [ ] **P4-016:** **API:** `GET /api/narrative/current`
- [ ] **P4-017:** **API:** `POST /api/narrative/ask`

#### 4.3 Cross-Widget Integration
- [ ] **P4-018:** Create global state store (Zustand)
- [ ] **P4-019:** Implement symbol synchronization across widgets
- [ ] **P4-020:** Add cross-widget highlighting (hover effects)
- [ ] **P4-021:** Create unified alert system
- [ ] **P4-022:** Implement browser notifications

---

### Phase 5: Polish & Deploy (Week 9-10)

#### 5.1 Performance Optimization
- [ ] **P5-001:** Implement React Server Components where possible
- [ ] **P5-002:** Add lazy loading for heavy widgets
- [ ] **P5-003:** Optimize chart rendering (virtualization)
- [ ] **P5-004:** Add skeleton loaders for all widgets
- [ ] **P5-005:** Implement request deduplication
- [ ] **P5-006:** Add service worker for offline support

#### 5.2 Mobile Responsiveness
- [ ] **P5-007:** Create mobile layout breakpoints
- [ ] **P5-008:** Build collapsible widget views
- [ ] **P5-009:** Add touch-friendly controls
- [ ] **P5-010:** Test on tablets and phones

#### 5.3 Error Handling
- [ ] **P5-011:** Add error boundaries to all widgets
- [ ] **P5-012:** Create fallback UI components
- [ ] **P5-013:** Implement retry logic for failed requests
- [ ] **P5-014:** Add toast notifications for errors
- [ ] **P5-015:** Set up Sentry error tracking

#### 5.4 Testing
- [ ] **P5-016:** Write unit tests for utility functions
- [ ] **P5-017:** Write component tests for widgets
- [ ] **P5-018:** Write integration tests for API
- [ ] **P5-019:** Write E2E tests for critical flows
- [ ] **P5-020:** Performance testing (Lighthouse)

#### 5.5 Deployment
- [ ] **P5-021:** Set up Vercel project for frontend
- [ ] **P5-022:** Configure environment variables
- [ ] **P5-023:** Set up Render/Railway for backend
- [ ] **P5-024:** Configure PostgreSQL (Neon/Supabase)
- [ ] **P5-025:** Configure Redis (Upstash)
- [ ] **P5-026:** Set up CI/CD pipeline
- [ ] **P5-027:** Configure custom domain
- [ ] **P5-028:** Set up SSL certificates
- [ ] **P5-029:** Create deployment documentation

---

## 🎯 PRIORITY MATRIX

| Priority | Tasks | Impact | Effort |
|----------|-------|--------|--------|
| **P0 (Critical)** | P1-001 to P1-005, P2-026 to P2-033 | Foundation | High |
| **P1 (High)** | P2-001 to P2-025 | Core functionality | High |
| **P2 (Medium)** | P3-001 to P3-035 | Advanced features | Medium |
| **P3 (Low)** | P4-001 to P4-022 | Intelligence | Medium |
| **P4 (Polish)** | P5-001 to P5-029 | Production ready | Low |

---

## 🔗 DEPENDENCIES

```
P1-001 → P1-002 → P1-003 → P1-004 → P1-005
                                    ↓
P1-006 → P1-007 → P1-008 → P1-009 → P1-010 → P1-011 → P1-012 → P1-013
                                                                  ↓
P2-026 → P2-027 → P2-028 → P2-029 → P2-030 → P2-031 → P2-032 → P2-033
    ↓                                                              ↓
P2-001 → P2-002 → ... → P2-010                                    ↓
P2-011 → P2-012 → ... → P2-016 ←──────────────────────────────────┘
P2-017 → P2-018 → ... → P2-025
```

---

## 📝 ACCEPTANCE CRITERIA

### Widget Standards
- [ ] Loads within 500ms
- [ ] Updates in real-time (< 1 second)
- [ ] Handles loading state gracefully
- [ ] Handles error state gracefully
- [ ] Responsive on all screen sizes
- [ ] Accessible (keyboard navigation, screen readers)
- [ ] Matches design system colors/typography

### API Standards
- [ ] Response time < 200ms (p95)
- [ ] Returns proper error codes
- [ ] Includes pagination where needed
- [ ] Cached appropriately
- [ ] Documented in OpenAPI spec

### WebSocket Standards
- [ ] Connects within 2 seconds
- [ ] Reconnects automatically
- [ ] Handles message backpressure
- [ ] Supports multiple channels
- [ ] Includes heartbeat mechanism

---

## 🚨 BLOCKERS & RISKS

| Risk | Mitigation |
|------|------------|
| TradingView chart performance | Use lightweight-charts, virtualize data |
| WebSocket scaling | Use Redis pub/sub, horizontal scaling |
| Real-time data costs | Aggressive caching, rate limiting |
| Mobile performance | Lazy loading, reduced animations |
| API rate limits | Request deduplication, caching |

---

## 📊 PROGRESS TRACKING

### Week 1-2: Foundation
- [ ] Project setup complete
- [ ] Design system implemented
- [ ] Layout structure built
- [ ] Backend API scaffolded

### Week 3-4: Core Widgets
- [ ] Market Overview functional
- [ ] Signals Center functional
- [ ] Dark Pool Flow functional
- [ ] WebSocket working

### Week 5-6: Advanced Widgets
- [ ] Gamma Tracker functional
- [ ] Squeeze Scanner functional
- [ ] Options Flow functional
- [ ] Reddit Sentiment functional

### Week 7-8: Intelligence
- [ ] Macro Intel functional
- [ ] Narrative Brain functional
- [ ] Cross-widget integration complete
- [ ] Alert system working

### Week 9-10: Polish
- [ ] Performance optimized
- [ ] Mobile responsive
- [ ] Fully tested
- [ ] Deployed to production

---

## 💬 COMMUNICATION

- **Daily standups:** 9:00 AM ET
- **Code reviews:** Required for all PRs
- **Design reviews:** Weekly on Fridays
- **Demo:** End of each phase

---

## 📚 RESOURCES

- **Design Spec:** `.cursor/rules/alpha-terminal-frontend-plan.mdc`
- **API Docs:** `/backend/docs` (auto-generated)
- **Component Library:** Storybook (to be set up)
- **Figma:** [Link TBD]

---

**ALPHA'S MESSAGE TO PLUMBERS:**
*"Build this like your portfolio depends on it. Because it fucking does. Every millisecond of latency is money left on the table. Every pixel that's out of place is a trader who won't trust us. Make it beautiful. Make it fast. Make it legendary."* 🚀💰🎯

---

**Document Version:** 1.0
**Last Updated:** December 17, 2024
**Owner:** Alpha

