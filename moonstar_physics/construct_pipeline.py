"""Multi-round orchestrator for the `construct` pipeline (Phase 3).

Each round: Planner -> per candidate (concurrently) Derive (long reasoning)
-> Generator (formalise to strict JSON) -> deterministic checks -> iota trace
-> criteria. Round n checks with seed n. After a round that is not
CONSTRUCTED, the best candidate so far and its evidence are fed back (to the
Planner as a stripped history, to Derive as `feedback`) for a minimal repair.
Stop: CONSTRUCTED, max_rounds, max_usd (checked at round boundaries), or the
wallclock budget. The LLM review (critic -> devil's advocate -> synthesizer)
runs once, on the best candidate, if it is not NOT_FOUND. The verdict is
computed by code; the synthesizer's first line is overwritten to match.
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
from .construct_cost import load_prices, run_cost_breakdown, run_cost_usd, usage_by_model
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
_HISTORY_ROUNDS = 2
_DEFAULT_PRICES_PATH = Path(__file__).resolve().parent.parent / "pipelines" / "prices.json"


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
    artifacts: dict[str, dict[str, Any]], seed: int,
) -> None:
    """Runs checks -> iota -> criteria for one generator; a candidate the
    checkers cannot even read becomes NOT_FOUND instead of failing the run."""
    lo = label.lower()
    gen_input = {gen_name: artifacts[gen_name]}
    try:
        checks = await _CONSTRUCT_LOCAL_TRANSFORMS["VectorCalculusCheckTransform"](
            gen_input,
            {**nodes[f"checks_{lo}"].config, "spec_path": spec_path, "seed": seed},
            _DUMMY_CTX,
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


def _packed(artifacts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"transform_name": n, "data": d} for n, d in artifacts.items()]


def _evidence(criteria: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in criteria.get("checklist", []):
        ev = row.get("evidence") or {}
        entry: dict[str, Any] = {"status": row.get("status"), "hard": row.get("hard")}
        for key in ("max_residual", "value", "iota", "detail"):
            if ev.get(key) is not None:
                entry[key] = ev[key]
        out[row["id"]] = entry
    return out


def _candidate_summary(label: str, artifacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    crit = artifacts.get(f"criteria_{label.lower()}", {})
    parsed = _loads_lenient(artifacts.get(f"Generator_{label}", {}).get("response"))
    parsed = parsed if isinstance(parsed, dict) else {}
    return {
        "verdict": crit.get("verdict", "NOT_FOUND"),
        "unmet_hard": list(crit.get("unmet_hard", [])),
        "unverified_hard": list(crit.get("unverified_hard", [])),
        "evidence": _evidence(crit),
        "candidate": {k: parsed[k] for k in ("defs", "objects", "params") if k in parsed},
        "derivation_notes": parsed.get("derivation_notes", ""),
        "error": crit.get("error"),
    }


def _round_summary(
    round_no: int, verdict: str, best: str, artifacts: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    return {
        "round": round_no, "verdict": verdict, "best_candidate": best,
        "candidates": {l: _candidate_summary(l, artifacts) for l in ("A", "B")},
    }


def _round_score(h: dict[str, Any]) -> tuple[int, int, int]:
    best = h["candidates"][h["best_candidate"]]
    return (_RANK[h["verdict"]], -len(best["unmet_hard"]), h["round"])


def _feedback(history: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The best candidate seen so far (by verdict, then fewest unmet hard
    criteria, then latest) with its evidence, as the repair target."""
    best: tuple[tuple[int, int, int], int, str, dict[str, Any]] | None = None
    for h in history:
        for label, c in h["candidates"].items():
            if not c["candidate"]:
                continue
            score = (_RANK[c["verdict"]], -len(c["unmet_hard"]), h["round"])
            if best is None or score > best[0]:
                best = (score, h["round"], label, c)
    if best is None:
        return None
    _, rnd, label, c = best
    return {
        "from_round": rnd, "from_candidate": label, "previous_best": c["candidate"],
        "evidence": c["evidence"], "unmet_hard": c["unmet_hard"],
        "unverified_hard": c["unverified_hard"], "derivation_notes": c["derivation_notes"],
    }


