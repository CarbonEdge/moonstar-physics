"""Bench core: pure summarise / aggregate / render, checked against a real committed run."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from moonstar_physics.construct_bench import (
    COST_LABEL, aggregate, render_report, summarise_run, trim_run, wilson,
)

_FIXTURE = Path(__file__).parent / "corpus" / "runs" / "mhd-v4pro-5round.json"


def _run() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_wilson_interval_known_values():
    lo, hi = wilson(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-3) and hi == pytest.approx(0.7634, abs=1e-3)
    assert wilson(0, 0) == (0.0, 1.0)
    lo, hi = wilson(0, 5)
    assert lo == 0.0 and 0.4 < hi < 0.5            # zero successes is not "0 %" with certainty
    lo, hi = wilson(5, 5)
    assert hi == 1.0 and lo > 0.5


def test_summarise_the_real_five_round_run():
    s = summarise_run(_run())
    assert s["status"] == "completed" and s["verdict"] == "PARTIAL"
    assert s["rounds"] == 5 and s["best_round"] == 5 and s["stop_reason"] == "max_rounds"
    assert s["final_unmet_hard"] == ["nonaxisym"]
    assert s["first_partial_round"] == 5 and s["first_constructed_round"] is None
    assert s["min_n_unmet"] == 1
    # best-candidate unmet counts per round are 3, 1, 2, 1, 1 -> exactly one regression (round 3)
    assert [p["best_n_unmet"] for p in s["per_round"]] == [3, 1, 2, 1, 1]
    assert s["regressions"] == 1
    assert s["cost_usd"] == pytest.approx(0.2996, abs=1e-3)


def test_failed_run_is_counted_not_dropped():
    s = summarise_run({"status": "failed", "error": "wallclock budget of 3600s exceeded"})
    assert s["status"] == "failed" and s["verdict"] is None and "wallclock" in s["error"]
    agg = aggregate([s, summarise_run(_run())])
    assert agg["n"] == 2 and agg["completed"] == 1 and agg["failed"] == 1
    assert agg["verdict_counts"] == {"CONSTRUCTED": 0, "PARTIAL": 1, "NOT_FOUND": 0}


def test_generation_failed_candidate_does_not_count_as_zero_unmet():
    run = _run()
    # pretend candidate B of round 1 failed generation: no n_unmet must be fabricated for it
    for a in run["rounds"][0]["artifacts"]:
        if a["transform_name"] == "criteria_b":
            a["data"] = {"verdict": "NOT_FOUND", "checklist": [], "unmet_hard": [], "unverified_hard": [],
                         "error": "generation failed: boom"}
    s = summarise_run(run)
    assert s["per_round"][0]["candidates"]["B"]["n_unmet"] is None


def test_aggregate_and_report_label_cost_provisional_and_warn_on_small_n():
    summaries = [summarise_run(_run()), summarise_run({"status": "failed", "error": "boom"})]
    agg = aggregate(summaries)
    text = render_report({"tag": "t", "spec": "mhd", "models": "v4-pro"}, agg, summaries)
    assert COST_LABEL in text                     # cost must never appear unlabelled
    assert "WARNING: N = 2 < 10" in text
    assert "| PARTIAL | 1 / 2 |" in text and "FAILED" in text
    assert agg["reached_le1_unmet"] == 1 and agg["min_unmet_histogram"] == {1: 1}
    assert agg["regressions_per_run"]["median"] == 1


def test_report_is_byte_stable():
    summaries = [summarise_run(_run())] * 3
    agg = aggregate(summaries)
    meta = {"tag": "t", "date": "2026-09-30"}
    assert render_report(meta, agg, summaries) == render_report(meta, agg, summaries)


def test_trim_run_drops_free_text_but_keeps_candidates_and_criteria():
    full = _run()
    full["rounds"][0]["artifacts"].append({"transform_name": "Derive_A", "data": {"response": "x" * 50_000, "_model": "m"}})
    full["rounds"][0]["artifacts"].append({"transform_name": "iota_a", "data": {"results": [], "script": "s", "stdout": "o"}})
    t = trim_run(full)
    by = {a["transform_name"]: a["data"] for a in t["rounds"][0]["artifacts"]}
    assert "response" not in by["Derive_A"] and by["Derive_A"]["_model"] == "m"
    assert "script" not in by["iota_a"] and "stdout" not in by["iota_a"]
    assert "response" in by["Generator_A"] and "verdict" in by["criteria_a"]
    assert "response" in {a["transform_name"]: a["data"] for a in full["rounds"][0]["artifacts"]}["Derive_A"]   # input untouched
