"""Pure functions for the construct bench: summarise a run, aggregate N runs, render a report.

No I/O and no network, so every number in a report can be reproduced from saved run JSON.
Honesty rules baked in:
  * every $ figure is labelled PROVISIONAL (token x price table) unless EVERY run's cost came from
    the gateway-reported OpenRouter cost (P6.1), in which case it is labelled as reported;
  * proportions carry a Wilson 95 % interval, and the report warns when N < 10;
  * a run that failed (gateway/wallclock) is counted as failed, never silently dropped.
"""
from __future__ import annotations

import copy
import math
import statistics
from collections import Counter
from typing import Any

COST_LABEL = "provisional (token x price table; gateway reports 0.0)"
COST_LABEL_EXACT = "reported by OpenRouter per call, incl. truncated retries; failed/timed-out calls are not counted"
_DROP_TEXT = ("Planner", "Derive_A", "Derive_B", "construct_critic", "devils_advocate", "synthesizer")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a proportion k/n."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _by_name(artifacts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {a["transform_name"]: a["data"] for a in artifacts}


def summarise_run(result: dict[str, Any]) -> dict[str, Any]:
    """One row per run. Works on a run_construct result (completed or failed)."""
    if result.get("status") != "completed":
        return {"status": "failed", "error": str(result.get("error", ""))[:200], "verdict": None,
                "rounds": 0, "cost_usd": 0.0, "elapsed_seconds": result.get("elapsed_seconds")}
    per_round: list[dict[str, Any]] = []
    for r in result.get("rounds", []):
        by = _by_name(r["artifacts"])
        cands: dict[str, Any] = {}
        for label in ("a", "b"):
            crit = by.get(f"criteria_{label}")
            if crit is None:
                continue
            ok = not crit.get("error")
            cands[label.upper()] = {
                "verdict": crit.get("verdict"),
                "unmet_hard": list(crit.get("unmet_hard", [])) if ok else None,
                "n_unmet": len(crit.get("unmet_hard", [])) if ok else None,
            }
        best = r["best_candidate"]
        best_row = cands.get(best, {})
        per_round.append({
            "round": r["round"], "verdict": r["verdict"], "best_candidate": best,
            "best_unmet_hard": best_row.get("unmet_hard"), "best_n_unmet": best_row.get("n_unmet"),
            "candidates": cands, "cost_usd": r.get("cost_usd", 0.0),
        })
    n_series = [p["best_n_unmet"] for p in per_round if p["best_n_unmet"] is not None]
    regressions = sum(1 for a, b in zip(n_series, n_series[1:]) if b > a)
    all_n = [c["n_unmet"] for p in per_round for c in p["candidates"].values() if c["n_unmet"] is not None]
    first_partial = next((p["round"] for p in per_round if p["verdict"] in ("PARTIAL", "CONSTRUCTED")), None)
    first_constructed = next((p["round"] for p in per_round if p["verdict"] == "CONSTRUCTED"), None)
    best_round = result.get("best_round")
    final = next((p for p in per_round if p["round"] == best_round), None)
    return {
        "status": "completed", "verdict": result.get("verdict"), "stop_reason": result.get("stop_reason"),
        "rounds": len(per_round), "best_round": best_round,
        "final_unmet_hard": final["best_unmet_hard"] if final else None,
        "min_n_unmet": min(all_n) if all_n else None,
        "first_partial_round": first_partial, "first_constructed_round": first_constructed,
        "regressions": regressions, "per_round": per_round,
        "cost_usd": float(result.get("cost_usd", 0.0)), "elapsed_seconds": result.get("elapsed_seconds"),
        "cost_is_exact": bool(result.get("cost_is_exact", False)),
        "cost_truncated_usd": float(result.get("cost_truncated_usd", 0.0) or 0.0),
        "unpriced_models": result.get("unpriced_models", []),
    }


def _stats(values: list[Any]) -> dict[str, float] | None:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return {"min": min(vals), "median": statistics.median(vals), "max": max(vals), "mean": statistics.fmean(vals)}


