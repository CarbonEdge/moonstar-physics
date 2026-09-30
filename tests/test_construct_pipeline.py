"""Tests for construct_pipeline.run_construct - LLM nodes served by an
httpx.MockTransport standing in for moonstar-rs; deterministic nodes run for
real; the sandbox runs the generated script with the host interpreter."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import yaml

from moonstar_physics import construct_pipeline, iota_trace_transform, local_pipeline
from moonstar_physics.construct_pipeline import _enforce_verdict_line, run_construct
from moonstar_physics.construct_spec import load_construct_spec

from .iota_helpers import fake_sandbox

_ROOT = Path(__file__).parent.parent
_SPEC = _ROOT / "constructs" / "analytic-3d-mhd-equilibrium.yaml"
_PIPELINE = _ROOT / "pipelines" / "construct.yaml"
_MODELS = _ROOT / "pipelines" / "models.json"
_IOTA2 = (Path(__file__).parent / "fixtures" / "iota2_candidate.json").read_text(encoding="utf-8")
_BAD = json.dumps({"objects": {"B": ["x", "y", "z"], "psi": "x**2+y**2+z**2", "p": "1-psi"}})       # NOT_FOUND
_PARTIAL = json.dumps({"objects": {"B": ["-y", "x", "0"], "psi": "x**2+y**2", "p": "1-x**2-y**2"}})  # PARTIAL
_PLAN = json.dumps({
    "generator_a": {"mechanism": "axis torsion", "ansatz": "rotating ellipse"},
    "generator_b": {"mechanism": "axial current", "ansatz": "helical perturbation"},
    "target": "force_balance",
})
_FULL = {
    "Planner": [_PLAN], "Derive_A": ["derivation A"], "Derive_B": ["derivation B"],
    "Generator_A": [_IOTA2], "Generator_B": [_BAD],
    "construct_critic": [json.dumps({"concerns": [], "unverified_assessment": "ok", "looks_trivial": False})],
    "devils_advocate": [json.dumps({"strongest_objection": "integer iota", "known_solution_risk": "possible",
                                    "unmet_or_unverified": ["iota_noninteger"]})],
    "synthesizer": ["VERDICT: PLAUSIBLE\n\nLooks great, truly novel."],
}


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(local_pipeline, "_POLL_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(iota_trace_transform, "_run_sandbox", fake_sandbox)


def _gateway(script: dict[str, list[str]], seen: list[dict], fail: dict[str, set[int]] | None = None,
             model: str = "deepseek/deepseek-v4-pro", tokens: tuple[int, int] = (10, 20),
             reported_cost: float | None = None):
    """script: node -> responses consumed per call (the last one repeats).
    fail: node -> set of 1-based call numbers that fail at the gateway."""
    fail = fail or {}
    calls: dict[str, int] = {}
    sessions: dict[str, tuple[str, int]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/pipelines/run":
            body = json.loads(request.content)
            node = yaml.safe_load(body["yaml_spec"])["transforms"][0]["name"]
            calls[node] = calls.get(node, 0) + 1
            seen.append({"node": node, "call": calls[node], "initial_input": body["initial_input"]})
            sid = f"sess-{node}-{calls[node]}"
            sessions[sid] = (node, calls[node])
            return httpx.Response(200, json={"session_id": sid})
        if request.url.path.startswith("/sessions/"):
            node, n = sessions[request.url.path.rsplit("/", 1)[-1]]
            if n in fail.get(node, set()):
                return httpx.Response(200, json={"status": "failed", "artifacts": []})
            responses = script[node]
            text = responses[min(n, len(responses)) - 1]
            return httpx.Response(200, json={
                "status": "completed",
                "artifacts": [{"transform_name": node, "data": {
                    "response": text, "_model": model,
                    "_input_tokens": tokens[0], "_output_tokens": tokens[1],
                    **({"_cost_usd": reported_cost} if reported_cost is not None else {})}}],
            })
        raise AssertionError(f"unexpected request {request.method} {request.url}")

    return httpx.MockTransport(handler)


def _run(script, seen, *, max_rounds=1, spec=_SPEC, **gw):
    return run_construct(spec, "http://gateway.test", "tok", _PIPELINE, _MODELS,
                         transport=_gateway(script, seen, **gw), max_rounds=max_rounds)


def _by_name(artifacts):
    return {a["transform_name"]: a["data"] for a in artifacts}


def _req(seen, node, call=1):
    return next(r["initial_input"] for r in seen if r["node"] == node and r["call"] == call)


def _names(seen):
    return [r["node"] for r in seen]


def _spec_with_budget(tmp_path, **budget):
    data = yaml.safe_load(_SPEC.read_text(encoding="utf-8"))
    data["budget"] = {**data["budget"], **budget}
    p = tmp_path / "spec.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    return p


async def test_single_round_constructed_and_verdict_line_is_enforced():
    seen: list[dict] = []
    result = await _run(_FULL, seen)
    assert result["status"] == "completed" and result["stop_reason"] == "constructed"
    assert result["verdict"] == "CONSTRUCTED" and result["best_candidate"] == "A" and result["best_round"] == 1
    names = _names(seen)
    assert names[0] == "Planner" and names[-3:] == ["construct_critic", "devils_advocate", "synthesizer"]
    assert names.index("Derive_A") < names.index("Generator_A") and names.index("Derive_B") < names.index("Generator_B")
    by = _by_name(result["artifacts"])
    assert by["criteria_a"]["verdict"] == "CONSTRUCTED" and by["criteria_b"]["verdict"] == "NOT_FOUND"
    assert by["synthesizer"]["response"].splitlines()[0] == "VERDICT: CONSTRUCTED"
    assert _req(seen, "Derive_A")["assignment"]["mechanism"] == "axis torsion"
    assert _req(seen, "Derive_B")["assignment"]["mechanism"] == "axial current"
    assert _req(seen, "Generator_A")["derivation"] == "derivation A"
    assert _req(seen, "Generator_B")["derivation"] == "derivation B"
    assert _req(seen, "construct_critic")["criteria"]["verdict"] == "CONSTRUCTED"
    assert _req(seen, "Planner")["history"] == [] and "feedback" not in _req(seen, "Derive_A")


async def test_candidates_are_generated_concurrently():
    seen: list[dict] = []
    await _run(_FULL, seen)
    names = _names(seen)
    assert names.index("Derive_B") < names.index("Generator_A")      # B started before A finished


async def test_both_candidates_fail_gate_skips_review_and_sandbox(monkeypatch):
    async def boom(script, timeout_seconds):
        raise AssertionError("sandbox must not run when the symbolic gate failed")

    monkeypatch.setattr(iota_trace_transform, "_run_sandbox", boom)
    seen: list[dict] = []
    result = await _run({**_FULL, "Generator_A": [_BAD]}, seen)
    assert result["status"] == "completed" and result["verdict"] == "NOT_FOUND"
    assert "construct_critic" not in _names(seen) and "synthesizer" not in _by_name(result["artifacts"])
    assert _by_name(result["artifacts"])["iota_a"]["skipped"] == "gate failed"


async def test_invalid_generator_json_is_not_found_for_that_candidate_only():
    seen: list[dict] = []
    result = await _run({**_FULL, "Generator_B": ["sorry, some prose"]}, seen)
    by = _by_name(result["artifacts"])
    assert by["criteria_b"]["verdict"] == "NOT_FOUND" and "error" in by["criteria_b"]
    assert result["verdict"] == "CONSTRUCTED"


async def test_unparseable_plan_falls_back_to_spec_mechanism_hints():
    seen: list[dict] = []
    result = await _run({**_FULL, "Planner": ["not json at all"]}, seen)
    hints = load_construct_spec(_SPEC).mechanism_hints
    assert _req(seen, "Derive_A")["assignment"]["mechanism"] == hints[0]
    assert _req(seen, "Derive_B")["assignment"]["mechanism"] == hints[1]
    assert _by_name(result["artifacts"])["Planner"].get("planner_fallback") is True


async def test_planner_failure_in_round_one_fails_the_run():
    seen: list[dict] = []
    result = await _run(_FULL, seen, fail={"Planner": {1, 2}})
    assert result["status"] == "failed" and "Planner" in result["error"]
    assert result["artifacts"] == []


async def test_one_candidates_generation_failure_only_sinks_that_candidate():
    seen: list[dict] = []
    result = await _run(_FULL, seen, fail={"Derive_B": {1, 2}})
    assert result["status"] == "completed" and result["verdict"] == "CONSTRUCTED"
    by = _by_name(result["artifacts"])
    assert by["criteria_b"]["verdict"] == "NOT_FOUND" and "generation failed" in by["criteria_b"]["error"]
    assert "Derive_B" not in by and "Generator_B" not in by
    assert "Generator_A" in by                                        # the other candidate was not cancelled


async def test_both_candidates_failing_generation_fails_the_run():
    seen: list[dict] = []
    result = await _run(_FULL, seen, fail={"Derive_A": {1, 2}, "Derive_B": {1, 2}})
    assert result["status"] == "failed" and "Derive_B" in result["error"]


async def test_failed_llm_step_is_retried_once_then_succeeds():
    seen: list[dict] = []
    result = await _run(_FULL, seen, fail={"Planner": {1}})
    assert result["status"] == "completed" and result["verdict"] == "CONSTRUCTED"
    assert [r["call"] for r in seen if r["node"] == "Planner"] == [1, 2]


async def test_repair_round_gets_history_feedback_and_a_new_seed():
    script = {**_FULL, "Generator_A": [_BAD, _IOTA2], "Generator_B": [_BAD]}
    seen: list[dict] = []
    result = await _run(script, seen, max_rounds=3)
    assert result["stop_reason"] == "constructed" and len(result["rounds"]) == 2
    assert [r["verdict"] for r in result["rounds"]] == ["NOT_FOUND", "CONSTRUCTED"]
    assert result["best_round"] == 2
    hist = _req(seen, "Planner", call=2)["history"]
    assert len(hist) == 1 and hist[0]["round"] == 1
    assert all("candidate" not in c for c in hist[0]["candidates"].values())      # stripped for the planner
    fb = _req(seen, "Derive_A", call=2)["feedback"]
    assert fb["previous_best"] and fb["unmet_hard"] and "force_balance" in fb["evidence"]
    assert "feedback" not in _req(seen, "Derive_A", call=1)
    r1 = _by_name(result["rounds"][0]["artifacts"])
    r2 = _by_name(result["rounds"][1]["artifacts"])
    assert r1["checks_a"]["seed"] == 1 and r2["checks_a"]["seed"] == 2
    assert _names(seen).count("construct_critic") == 1                            # review runs once, at the end


async def test_worse_later_round_does_not_replace_the_best_round():
    script = {**_FULL, "Generator_A": [_PARTIAL, _BAD], "Generator_B": [_PARTIAL, _BAD]}
    seen: list[dict] = []
    result = await _run(script, seen, max_rounds=2)
    assert [r["verdict"] for r in result["rounds"]] == ["PARTIAL", "NOT_FOUND"]
    assert result["verdict"] == "PARTIAL" and result["best_round"] == 1
    assert result["stop_reason"] == "max_rounds"
    assert "synthesizer" in _by_name(result["artifacts"])                           # reviewed the best (round 1)
    assert _by_name(result["artifacts"])["synthesizer"]["response"].splitlines()[0] == "VERDICT: PARTIAL"


async def test_max_rounds_without_success_skips_review():
    script = {**_FULL, "Generator_A": [_BAD], "Generator_B": [_BAD]}
    seen: list[dict] = []
    result = await _run(script, seen, max_rounds=2)
    assert len(result["rounds"]) == 2 and result["stop_reason"] == "max_rounds"
    assert result["verdict"] == "NOT_FOUND" and "construct_critic" not in _names(seen)


async def test_max_usd_stops_at_the_round_boundary(tmp_path):
    spec = _spec_with_budget(tmp_path, max_usd=0.01, max_rounds=3)
    script = {**_FULL, "Generator_A": [_BAD], "Generator_B": [_BAD]}
    seen: list[dict] = []
    result = await _run(script, seen, max_rounds=3, spec=spec, tokens=(1_000_000, 1_000_000))
    assert result["stop_reason"] == "max_usd" and len(result["rounds"]) == 1
    assert result["cost_usd"] > 0.01 and result["rounds"][0]["cost_usd"] > 0.01
    assert result["token_usage"]["deepseek/deepseek-v4-pro"]["input_tokens"] > 0


async def test_unpriced_model_is_reported():
    seen: list[dict] = []
    result = await _run(_FULL, seen, model="mystery/model")
    assert result["unpriced_models"] == ["mystery/model"] and result["cost_usd"] == 0.0


async def test_round_two_failure_keeps_completed_rounds():
    script = {**_FULL, "Generator_A": [_BAD], "Generator_B": [_BAD]}
    seen: list[dict] = []
    result = await _run(script, seen, max_rounds=3, fail={"Planner": {2, 3}})
    assert result["status"] == "completed" and len(result["rounds"]) == 1
    assert result["stop_reason"].startswith("round_failed") and result["verdict"] == "NOT_FOUND"


async def test_wallclock_budget_before_any_round_fails_fast(monkeypatch, tmp_path):
    spec = _spec_with_budget(tmp_path, max_wallclock_seconds=0.0001)
    monkeypatch.setattr(local_pipeline, "_POLL_INTERVAL_SECONDS", 0.05)
    result = await _run(_FULL, [], spec=spec)
    assert result["status"] == "failed" and "wallclock" in result["error"]


def test_llm_polling_ceiling_exceeds_the_shared_default():
    assert construct_pipeline._LLM_MAX_POLLS > local_pipeline._MAX_POLLS


@pytest.mark.parametrize("text,expected", [
    ("VERDICT: PLAUSIBLE\n\nbody", "VERDICT: PARTIAL\n\nbody"),
    ("VERDICT: PARTIAL\n\nbody", "VERDICT: PARTIAL\n\nbody"),
    ("no verdict line\nbody", "VERDICT: PARTIAL\n\nno verdict line\nbody"),
    ("", "VERDICT: PARTIAL"),
])
def test_enforce_verdict_line(text, expected):
    assert _enforce_verdict_line(text, "PARTIAL") == expected


async def test_reported_gateway_cost_makes_the_run_cost_exact():
    seen: list[dict] = []
    transport = _gateway(_FULL, seen, reported_cost=0.01)
    result = await run_construct(_SPEC, "http://gateway.test", "tok", _PIPELINE, _MODELS,
                                 transport=transport, max_rounds=1)
    llm_calls = len(seen)                                   # every LLM call carried _cost_usd = 0.01
    assert result["cost_is_exact"] is True
    assert result["cost_usd"] == pytest.approx(0.01 * llm_calls)
    assert result["cost_reported_usd"] == pytest.approx(result["cost_usd"]) and result["cost_estimated_usd"] == 0.0


async def test_no_reported_cost_falls_back_to_the_estimate_and_is_flagged():
    seen: list[dict] = []
    result = await _run(_FULL, seen)
    assert result["cost_is_exact"] is False and result["cost_reported_usd"] == 0.0
    assert result["cost_estimated_usd"] == pytest.approx(result["cost_usd"]) and result["cost_usd"] > 0
