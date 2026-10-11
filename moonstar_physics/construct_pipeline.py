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
import copy
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from ._compat import NonRetryableTransformError
from ._pipeline_spec import PipelineSpec, TransformSpec, render_pipeline_yaml
from .construct_cost import load_prices, run_cost_breakdown, run_cost_usd, usage_by_model
from .construct_diagnose import family_tags
from .construct_history import (  # noqa: F401 - re-exported: tests and scripts import these names here
    _DIAG_MAX_CHARS, _RANK, _loads_lenient, _cand_score, _candidate_summary, _cap_diagnostics, _evidence, _feedback,
    _hard_met, _planner_view, _round_score, _round_summary,
)
from .construct_residuals import diagnose_with_timeout
from .construct_spec import GATE_CHECKS, ConstructSpec, load_construct_spec
from .local_pipeline import (
    _CONSTRUCT_LOCAL_TRANSFORMS,
    _DUMMY_CTX,
    PipelineRunError,
    _submit_single_node,
)

# Generators are long-reasoning calls; the shared 90-poll (180 s) ceiling is too short.
_LLM_MAX_POLLS = 600  # x _POLL_INTERVAL_SECONDS (2 s) = 20 min per LLM step
# Live run 2026-09-29: OpenRouter intermittently returns an undecodable body on long calls
# (gateway reports `failed`, no retry). One retry of a failed LLM step is cheap insurance.
_LLM_ATTEMPTS = 2
_LABELS = "ABCDEF"
_MAX_CANDIDATES = len(_LABELS)
# Candidates generated at once. The gateway itself allows far more (MAX_GLOBAL_TRANSFORMS=20,
# MAX_SESSION_PARALLELISM=4, OPENROUTER_MAX_INFLIGHT=20 by default); 2 is the pace live runs
# showed to be safe with the provider. Raise it with CONSTRUCT_MAX_CONCURRENT after measuring.
_MAX_CONCURRENT_CANDIDATES = max(1, int(os.environ.get("CONSTRUCT_MAX_CONCURRENT", "2")))
_REPAIR_MODEL_KEY = "MODEL_REPAIR"
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


def _parse_assignments(
    planner_data: dict[str, Any], spec: ConstructSpec, labels: tuple[str, ...] = ("A", "B")
) -> tuple[dict[str, dict[str, str]], bool]:
    """label -> {"mechanism", "ansatz"} from the planner's generator_<letter> entries; any
    label the planner did not (validly) assign falls back to the spec's mechanism hints."""
    plan = _loads_lenient(planner_data.get("response"))
    plan = plan if isinstance(plan, dict) else {}
    hints = list(spec.mechanism_hints) or ["free choice"]
    out: dict[str, dict[str, str]] = {}
    fallback = False
    for i, label in enumerate(labels):
        g = plan.get(f"generator_{label.lower()}")
        if (isinstance(g, dict) and isinstance(g.get("mechanism"), str) and g["mechanism"].strip()
                and isinstance(g.get("ansatz"), str)):
            out[label] = {"mechanism": g["mechanism"], "ansatz": g["ansatz"]}
            continue
        fallback = True
        mech = hints[i % len(hints)] if (i == 0 or len(hints) > 1) else "an approach different from generator A"
        out[label] = {"mechanism": mech, "ansatz": ""}
    return out, fallback


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
        if not gate_ok:
            await _attach_diagnostics(lo, gen_input[gen_name], checks, spec_path, artifacts)
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


async def _attach_diagnostics(
    lo: str, generator: dict[str, Any], checks: dict[str, Any], spec_path: str,
    artifacts: dict[str, dict[str, Any]],
) -> None:
    """Symbolic/point residual diagnostics for the failed gates (P4.3). Best effort."""
    candidate = _loads_lenient(generator.get("response"))
    failed = [r["id"] for r in checks["results"] if r.get("check") in GATE_CHECKS and r["status"] == "fail"]
    if not isinstance(candidate, dict) or not failed:
        return
    try:
        diag = await asyncio.to_thread(diagnose_with_timeout, str(spec_path), candidate, failed)
    except Exception:  # noqa: BLE001 - diagnostics must never sink a candidate
        return
    if diag:
        artifacts[f"diag_{lo}"] = {
            "diagnostics": diag, "_model": "none", "_provider": "none",
            "_input_tokens": 0, "_output_tokens": 0,
        }