def aggregate(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(summaries)
    done = [s for s in summaries if s["status"] == "completed"]
    verdicts = Counter(s["verdict"] for s in done)
    counts = {v: verdicts.get(v, 0) for v in ("CONSTRUCTED", "PARTIAL", "NOT_FOUND")}
    le1 = sum(1 for s in done if s["min_n_unmet"] is not None and s["min_n_unmet"] <= 1)
    hist = Counter(s["min_n_unmet"] for s in done if s["min_n_unmet"] is not None)
    return {
        "n": n, "completed": len(done), "failed": n - len(done),
        "verdict_counts": counts,
        "verdict_intervals": {v: wilson(c, n) for v, c in counts.items()},
        "reached_le1_unmet": le1, "reached_le1_unmet_interval": wilson(le1, n),
        "min_unmet_histogram": dict(sorted(hist.items())),
        "rounds_to_first_partial": _stats([s["first_partial_round"] for s in done if s["first_partial_round"]]),
        "regressions_per_run": _stats([s["regressions"] for s in done]),
        "cost_usd": _stats([s["cost_usd"] for s in done]),
        "elapsed_seconds": _stats([s["elapsed_seconds"] for s in done]),
        "cost_all_exact": bool(done) and all(s.get("cost_is_exact") for s in done),
        "cost_truncated_usd": _stats([s.get("cost_truncated_usd", 0.0) for s in done]),
        "unpriced_models": sorted({m for s in done for m in s.get("unpriced_models", [])}),
    }


def _fmt_stats(s: dict[str, float] | None, fmt: str) -> str:
    if not s:
        return "n/a"
    return f"min {s['min']:{fmt}} / median {s['median']:{fmt}} / max {s['max']:{fmt}}"


def render_report(meta: dict[str, Any], agg: dict[str, Any], summaries: list[dict[str, Any]]) -> str:
    n = agg["n"]
    lines = [f"# Construct bench: {meta.get('tag', '?')}", ""]
    for k in ("date", "spec", "models", "max_rounds", "note"):
        if meta.get(k) is not None:
            lines.append(f"- {k}: {meta[k]}")
    lines += [f"- runs: {n} ({agg['completed']} completed, {agg['failed']} failed)", ""]
    if n < 10:
        lines += [f"> WARNING: N = {n} < 10. Intervals are wide; do not claim a difference from this alone.", ""]
    lines += ["## Outcomes", "", "| verdict | runs | 95% Wilson interval |", "|---|---|---|"]
    for v in ("CONSTRUCTED", "PARTIAL", "NOT_FOUND"):
        lo, hi = agg["verdict_intervals"][v]
        lines.append(f"| {v} | {agg['verdict_counts'][v]} / {n} | {lo:.0%} - {hi:.0%} |")
    lo, hi = agg["reached_le1_unmet_interval"]
    lines += [
        "",
        f"- runs whose best candidate reached <= 1 unmet hard criterion: {agg['reached_le1_unmet']} / {n} ({lo:.0%} - {hi:.0%})",
        f"- min unmet hard criteria (best candidate over all rounds) histogram: {agg['min_unmet_histogram']}",
        f"- rounds to first PARTIAL-or-better: {_fmt_stats(agg['rounds_to_first_partial'], '.1f')}",
        f"- regression events per run (best candidate got worse vs previous round): {_fmt_stats(agg['regressions_per_run'], '.1f')}",
        "", "## Cost and time", "",
        f"- cost per run, USD, **{COST_LABEL_EXACT if agg['cost_all_exact'] else COST_LABEL}**: "
        f"{_fmt_stats(agg['cost_usd'], '.3f')}",
        f"- of which wasted on truncated attempts, USD: {_fmt_stats(agg['cost_truncated_usd'], '.3f')}",
        f"- elapsed per run, seconds: {_fmt_stats(agg['elapsed_seconds'], '.0f')}",
    ]
    if agg["unpriced_models"]:
        lines.append(f"- UNPRICED models (cost undercounted): {', '.join(agg['unpriced_models'])}")
    lines += ["", "## Runs", "",
              "| # | status | verdict | rounds | stop | final unmet (best) | min unmet | regressions | cost |",
              "|---|---|---|---|---|---|---|---|---|"]
    for i, s in enumerate(summaries, 1):
        if s["status"] != "completed":
            lines.append(f"| {i} | FAILED | - | - | {s.get('error', '')[:40]} | - | - | - | - |")
            continue
        lines.append(
            f"| {i} | ok | {s['verdict']} | {s['rounds']} | {s['stop_reason']} | {s['final_unmet_hard']} "
            f"| {s['min_n_unmet']} | {s['regressions']} | ${s['cost_usd']:.3f}{'' if s.get('cost_is_exact') else ' (est.)'} |"
        )
    return "\n".join(lines) + "\n"


def trim_run(result: dict[str, Any]) -> dict[str, Any]:
    """Shrink a saved run for use as a committed fixture: drop the bulky free text (Planner, Derive,
    review) and the iota script/stdout, keep candidates, checks, iota rows and criteria."""
    out = copy.deepcopy(result)

    def trim_artifacts(arts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        kept = []
        for a in arts:
            name, data = a["transform_name"], a["data"]
            if name in _DROP_TEXT and isinstance(data, dict):
                data = {k: v for k, v in data.items() if k != "response"}
            if name.startswith("iota_") and isinstance(data, dict):
                data = {k: v for k, v in data.items() if k not in ("script", "stdout")}
            kept.append({"transform_name": name, "data": data})
        return kept

    out["artifacts"] = trim_artifacts(out.get("artifacts", []))
    for r in out.get("rounds", []):
        r["artifacts"] = trim_artifacts(r["artifacts"])
    return out
