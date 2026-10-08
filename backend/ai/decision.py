"""AI decision layer. Phase 1 provides a leakage-safe baseline interface."""
from dataclasses import dataclass
from typing import Literal

Decision = Literal["TAKE", "SKIP", "WAIT"]

@dataclass
class AIDecision:
    decision: Decision
    probability: float
    expected_r: float
    confidence: float
    model_version: str = "baseline-rule-v0"

class BaselineDecisionModel:
    """Temporary deterministic baseline; replace with trained tabular model after data collection."""
    def __init__(self, min_probability: float = 0.60):
        self.min_probability = min_probability

    def predict(self, features: dict) -> AIDecision:
        score = 0.50
        if features.get("trend_aligned"): score += 0.12
        if features.get("cycle_atr_ratio", 0) >= 1.0: score += 0.08
        if features.get("spread_points", 10**9) <= features.get("max_spread_points", 80): score += 0.05
        score = max(0.01, min(0.99, score))
        decision = "TAKE" if score >= self.min_probability else "SKIP"
        return AIDecision(decision, score, 0.0, score, "baseline-rule-v0")
