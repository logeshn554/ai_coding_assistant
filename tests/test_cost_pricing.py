"""Tests for config-driven cost calculation (no hardcoded model pricing tables)."""
from __future__ import annotations

import os
from unittest.mock import patch

from backend.app.adapters.base import ModelAdapter


def test_calculate_cost_uses_profile_rates():
    cost, estimated = ModelAdapter.calculate_cost(
        "any-model-name",
        1_000_000,
        1_000_000,
        profile={"input_cost_per_m": 1.0, "output_cost_per_m": 2.0},
    )
    assert estimated is False
    assert abs(cost - 3.0) < 1e-9


def test_calculate_cost_env_override():
    with patch.dict(os.environ, {"LOOPIX_INPUT_COST_PER_M": "0.5", "LOOPIX_OUTPUT_COST_PER_M": "1.5"}):
        cost, estimated = ModelAdapter.calculate_cost("whatever", 1_000_000, 0)
    assert estimated is False
    assert abs(cost - 0.5) < 1e-9


def test_calculate_cost_default_is_estimated():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("LOOPIX_INPUT_COST_PER_M", None)
        os.environ.pop("LOOPIX_OUTPUT_COST_PER_M", None)
        cost, estimated = ModelAdapter.calculate_cost("unknown-model", 1_000_000, 1_000_000)
    assert estimated is True
    assert cost > 0
