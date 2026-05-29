"""Analog package: FRED client, API stubs, verified analog scorer, oil betas."""

from analog.analog_scorer import AnalogScoreResult, score_analogs
from analog.oil_beta import get_eps_model_oil_betas, load_oil_beta_verified

__all__ = [
    "AnalogScoreResult",
    "get_eps_model_oil_betas",
    "load_oil_beta_verified",
    "score_analogs",
]
