"""Tests for construct_pipeline.run_construct — LLM nodes served by an
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
# Axisymmetric relabel: passes div/flux, fails nonaxisym -> PARTIAL at best; here NOT_FOUND-ish.
_BAD = json.dumps({"objects": {"B": ["x", "y", "z"], "psi": "x**2+y**2+z**2", "p": "1-psi"}})  # div B = 3

_PLAN = json.dumps({
    "generator_a": {"mechanism": "axis torsion", "ansatz": "rotating ellipse"},
    "generator_b": {"mechanism": "axial current", "ansatz": "helical perturbation"},
    "target": "force_balance",
})


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(local_pipeline, "_POLL_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(iota_trace_transform, "_run_sandbox", fake_sandbox)


def _gateway(responses: dict[str, str], seen: list[dict], fail_node: str | None = None):
    sessions: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/pipelines/run":
            body = json.loads(request.content)
            node = yaml.safe_load(body["yaml_spec"])["transforms"][0]["name"]
            seen.append({"node": node, "initial_input": body["initial_input"]})
            sessions[f"sess-{node}"] = node
            return httpx.Response(200, json={"session_id": f"sess-{node}"})
        if request.url.path.startswith("/sessions/"):
            node = sessions[request.url.path.rsplit("/", 1)[-1]]
            if node == fail_node:
                return httpx.Response(200, json={"status": "failed", "artifacts": []})
            return httpx.Response(200, json={
                "status": "completed",
                "artifacts": [{"transform_name": node, "data": {"response": responses[node]}}],
            })
        raise AssertionError(f"unexpected request {request.method} {request.url}")

    return httpx.MockTransport(handler)


def _run(responses, seen, **kw):
    return run_construct(_SPEC, "http://gateway.test", "tok", _PIPELINE, _MODELS,
                         transport=_gateway(responses, seen, **kw))


def _by_name(result):
    return {a["transform_name"]: a["data"] for a in result["artifacts"]}


_FULL = {
    "Planner": _PLAN, "Generator_A": _IOTA2, "Generator_B": _BAD,
    "construct_critic": json.dumps({"concerns": [], "unverified_assessment": "ok", "looks_trivial": False}),
    "devils_advocate": json.dumps({"strongest_objection": "integer iota", "known_solution_risk": "possible",
                                   "unmet_or_unverified": ["iota_noninteger"]}),
    "synthesizer": "VERDICT: PLAUSIBLE\n\nLooks great, truly novel.",
}


async def test_full_round_constructed_and_verdict_line_is_enforced():
    seen: list[dict] = []
    result = await _run(_FULL, seen)
    assert result["status"] == "completed"
    assert result["verdict"] == "CONSTRUCTED" and result["best_candidate"] == "A"
    assert [r["node"] for r in seen] == [
        "Planner", "Generator_A", "Generator_B", "construct_critic", "devils_advocate", "synthesizer",
    ]
    by = _by_name(result)
    assert by["criteria_a"]["verdict"] == "CONSTRUCTED"
    assert by["criteria_b"]["verdict"] == "NOT_FOUND"
    assert by["synthesizer"]["response"].splitlines()[0] == "VERDICT: CONSTRUCTED"   # LLM said PLAUSIBLE
    # Generators received their own planner assignment.
    assert seen[1]["initial_input"]["assignment"]["mechanism"] == "axis torsion"
    assert seen[2]["initial_input"]["assignment"]["mechanism"] == "axial current"
    # Critic sees the winning candidate + its checklist, not the losing one.
    assert seen[3]["initial_input"]["criteria"]["verdict"] == "CONSTRUCTED"


async def test_both_candidates_fail_gate_skips_llm_review_and_sandbox(monkeypatch):
    async def boom(script, timeout_seconds):
        raise AssertionError("sandbox must not run when the symbolic gate failed")

    monkeypatch.setattr(iota_trace_transform, "_run_sandbox", boom)
    seen: list[dict] = []
    result = await _run({**_FULL, "Generator_A": _BAD}, seen)
    assert result["status"] == "completed" and result["verdict"] == "NOT_FOUND"
    assert [r["node"] for r in seen] == ["Planner", "Generator_A", "Generator_B"]
    by = _by_name(result)
    assert "synthesizer" not in by and "construct_critic" not in by
    assert by["iota_a"]["skipped"] == "gate failed"


async def test_invalid_generator_json_is_not_found_for_that_candidate_only():
    seen: list[dict] = []
    result = await _run({**_FULL, "Generator_B": "sorry, here's some prose"}, seen)
    by = _by_name(result)
    assert by["criteria_b"]["verdict"] == "NOT_FOUND" and "error" in by["criteria_b"]
    assert result["verdict"] == "CONSTRUCTED"


async def test_unparseable_plan_falls_back_to_spec_mechanism_hints():
    seen: list[dict] = []
    result = await _run({**_FULL, "Planner": "not json at all"}, seen)
    hints = load_construct_spec(_SPEC).mechanism_hints
    assert seen[1]["initial_input"]["assignment"]["mechanism"] == hints[0]
    assert seen[2]["initial_input"]["assignment"]["mechanism"] == hints[1]
    assert _by_name(result)["Planner"].get("planner_fallback") is True


async def test_gateway_failure_returns_failed_with_partial_artifacts():
    seen: list[dict] = []
    result = await _run(_FULL, seen, fail_node="Generator_B")
    assert result["status"] == "failed" and "Generator_B" in result["error"]
    by = _by_name(result)
    assert "Planner" in by and "Generator_A" in by and "Generator_B" not in by


async def test_wallclock_budget_zero_fails_fast(monkeypatch, tmp_path):
    spec = yaml.safe_load(_SPEC.read_text(encoding="utf-8"))
    spec["budget"]["max_wallclock_seconds"] = 0.0001
    p = tmp_path / "spec.yaml"
    p.write_text(yaml.safe_dump(spec), encoding="utf-8")
    monkeypatch.setattr(local_pipeline, "_POLL_INTERVAL_SECONDS", 0.05)
    result = await run_construct(p, "http://gateway.test", "tok", _PIPELINE, _MODELS,
                                 transport=_gateway(_FULL, []))
    assert result["status"] == "failed" and "wallclock" in result["error"]


@pytest.mark.parametrize("text,expected", [
    ("VERDICT: PLAUSIBLE\n\nbody", "VERDICT: PARTIAL\n\nbody"),
    ("VERDICT: PARTIAL\n\nbody", "VERDICT: PARTIAL\n\nbody"),
    ("no verdict line\nbody", "VERDICT: PARTIAL\n\nno verdict line\nbody"),
    ("", "VERDICT: PARTIAL"),
])
def test_enforce_verdict_line(text, expected):
    assert _enforce_verdict_line(text, "PARTIAL") == expected