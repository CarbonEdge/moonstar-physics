from __future__ import annotations

import json
from pathlib import Path

import pytest

from moonstar_physics.construct_cost import (
    artifact_usage, load_prices, run_cost_usd, usage_by_model,
)

_ROOT = Path(__file__).parent.parent
_PRICES = _ROOT / "pipelines" / "prices.json"
_MODELS = _ROOT / "pipelines" / "models.json"


def _llm(model, i, o):
    return {"response": "x", "_model": model, "_input_tokens": i, "_output_tokens": o}


def test_every_construct_model_is_priced():
    prices = load_prices(_PRICES)
    models = json.loads(_MODELS.read_text(encoding="utf-8"))
    for key in ("MODEL_PLANNER", "MODEL_GENERATOR", "MODEL_CONSTRUCT_REVIEW"):
        assert models[key] in prices, f"{models[key]} missing from pipelines/prices.json"


def test_prices_file_is_dated_and_sourced():
    raw = json.loads(_PRICES.read_text(encoding="utf-8"))
    assert raw["as_of"] and raw["source"]


def test_artifact_usage_skips_deterministic_and_usage_less_artifacts():
    assert artifact_usage({"verdict": "PARTIAL"}) is None
    assert artifact_usage({"_model": "none", "_input_tokens": 0, "_output_tokens": 0}) is None
    assert artifact_usage({"response": "x"}) is None
    assert artifact_usage(_llm("m/x", 10, 20)) == ("m/x", 10, 20)


def test_run_cost_prices_input_and_output_separately():
    prices = {"m/x": {"input": 1e-6, "output": 2e-6}}
    total, unpriced = run_cost_usd([_llm("m/x", 1_000_000, 500_000), {"verdict": "x"}], prices)
    assert total == pytest.approx(1.0 + 1.0)
    assert unpriced == []


def test_unpriced_model_is_reported_not_silently_free():
    total, unpriced = run_cost_usd([_llm("mystery/model", 5, 5)], {"m/x": {"input": 1, "output": 1}})
    assert total == 0.0 and unpriced == ["mystery/model"]


def test_usage_by_model_aggregates():
    got = usage_by_model([_llm("a", 1, 2), _llm("a", 3, 4), _llm("b", 5, 6), {"verdict": "x"}])
    assert got == {"a": {"input_tokens": 4, "output_tokens": 6}, "b": {"input_tokens": 5, "output_tokens": 6}}