def _planner_view(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "round": h["round"], "verdict": h["verdict"], "best_candidate": h["best_candidate"],
            "candidates": {
                l: {k: v for k, v in c.items() if k != "candidate"}
                for l, c in h["candidates"].items()
            },
        }
        for h in history[-_HISTORY_ROUNDS:]
    ]


def _make_llm(client, gateway_url, token, nodes, store):
    async def llm(name: str, payload: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(_LLM_ATTEMPTS):
            try:
                store[name] = await _submit_single_node(
                    client, gateway_url, token, nodes[name], payload, max_polls=_LLM_MAX_POLLS
                )
                return store[name]
            except PipelineRunError:
                if attempt == _LLM_ATTEMPTS - 1:
                    raise
        raise AssertionError("unreachable")

    return llm


async def _run_round(
    client: httpx.AsyncClient, gateway_url: str, token: str, spec: ConstructSpec, spec_path: str,
    nodes: dict[str, TransformSpec], artifacts: dict[str, dict[str, Any]],
    round_no: int, history: list[dict[str, Any]],
) -> tuple[str, str]:
    task = _task_payload(spec)
    feedback = _feedback(history)
    llm = _make_llm(client, gateway_url, token, nodes, artifacts)

    planner = await llm("Planner", {"task": task, "history": _planner_view(history)})
    assign_a, assign_b, fallback = _parse_assignments(planner, spec)
    if fallback:
        planner["planner_fallback"] = True

    async def generate(label: str, assignment: dict[str, str]) -> None:
        # Two calls per candidate keep each under the gateway's LLM timeout: a long
        # reasoning "derive" step, then a cheap "formalise" step that emits strict JSON.
        derive_input: dict[str, Any] = {"task": task, "assignment": assignment}
        if feedback:
            derive_input["feedback"] = feedback
        derive = await llm(f"Derive_{label}", derive_input)
        await llm(f"Generator_{label}", {
            "task": task, "assignment": assignment, "derivation": derive.get("response"),
        })

    # Candidates run concurrently. A candidate whose generation fails is NOT_FOUND
    # alone; the run fails only if BOTH do.
    results = await asyncio.gather(
        generate("A", assign_a), generate("B", assign_b), return_exceptions=True
    )
    gen_errors: dict[str, PipelineRunError] = {}
    for label, res in zip(("A", "B"), results):
        if isinstance(res, PipelineRunError):
            gen_errors[label] = res
            artifacts[f"criteria_{label.lower()}"] = _not_found_row(f"generation failed: {res}")
        elif isinstance(res, BaseException):
            raise res
    if len(gen_errors) == 2:
        raise gen_errors["B"]
    for label in ("A", "B"):
        if label not in gen_errors:
            await _evaluate_candidate(
                label, f"Generator_{label}", nodes, spec_path, artifacts, seed=round_no
            )

    verdicts = {l: artifacts[f"criteria_{l.lower()}"]["verdict"] for l in ("A", "B")}
    best = max(
        ("A", "B"),
        key=lambda l: (
            _RANK[verdicts[l]],
            -len(artifacts[f"criteria_{l.lower()}"].get("unmet_hard", [])),
            l == "A",
        ),
    )
    return verdicts[best], best


async def _review(
    client: httpx.AsyncClient, gateway_url: str, token: str, spec: ConstructSpec,
    nodes: dict[str, TransformSpec], best_artifacts: dict[str, dict[str, Any]],
    best_label: str, verdict: str, store: dict[str, dict[str, Any]],
) -> None:
    task = _task_payload(spec)
    llm = _make_llm(client, gateway_url, token, nodes, store)
    criteria = best_artifacts[f"criteria_{best_label.lower()}"]
    candidate = best_artifacts[f"Generator_{best_label}"].get("response")
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
    store["synthesizer"] = {
        **synth, "response": _enforce_verdict_line(synth.get("response", ""), verdict),
    }


async def run_construct(
    spec_path: Any,
    gateway_url: str,
    token: str,
    pipeline_path: Path,
    models_path: Path,
    transport: httpx.BaseTransport | None = None,
    *,
    max_rounds: int | None = None,
    prices_path: Any = None,
) -> dict[str, Any]:
    spec = load_construct_spec(spec_path)
    text = render_pipeline_yaml(pipeline_path, models_path)
    nodes = PipelineSpec.from_yaml_text(text).by_name()
    prices = load_prices(prices_path or _DEFAULT_PRICES_PATH)
    rounds_limit = max(1, max_rounds if max_rounds is not None else int(spec.budget.get("max_rounds", 1)))
    max_usd = spec.budget.get("max_usd")
    wallclock = spec.budget.get("max_wallclock_seconds")
    session_id = f"local-{uuid.uuid4().hex[:12]}"
    started = time.monotonic()

    rounds: list[dict[str, Any]] = []
    raw: dict[int, dict[str, dict[str, Any]]] = {}
    history: list[dict[str, Any]] = []
    review: dict[str, dict[str, Any]] = {}
    current: dict[str, dict[str, Any]] = {}
    stop_reason = "max_rounds"

    def failed(error: str) -> dict[str, Any]:
        return {"status": "failed", "session_id": session_id, "error": error,
                "artifacts": _packed(current)}

    try:
        async with asyncio.timeout(wallclock):
            async with httpx.AsyncClient(timeout=30.0, transport=transport) as client:
                for n in range(1, rounds_limit + 1):
                    current = {}
                    try:
                        verdict, best = await _run_round(
                            client, gateway_url, token, spec, str(spec_path), nodes,
                            current, n, history,
                        )
                    except (NonRetryableTransformError, PipelineRunError) as e:
                        if not rounds:
                            raise
                        stop_reason = f"round_failed: {e}"
                        break
                    raw[n] = current
                    cost, _ = run_cost_usd(current.values(), prices)
                    rounds.append({"round": n, "verdict": verdict, "best_candidate": best,
                                   "cost_usd": cost, "artifacts": _packed(current)})
                    history.append(_round_summary(n, verdict, best, current))
                    if verdict == "CONSTRUCTED":
                        stop_reason = "constructed"
                        break
                    if max_usd is not None and sum(r["cost_usd"] for r in rounds) >= float(max_usd):
                        stop_reason = "max_usd"
                        break
                best_h = max(history, key=_round_score)
                if best_h["verdict"] != "NOT_FOUND":
                    try:
                        await _review(
                            client, gateway_url, token, spec, nodes, raw[best_h["round"]],
                            best_h["best_candidate"], best_h["verdict"], review,
                        )
                    except PipelineRunError as e:
                        review["review_error"] = {"error": str(e)}
    except TimeoutError:
        if not rounds:
            return failed(f"wallclock budget of {wallclock}s exceeded")
        stop_reason = "wallclock"
    except (NonRetryableTransformError, PipelineRunError) as e:
        return failed(str(e))

    best_h = max(history, key=_round_score)
    all_datas = [d for r in raw.values() for d in r.values()] + list(review.values())
    cost = run_cost_breakdown(all_datas, prices)
    return {
        "status": "completed", "session_id": session_id, "verdict": best_h["verdict"],
        "best_candidate": best_h["best_candidate"], "best_round": best_h["round"],
        "stop_reason": stop_reason, "rounds": rounds, "cost_usd": cost["total_usd"],
        "cost_reported_usd": cost["reported_usd"], "cost_estimated_usd": cost["estimated_usd"],
        "cost_truncated_usd": cost["truncated_usd"], "cost_is_exact": cost["is_exact"],
        "unpriced_models": cost["unpriced_models"], "token_usage": usage_by_model(all_datas),
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "artifacts": _packed(raw[best_h["round"]]) + _packed(review),
    }
