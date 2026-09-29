"""Single-round orchestrator for the `construct` pipeline (Phase 2).

Like local_pipeline.run_*, this walks a fixed DAG in Python: LLM nodes go to
the moonstar-rs gateway (one single-node session each, via
local_pipeline._submit_single_node); deterministic nodes run in-process.
`pipelines/construct.yaml` supplies per-node config only — no control flow.

Flow: Planner -> Derive_A/B -> Generator_A/B (formalise to JSON) -> (checks -> iota -> criteria) per candidate
-> if the best verdict is not NOT_FOUND: construct_critic ->
devils_advocate -> synthesizer. The verdict is computed by code; the
synthesizer's first line is overwritten to match. Multi-round feedback and
max_usd enforcement are Phase 3.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from ._compat import NonRetryableTransformError
from ._pipeline_spec import PipelineSpec, TransformSpec, render_pipeline_yaml
from .construct_spec import GATE_CHECKS, ConstructSpec, load_construct_spec
from .local_pipeline import (
    _CONSTRUCT_LOCAL_TRANSFORMS,
    _DUMMY_CTX,
    PipelineRunError,
    _submit_single_node,
)

_RANK = {"NOT_FOUND": 0, "PARTIAL": 1, "CONSTRUCTED": 2}
# Generators are long-reasoning calls; the shared 90-poll (180 s) ceiling is too short.
_LLM_MAX_POLLS = 600  # x _POLL_INTERVAL_SECONDS (2 s) = 20 min per LLM step
# Live run 2026-09-29: OpenRouter intermittently returns an undecodable body on long calls
# (gateway reports `failed`, no retry). One retry of a failed LLM step is cheap insurance.
_LLM_ATTEMPTS = 2


def _task_payload(spec: ConstructSpec) -> dict[str, Any]:
    return {
        "title": spec.title,
        "statement": spec.statement,
        "unknowns": list(spec.unknowns),
        "criteria": [
            {"id": c.id, "level": "hard" if c.hard else "soft", "check": c.check,
             "expr": c.expr, "kind": c.kind, "target": c.target, "note": c.note}
            for c in spec.criteria
        ],
        "degrees_of_freedom": [{"name": d.name, "range": [d.low, d.high]} for d in spec.degrees_of_freedom],
        "sample_box": {k: list(v) for k, v in spec.sample_box.items()},
        "mechanism_hints": list(spec.mechanism_hints),
    }


def _loads_lenient(raw: Any) -> Any:
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


def _parse_assignments(
    planner_data: dict[str, Any], spec: ConstructSpec
) -> tuple[dict[str, str], dict[str, str], bool]:
    plan = _loads_lenient(planner_data.get("response"))
    try:
        a, b = plan["generator_a"], plan["generator_b"]
        out = []
        for g in (a, b):
            mech, ansatz = g["mechanism"], g["ansatz"]
            if not (isinstance(mech, str) and isinstance(ansatz, str) and mech.strip()):
                raise KeyError
            out.append({"mechanism": mech, "ansatz": ansatz})
        return out[0], out[1], False
    except (TypeError, KeyError):
        hints = list(spec.mechanism_hints) or ["free choice"]
        first = {"mechanism": hints[0], "ansatz": ""}
        second = {"mechanism": hints[1 % len(hints)] if len(hints) > 1 else "an approach different from generator A",
                  "ansatz": ""}
        return first, second, True


def _enforce_verdict_line(text: str, verdict: str) -> str:
    line = f"VERDICT: {verdict}"
    stripped = (text or "").strip()
    if not stripped:
        return line
    first, _, rest = stripped.partition("\n")
    if first.strip().upper().startswith("VERDICT:"):
        return line + (("\n" + rest) if rest else "")
    return line + "\n\n" + stripped


def _not_found_row(error: str) -> dict[str, Any]:
    return {"verdict": "NOT_FOUND", "checklist": [], "unmet_hard": [], "unverified_hard": [], "error": error}


async def _evaluate_candidate(
    label: str, gen_name: str, nodes: dict[str, TransformSpec], spec_path: str,
    artifacts: dict[str, dict[str, Any]],
) -> None:
    """Runs checks -> iota -> criteria for one generator; a candidate the
    checkers cannot even read becomes NOT_FOUND instead of failing the run."""
    lo = label.lower()
    gen_input = {gen_name: artifacts[gen_name]}
    try:
        checks = await _CONSTRUCT_LOCAL_TRANSFORMS["VectorCalculusCheckTransform"](
            gen_input, {**nodes[f"checks_{lo}"].config, "spec_path": spec_path}, _DUMMY_CTX
        )
        artifacts[f"checks_{lo}"] = checks
        gate_ok = all(
            r["status"] == "pass" for r in checks["results"] if r.get("check") in GATE_CHECKS
        )
        if gate_ok:
            iota = await _CONSTRUCT_LOCAL_TRANSFORMS["IotaTraceTransform"](
                gen_input, {**nodes[f"iota_{lo}"].config, "spec_path": spec_path}, _DUMMY_CTX
            )
        else:
            iota = {"results": [], "skipped": "gate failed"}
        artifacts[f"iota_{lo}"] = iota
        artifacts[f"criteria_{lo}"] = await _CONSTRUCT_LOCAL_TRANSFORMS["ConstructCriteriaTransform"](
            {"checks": checks, "iota": iota},
            {**nodes[f"criteria_{lo}"].config, "spec_path": spec_path}, _DUMMY_CTX,
        )
    except NonRetryableTransformError as e:
        artifacts[f"criteria_{lo}"] = _not_found_row(str(e))


async def _run_round(
    client: httpx.AsyncClient, gateway_url: str, token: str, spec: ConstructSpec, spec_path: str,
    nodes: dict[str, TransformSpec], artifacts: dict[str, dict[str, Any]],
) -> tuple[str, str]:
    task = _task_payload(spec)

    async def llm(name: str, payload: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(_LLM_ATTEMPTS):
            try:
                artifacts[name] = await _submit_single_node(
                    client, gateway_url, token, nodes[name], payload, max_polls=_LLM_MAX_POLLS
                )
                return artifacts[name]
            except PipelineRunError:
                if attempt == _LLM_ATTEMPTS - 1:
                    raise
        raise AssertionError("unreachable")

    planner = await llm("Planner", {"task": task})
    assign_a, assign_b, fallback = _parse_assignments(planner, spec)
    if fallback:
        planner["planner_fallback"] = True

    # Two calls per candidate keep each under the gateway's LLM timeout: a long
    # reasoning "derive" step (free-form maths), then a cheap "formalise" step
    # that turns the derivation into the strict JSON the checkers read.
    # A candidate whose generation fails (e.g. the reasoning model burns its whole
    # budget) is NOT_FOUND for that candidate only; the run fails only if BOTH do.
    gen_errors: dict[str, PipelineRunError] = {}
    for label, assignment in (("A", assign_a), ("B", assign_b)):
        try:
            derive = await llm(f"Derive_{label}", {"task": task, "assignment": assignment})
            await llm(f"Generator_{label}", {
                "task": task, "assignment": assignment, "derivation": derive.get("response"),
            })
        except PipelineRunError as e:
            gen_errors[label] = e
            artifacts[f"criteria_{label.lower()}"] = _not_found_row(f"generation failed: {e}")
    if len(gen_errors) == 2:
        raise gen_errors["B"]
    for label in ("A", "B"):
        if label not in gen_errors:
            await _evaluate_candidate(label, f"Generator_{label}", nodes, spec_path, artifacts)

    verdicts = {l: artifacts[f"criteria_{l.lower()}"]["verdict"] for l in ("A", "B")}
    best = max(("A", "B"), key=lambda l: (_RANK[verdicts[l]], l == "A"))
    verdict = verdicts[best]
    if verdict == "NOT_FOUND":
        return verdict, best

    criteria = artifacts[f"criteria_{best.lower()}"]
    candidate = artifacts[f"Generator_{best}"].get("response")
    critic = await llm("construct_critic", {
        "task": task, "candidate": candidate, "criteria": criteria, "verdict": verdict,
    })
    devil = await llm("devils_advocate", {
        "construct_critic": critic, "candidate": candidate, "criteria": criteria, "verdict": verdict,
    })
    synth = await llm("synthesizer", {
        "task": task, "candidate": candidate, "criteria": criteria, "verdict": verdict,
        "construct_critic": critic, "devils_advocate": devil,
    })
    artifacts["synthesizer"] = {
        **synth, "response": _enforce_verdict_line(synth.get("response", ""), verdict),
    }
    return verdict, best


async def run_construct(
    spec_path: Any,
    gateway_url: str,
    token: str,
    pipeline_path: Path,
    models_path: Path,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    spec = load_construct_spec(spec_path)
    text = render_pipeline_yaml(pipeline_path, models_path)
    nodes = PipelineSpec.from_yaml_text(text).by_name()
    artifacts: dict[str, dict[str, Any]] = {}
    session_id = f"local-{uuid.uuid4().hex[:12]}"
    started = time.monotonic()

    def packed() -> list[dict[str, Any]]:
        return [{"transform_name": n, "data": d} for n, d in artifacts.items()]

    try:
        async with asyncio.timeout(spec.budget.get("max_wallclock_seconds")):
            async with httpx.AsyncClient(timeout=30.0, transport=transport) as client:
                verdict, best = await _run_round(
                    client, gateway_url, token, spec, str(spec_path), nodes, artifacts
                )
    except TimeoutError:
        error = f"wallclock budget of {spec.budget.get('max_wallclock_seconds')}s exceeded"
        return {"status": "failed", "session_id": session_id, "error": error, "artifacts": packed()}
    except (NonRetryableTransformError, PipelineRunError) as e:
        return {"status": "failed", "session_id": session_id, "error": str(e), "artifacts": packed()}

    return {
        "status": "completed", "session_id": session_id, "verdict": verdict,
        "best_candidate": best, "elapsed_seconds": round(time.monotonic() - started, 2),
        "artifacts": packed(),
    }
