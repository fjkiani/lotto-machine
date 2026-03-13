import os
import sys
import asyncio
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
from live_monitoring.orchestrator.swarm_router import swarm_dispatch

# Try to load gemini model to get the JSON plan
try:
    import google.generativeai as genai
except ImportError:
    genai = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger(__name__)

COMMANDER_PROMPT = """You are Zeta Swarm Commander. Your job is NOT to think deeply or write essays. 
Your job is to FIRE MULTIPLE ARSENALS IN PARALLEL and collect results.

Rules:
1. NEVER do the work yourself.
2. Identify which arsenals / agents / tools need to run for this query.
3. Output ONLY a parallel dispatch plan in JSON format — nothing else. Do not wrap in markdown tags like ```json. Just raw JSON.
4. Each task gets: agent_name, input_payload, priority (high/medium/low)
5. If something needs sequential dependency, list it as "after: task_id"

Example output ONLY:

{
  "parallel_tasks": [
    {
      "task_id": "1",
      "agent": "DarkPoolMonitor",
      "input": {"ticker": "SPY", "lookback_days": 20},
      "priority": "high"
    },
    {
      "task_id": "2",
      "agent": "GEXCalculator",
      "input": {"index": "SPX"},
      "priority": "high"
    },
    {
      "task_id": "3",
      "agent": "FedToneScanner",
      "input": {"since": "2026-03-01"},
      "priority": "medium"
    }
  ],
  "sequential": [
    {
      "task_id": "4",
      "after": ["1","2","3"],
      "agent": "DivergenceSynthesizer",
      "input": "merge results from 1,2,3"
    }
  ]
}
"""

async def run_orchestration_test():
    load_dotenv()
    
    query = "what's happening in SPX right now?"
    logger.info(f"🚨 Raw Query: '{query}'")
    
    plan_json = None
    
    if genai and os.getenv("GEMINI_API_KEY"):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model = genai.GenerativeModel("gemini-2.5-pro")
        
        prompt = f"{COMMANDER_PROMPT}\n\nQuery: {query}"
        logger.info("📡 Firing to Savage LLM (Gemini 2.5 Pro) for Swarm Dispatch Plan...")
        
        try:
            response = model.generate_content(prompt)
            raw_text = response.text.replace("```json", "").replace("```", "").strip()
            logger.info("✅ LLM Responded with Dispatch Plan")
            plan_json = json.loads(raw_text)
        except Exception as e:
            logger.error(f"Failed to generate/parse JSON from LLM: {e}")
            plan_json = None
            
    if not plan_json:
        logger.warning("No valid plan from LLM. Using fallback mock plan to demonstrate routing.")
        plan_json = {
            "parallel_tasks": [
                {"task_id": "1", "agent": "DarkPoolMonitor", "input": {"ticker": "SPX", "lookback_days": 5}, "priority": "high"},
                {"task_id": "2", "agent": "GEXCalculator", "input": {"index": "SPX"}, "priority": "high"},
                {"task_id": "3", "agent": "InsiderBuys", "input": {"ticker": "SPY"}, "priority": "low"}
            ],
            "sequential": [
                {"task_id": "4", "after": ["1", "2", "3"], "agent": "DivergenceSynthesizer", "input": "Merge DP, GEX, and Insider flow for SPX"}
            ]
        }
        
    logger.info("=== DISPATCH PLAN ===")
    print(json.dumps(plan_json, indent=2))
    print("=====================\n")
    
    # Run through router
    logger.info("🚀 Routing through Swarm Commander...")
    final_output = await swarm_dispatch(plan_json)
    
    logger.info("✅ Swarm Execution Complete. Final Output State:")
    print(json.dumps(final_output, indent=2))

if __name__ == "__main__":
    asyncio.run(run_orchestration_test())