def _packed(artifacts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"transform_name": n, "data": d} for n, d in artifacts.items()]


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
    round_no: int, history: list[dict[str, Any]], labels: tuple[str, ...] = ("A", "B"),
) -> tuple[str, str]:
    task = _task_payload(spec)
    feedback = _feedback(history)
    llm = _make_llm(client, gateway_url, token, nodes, artifacts)

    planner = await llm("Planner", {
        "task": task, "history": _planner_view(history), "candidates": len(labels),
    })
    assignments, fallback = _parse_assignments(planner, spec, labels)
    if fallback:
        planner["planner_fallback"] = True
    gate = asyncio.Semaphore(_MAX_CONCURRENT_CANDIDATES)

    async def generate(label: str, assignment: dict[str, str]) -> None:
        # Two calls per candidate keep each under the gateway's LLM timeout: a long
        # reasoning "derive" step, then a cheap "formalise" step that emits strict JSON.
        async with gate:
            derive_input: dict[str, Any] = {"task": task, "assignment": assignment}
            if feedback:
                derive_input["feedback"] = feedback
            derive = await llm(f"Derive_{label}", derive_input)
            await llm(f"Generator_{label}", {
                "task": task, "assignment": assignment, "derivation": derive.get("response"),
            })

    # Candidates run concurrently (at most two gateway slots at a time). A candidate whose
    # generation fails is NOT_FOUND alone; the run fails only if EVERY candidate does.
    results = await asyncio.gather(
        *(generate(l, assignments[l]) for l in labels), return_exceptions=True
    )
    gen_errors: dict[str, PipelineRunError] = {}
    for label, res in zip(labels, results):
        if isinstance(res, PipelineRunError):
            gen_errors[label] = res
            artifacts[f"criteria_{label.lower()}"] = _not_found_row(f"generation failed: {res}")
        elif isinstance(res, BaseException):
            raise res
    if len(gen_errors) == len(labels):
        raise gen_errors[labels[-1]]
    for label in labels:
        if label not in gen_errors:
            await _evaluate_candidate(
                label, f"Generator_{label}", nodes, spec_path, artifacts, seed=round_no
            )

    verdicts = {l: artifacts[f"criteria_{l.lower()}"]["verdict"] for l in labels}
    best = max(
        labels,
        key=lambda l: (
            *_cand_score(verdicts[l], _candidate_summary(l, artifacts), round_no)[:3],
            l == "A",
        ),
    )
    return verdicts[best], best


def _expand_candidates(nodes: dict[str, TransformSpec], labels: tuple[str, ...]) -> None:
    """The pipeline YAML defines candidates A and B; extra labels are clones of A's nodes."""
    for label in labels[2:]:
        for stem, lower in (("Derive", False), ("Generator", False), ("checks", True),
                            ("iota", True), ("criteria", True)):
            clone = copy.deepcopy(nodes[f"{stem}_a" if lower else f"{stem}_A"])
            clone.name = f"{stem}_{label.lower()}" if lower else f"{stem}_{label}"
            if "source" in clone.config:
                clone.config["source"] = f"Generator_{label}"
            nodes[clone.name] = clone


def _round_nodes(
    nodes: dict[str, TransformSpec], labels: tuple[str, ...], repair_model: str | None, round_no: int
) -> dict[str, TransformSpec]:
    """Tiering (P4.4): flash does breadth in round 1, the pro `MODEL_REPAIR` model does the
    depth - every Derive call in repair rounds. Without a repair model, nodes are unchanged."""
    if not repair_model or round_no < 2:
        return nodes
    out = dict(nodes)
    for label in labels:
        node = copy.deepcopy(nodes[f"Derive_{label}"])
        node.config["model"] = repair_model
        out[node.name] = node
    return out


def _best_family(
    spec: ConstructSpec, spec_path: str, artifacts: dict[str, dict[str, Any]], label: str
) -> dict[str, Any]:
    """Names the best candidate by family (decision D3): the planner's mechanism + deterministic
    structural tags. A label for a human literature check, never a novelty claim."""
    try:
        assignments, _ = _parse_assignments(artifacts.get("Planner", {}), spec, tuple(_LABELS))
    except Exception:  # noqa: BLE001
        assignments = {}
    candidate = _loads_lenient(artifacts.get(f"Generator_{label}", {}).get("response"))
    tags = family_tags(spec_path, candidate) if isinstance(candidate, dict) else []
    return {"mechanism": assignments.get(label, {}).get("mechanism", ""), "tags": tags}


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
    candidates_per_round: int = 2,
) -> dict[str, Any]:
    spec = load_construct_spec(spec_path)
    if not 2 <= candidates_per_round <= _MAX_CANDIDATES:
        raise ValueError(f"candidates_per_round must be between 2 and {_MAX_CANDIDATES}")
    labels = tuple(_LABELS[:candidates_per_round])
    text = render_pipeline_yaml(pipeline_path, models_path)
    nodes = PipelineSpec.from_yaml_text(text).by_name()
    _expand_candidates(nodes, labels)
    repair_model = json.loads(Path(models_path).read_text(encoding="utf-8")).get(_REPAIR_MODEL_KEY)
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
                            client, gateway_url, token, spec, str(spec_path),
                            _round_nodes(nodes, labels, repair_model, n), current, n, history, labels,
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
                    anchor = _feedback(history)
                    history.append(_round_summary(
                        n, verdict, best, current, anchor["must_still_pass"] if anchor else None, labels,
                    ))
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
    family = _best_family(spec, str(spec_path), raw[best_h["round"]], best_h["best_candidate"])
    all_datas = [d for r in raw.values() for d in r.values()] + list(review.values())
    cost = run_cost_breakdown(all_datas, prices)
    return {
        "status": "completed", "session_id": session_id, "verdict": best_h["verdict"],
        "best_candidate": best_h["best_candidate"], "best_round": best_h["round"],
        "best_family": family, "stop_reason": stop_reason, "rounds": rounds, "cost_usd": cost["total_usd"],
        "cost_reported_usd": cost["reported_usd"], "cost_estimated_usd": cost["estimated_usd"],
        "cost_truncated_usd": cost["truncated_usd"], "cost_is_exact": cost["is_exact"],
        "unpriced_models": cost["unpriced_models"], "token_usage": usage_by_model(all_datas),
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "artifacts": _packed(raw[best_h["round"]]) + _packed(review),
    }
