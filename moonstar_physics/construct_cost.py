"""Token -> USD accounting for construct runs.

Costs are estimates: they count only artifacts that carry token usage
(successful LLM calls). Failed or retried calls leave no artifact and are
not counted. A model absent from the price table is reported, never priced
at zero silently.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def load_prices(path: Any) -> dict[str, dict[str, float]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        model: {
            "input": float(p["input_usd_per_token"]),
            "output": float(p["output_usd_per_token"]),
        }
        for model, p in data["models"].items()
    }


def artifact_usage(data: Any) -> tuple[str, int, int] | None:
    if not isinstance(data, dict):
        return None
    model = data.get("_model")
    if not model or model == "none":
        return None
    if "_input_tokens" not in data and "_output_tokens" not in data:
        return None
    return str(model), int(data.get("_input_tokens") or 0), int(data.get("_output_tokens") or 0)


def run_cost_usd(
    artifact_datas: Iterable[Any], prices: dict[str, dict[str, float]]
) -> tuple[float, list[str]]:
    total = 0.0
    unpriced: set[str] = set()
    for data in artifact_datas:
        usage = artifact_usage(data)
        if usage is None:
            continue
        model, tokens_in, tokens_out = usage
        price = prices.get(model)
        if price is None:
            unpriced.add(model)
            continue
        total += tokens_in * price["input"] + tokens_out * price["output"]
    return total, sorted(unpriced)


def usage_by_model(artifact_datas: Iterable[Any]) -> dict[str, dict[str, int]]:
    totals: dict[str, dict[str, int]] = {}
    for data in artifact_datas:
        usage = artifact_usage(data)
        if usage is None:
            continue
        model, tokens_in, tokens_out = usage
        row = totals.setdefault(model, {"input_tokens": 0, "output_tokens": 0})
        row["input_tokens"] += tokens_in
        row["output_tokens"] += tokens_out
    return totals