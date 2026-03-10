import asyncio
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# --- Mock Agent Registry for Swarm ---
# In reality, these would map to your actual agent classes (DarkPoolMonitor, GEXCalculator, etc.)
class MockAgent:
    def __init__(self, name: str):
        self.name = name

    async def run(self, input_data: Any) -> Dict[str, Any]:
        logger.info(f"[{self.name}] Executing with input: {input_data}")
        await asyncio.sleep(1) # Simulate network/processing time
        return {"agent": self.name, "status": "success", "processed_data": f"Data for {input_data}"}

class DivergenceSynthesizer:
    async def run(self, input_data: Any) -> Dict[str, Any]:
        logger.info(f"[DivergenceSynthesizer] Synthesizing results: {input_data}")
        await asyncio.sleep(1)
        return {"agent": "DivergenceSynthesizer", "status": "success", "verdict": "Market is acting strange. Puts on SPY."}


def get_agent(agent_name: str):
    """Factory to retrieve the appropriate Agent instance."""
    if agent_name == "DivergenceSynthesizer":
        return DivergenceSynthesizer()
    # Fallback mock for testing
    return MockAgent(agent_name)

def merge_dependencies(deps: list, instructions: str) -> dict:
    """Format the results of the parallel run for the sequential synthesizer."""
    return {
        "instructions": instructions,
        "context": deps
    }

async def swarm_dispatch(plan_json: dict) -> dict:
    """
    Executes a Zeta Swarm Commander JSON dispatch plan.
    Runs 'parallel_tasks' concurrently, then runs 'sequential' tasks.
    """
    results = {}
    
    # 1. Parallel Phase
    parallel_tasks = plan_json.get("parallel_tasks", [])
    if parallel_tasks:
        logger.info(f"🚀 Unleashing Swarm: {len(parallel_tasks)} parallel tasks...")
        
        # Build tasks
        async def run_task(task_def):
            agent = get_agent(task_def["agent"])
            # Execute agent
            result = await agent.run(task_def["input"])
            return task_def["task_id"], result

        # Gather concurrently
        gathered = await asyncio.gather(*(run_task(t) for t in parallel_tasks))
        
        for task_id, res in gathered:
            results[task_id] = res

    # 2. Sequential Phase
    sequential_tasks = plan_json.get("sequential", [])
    if sequential_tasks:
        logger.info(f"🧠 Synthesis Phase: {len(sequential_tasks)} sequential tasks...")
        
        for seq_task in sequential_tasks:
            # Collect dependency results
            deps_results = [results.get(str(t_id)) for t_id in seq_task.get("after", [])]
            merged_input = merge_dependencies(deps_results, seq_task["input"])
            
            agent = get_agent(seq_task["agent"])
            final_res = await agent.run(merged_input)
            results[seq_task["task_id"]] = final_res

    return results

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
    
    # Example JSON plan (simulated output from Savage LLM)
    sample_plan = {
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
                "after": ["1", "2", "3"],
                "agent": "DivergenceSynthesizer",
                "input": "merge results from 1,2,3"
            }
        ]
    }
    
    logger.info("Starting Swarm Router Test...")
    final_results = asyncio.run(swarm_dispatch(sample_plan))
    logger.info(f"Final Swarm Output:\n{json.dumps(final_results, indent=2)}")
