"""
Prediction Engine — Predicts files, symbols, APIs, tests, risks, and cost estimates for proposed changes.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..intelligence.intent_compiler import CompiledIntent
from .impact_analyzer import impact_analyzer

logger = logging.getLogger("devpilot.analysis.prediction_engine")


@dataclass
class ChangePrediction:
    predicted_files: list[str] = field(default_factory=list)
    predicted_apis: list[str] = field(default_factory=list)
    predicted_tests: list[str] = field(default_factory=list)
    risk_assessment: str = "low"
    estimated_cost_usd: float = 0.05
    reassurance_reason: str = ""


class PredictionEngine:
    """Pre-evaluates tasks to estimate execution cost and blast radius prior to running code tools."""

    def predict_change_impact(self, intent: CompiledIntent) -> ChangePrediction:
        """Combine heuristic analyzer outcomes into a composite impact prediction."""
        predicted_files = list(intent.affected_components)
        
        # Analyze impact on each of the predicted files
        additional_files = set()
        for f in predicted_files:
            impacted = impact_analyzer.analyze_file_change(f)
            additional_files.update(impacted)

        all_files = list(set(predicted_files + list(additional_files)))
        affected_tests = impact_analyzer.get_affected_tests(set(all_files))

        # Base heuristics for API and cost metrics
        predicted_apis = []
        for f in all_files:
            if "route" in f or "controller" in f or "api" in f:
                predicted_apis.append(f)

        # Cost estimation heuristic: $0.05 per affected file (LLM processing allocation)
        est_cost = max(0.02, len(all_files) * 0.04)

        prediction = ChangePrediction(
            predicted_files=all_files,
            predicted_apis=predicted_apis,
            predicted_tests=affected_tests,
            risk_assessment=intent.estimated_risk,
            estimated_cost_usd=round(est_cost, 3),
            reassurance_reason=f"Based on impact analysis: {len(all_files)} files may be modified and {len(affected_tests)} tests run."
        )

        logger.info(
            f"Prediction completed: files={len(prediction.predicted_files)}, "
            f"cost=${prediction.estimated_cost_usd:.3f}, risk={prediction.risk_assessment}"
        )
        return prediction


# ── Singleton ───────────────────────────────────────────────────────────────

prediction_engine = PredictionEngine()
