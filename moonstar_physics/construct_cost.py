"""Token -> USD accounting for construct runs.

Cost source, in order of preference per artifact:
  1. `_cost_usd` reported by the gateway (OpenRouter's usage.cost, incl. the cost of truncated
     retries inside the call): EXACT for those calls;
  2. token counts x the dated price table: an ESTIMATE (providers differ in price, ~3x seen).
A model absent from the price table is reported, never priced at zero silently. Only artifacts that
carry token usage count; calls that failed or timed out entirely leave no artifact and are not counted.
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


def _number(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 else None


def run_cost_breakdown(
    artifact_datas: Iterable[Any], prices: dict[str, dict[str, float]]
) -> dict[str, Any]:
    """Total cost split by source. `is_exact` is True only when every costed artifact carried a
    gateway-reported `_cost_usd` and no model was left unpriced."""
    reported = estimated = truncated = 0.0
    unpriced: set[str] = set()
    for data in artifact_datas:
        usage = artifact_usage(data)
        if usage is None:
            continue
        model, tokens_in, tokens_out = usage
        own = _number(data.get("_cost_usd"))
        if own is not None:
            reported += own
            truncated += _number(data.get("_cost_truncated_usd")) or 0.0   # already inside `own`
            continue
        price = prices.get(model)
        if price is None:
            unpriced.add(model)
            continue
        estimated += tokens_in * price["input"] + tokens_out * price["output"]
    return {
        "total_usd": reported + estimated, "reported_usd": reported, "estimated_usd": estimated,
        "truncated_usd": truncated, "unpriced_models": sorted(unpriced),
        "is_exact": estimated == 0.0 and not unpriced,
    }


def run_cost_usd(
    artifact_datas: Iterable[Any], prices: dict[str, dict[str, float]]
) -> tuple[float, list[str]]:
    b = run_cost_breakdown(artifact_datas, prices)
    return b["total_usd"], b["unpriced_models"]


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