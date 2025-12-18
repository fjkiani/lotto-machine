# 🔥 Alpha Terminal Backend - Savage LLM Agents

Backend API layer for Alpha Terminal with Savage LLM Agent integration.

## 🏗️ Architecture

```
backend/
├── app/
│   ├── main.py                    # FastAPI application entry point
│   ├── api/v1/
│   │   └── agents.py              # Agent API endpoints
│   ├── services/
│   │   └── savage_agents.py      # Agent implementations
│   ├── integrations/
│   │   └── unified_monitor_bridge.py  # Bridge to existing monitor
│   └── core/
│       └── dependencies.py        # FastAPI dependencies
```

## 🚀 Quick Start

### Prerequisites

```bash
pip install fastapi uvicorn redis python-dotenv
```

### Environment Variables

```bash
# Required
CHARTEXCHANGE_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here

# Optional (for agent memory)
REDIS_URL=redis://localhost:6379
```

### Run the API

```bash
# Development
python3 -m backend.app.main

# Or with uvicorn directly
uvicorn backend.app.main:app --reload --port 8000
```

### Test the Agents

```bash
python3 test_savage_agents.py
```

## 📊 API Endpoints

### Agent Endpoints

#### `POST /api/v1/agents/{agent_name}/analyze`
Analyze data with a specific savage agent.

**Supported agents:**
- `market` - Market analysis agent
- `signal` - Signal analysis agent
- `darkpool` - Dark pool analysis agent

**Request:**
```json
{
  "symbol": "SPY",
  "data": {...},  // Optional - will fetch if not provided
  "context": {...}  // Optional
}
```

**Response:**
```json
{
  "insight": "Savage analysis text...",
  "confidence": 0.85,
  "actionable": true,
  "warnings": ["Warning 1", "Warning 2"],
  "timestamp": "2025-01-XXT...",
  "agent": "Market Agent"
}
```

#### `GET /api/v1/agents/narrative/current`
Get current narrative brain synthesis (combines all agents).

**Response:**
```json
{
  "narrative": "Unified market narrative...",
  "confidence": 0.82,
  "agent_insights": {
    "Market Agent": {...},
    "Signal Agent": {...},
    ...
  },
  "timestamp": "2025-01-XXT...",
  "data_sources": ["market", "signals", "synthesis_result", ...]
}
```

#### `POST /api/v1/agents/narrative/ask`
Ask the Narrative Brain a question.

**Request:**
```json
{
  "question": "What's happening with SPY right now?"
}
```

**Response:**
```json
{
  "question": "What's happening with SPY right now?",
  "answer": "Savage answer...",
  "timestamp": "2025-01-XXT...",
  "data_sources": ["market", "signals", ...]
}
```

## 🧠 Available Agents

### Market Agent
- **Domain:** Market data analysis
- **Input:** Market quotes, regime, VIX
- **Output:** Market analysis with savage insights

### Signal Agent
- **Domain:** Trading signal analysis
- **Input:** List[LiveSignal], SynthesisResult
- **Output:** Signal prioritization and reasoning

### Dark Pool Agent
- **Domain:** Dark pool intelligence
- **Input:** DP levels, prints, battlegrounds
- **Output:** Institutional positioning analysis

### Narrative Brain Agent (Master)
- **Domain:** Unified synthesis
- **Input:** ALL agent insights + all data
- **Output:** One unified market narrative

## 🔌 Integration with Existing Monitor

The `MonitorBridge` class reads from the existing `UnifiedAlphaMonitor` without modifying it:

- Reads signals from `SignalGenerator.generate_signals()`
- Reads synthesis from `SignalBrainEngine.analyze()`
- Reads narratives from `NarrativeBrain.memory.get_recent_narratives()`
- Converts Python dataclasses to JSON for API responses

## 📝 Development

### Adding a New Agent

1. Create agent class in `backend/app/services/savage_agents.py`:

```python
class MyAgent(SavageAgent):
    def __init__(self, redis_client=None):
        super().__init__("My Agent", "my_domain", redis_client)
    
    def _build_prompt(self, data: Dict, context: Dict = None) -> str:
        # Build prompt from actual data structures
        return prompt
```

2. Add to agent registry in `backend/app/api/v1/agents.py`:

```python
elif agent_name == "my_agent":
    _agents[agent_name] = MyAgent(redis_client)
```

3. Add endpoint logic to fetch data from MonitorBridge

### Testing

```bash
# Test agent infrastructure
python3 test_savage_agents.py

# Test API endpoints
curl http://localhost:8000/api/v1/agents/market/analyze \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"symbol": "SPY"}'
```

## 🚨 Important Notes

1. **Don't Modify Existing Monitor:** The `UnifiedAlphaMonitor` is running in production. The bridge only READS from it.

2. **Use Actual Data Structures:** All agents use verified data structures from the codebase (LiveSignal, SynthesisResult, etc.)

3. **Error Handling:** All agents handle missing data gracefully and return error messages in insights.

4. **Caching:** MonitorBridge caches responses (30s for signals, 5s for market data) to avoid hammering APIs.

## 📚 References

- Architecture: `SAVAGE_LLM_AGENT_ARCHITECTURE_V2.md`
- Frontend Plan: `.cursor/rules/alpha-terminal-frontend-plan.mdc`
- Plumber Tasks: `FRONTEND_PLUMBER_TASKS.md`

