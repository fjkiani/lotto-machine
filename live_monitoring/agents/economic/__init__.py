"""
Economic Intelligence Engine - Modular Architecture

A LEARNING system that predicts Fed Watch movements from economic data.
Integrates Dark Pool signals for institutional positioning context.

Modules:
- models.py: Data contracts and types
- database.py: SQLite persistence
- data_collector.py: Historical data fetching (FRED, BLS, etc.)
- pattern_learner.py: Statistical pattern recognition
- dp_integrator.py: Dark Pool signal integration
- predictor.py: Fed Watch prediction engine
- alert_generator.py: Alert formatting and delivery
- engine.py: Main orchestrator

Usage:
    from live_monitoring.agents.economic import EconomicIntelligenceEngine
    
    engine = EconomicIntelligenceEngine()
    engine.train()  # Load historical data and learn patterns
    
    prediction = engine.predict("NFP", surprise_sigma=-2.0)
    # Returns: {predicted_shift: +8.5%, confidence: 0.78, ...}
"""

from .engine import EconomicIntelligenceEngine

__all__ = ['EconomicIntelligenceEngine']


