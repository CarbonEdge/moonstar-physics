"""Local orchestrator for the `physics_hypothesis` pipeline.

`physics_hypothesis.yaml` mixes two kinds of steps: LLM calls (Extractor,
theory_critic, devils_advocate, synthesizer) and deterministic physics
checks (ConservationLawCheckTransform, QMCalculationTransform,
ReferenceDataLookupTransform, DimensionConsistencyTransform). It used to be
submitted to the Python `moonstar` gateway as one YAML and executed
entirely on that side, because that gateway loaded moonstar-physics's
transforms as `moonstar.transforms` entry points at worker startup
(`importlib.metadata`).

That gateway no longer exists — moonstar-rs replaced it, and moonstar-rs
has **no runtime plugin mechanism**: transforms register at compile time
via `inventory::submit!`, so an external package can never make its own
transform types resolvable there. moonstar-physics is meant to stay an
outside add-on (never merged into the harness itself, matching how
moonstar-crypto/moonstar-video are pure HTTP clients of it) — so this
module runs the DAG *locally* instead of asking the gateway to:

  - LLM steps: point at the gateway. Each one is submitted as its own
    single-node, single-transform session (`POST /pipelines/run` with that
    node's `config` and an `initial_input` built from whichever local
    results it depends on) — the gateway only ever sees `LlmTransform`,
    a type it has always known how to run, with model selection coming
    from `pipelines/models.json` same as before.
  - Deterministic checks: run the transform in-process, right here, no
    network round-trip — passing the same `{"Extractor": {...}}`-shaped
    `input` dict the gateway executor would have.

The return shape mirrors a completed gateway session
(`{"status": "completed", "artifacts": [{"transform_name", "data"}, ...]}`)
so downstream code (`_pipeline_client.find_artifact`/`extract_verdict`,
`scripts/publish_review.py`, `scripts/build_site.py`) needs no changes.
"""
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx

from ._compat import NonRetryableTransformError, SessionContext
from ._pipeline_spec import PipelineSpec, TransformSpec
from .conservation_transform import ConservationLawCheckTransform
from .dimension_transform import DimensionConsistencyTransform
from .qm_calc_transform import QMCalculationTransform
from .reference_lookup_transform import ReferenceDataLookupTransform

_POLL_INTERVAL_SECONDS = 2
_MAX_POLLS = 90

_DUMMY_CTX = SessionContext()

# Transform types this module runs locally instead of dispatching to the
# gateway — must match physics_hypothesis.yaml's wave-1 deterministic steps.
_LOCAL_TRANSFORMS: dict[str, Callable[[dict[str, Any], dict[str, Any], SessionContext], Awaitable[dict[str, Any]]]] = {
    "ConservationLawCheckTransform": ConservationLawCheckTransform,
    "QMCalculationTransform": QMCalculationTransform,
    "ReferenceDataLookupTransform": ReferenceDataLookupTransform,
    "DimensionConsistencyTransform": DimensionConsistencyTransform,
}


class PipelineRunError(RuntimeError):
    """Raised when a gateway-submitted LLM step fails, is rejected, or times out."""


async def _submit_single_node(
    client: httpx.AsyncClient,
    gateway_url: str,
    token: str,
    transform: TransformSpec,
    initial_input: dict[str, Any],
) -> dict[str, Any]:
    """Submits one LLM transform as its own root-node gateway session and
    returns its artifact data once the session completes.

    A lone root node with no `input:` receives whatever `initial_input`
    the session was submitted with — the same mechanism a multi-node
    pipeline uses to feed its first transform — so this reproduces exactly
    what that node would have received as part of the full pipeline.
    """
    solo_yaml = _render_solo_yaml(transform)
    headers = {"Authorization": f"Bearer {token}"}

    submit_resp = await client.post(
        f"{gateway_url}/pipelines/run",
        json={"yaml_spec": solo_yaml, "initial_input": initial_input},
        headers=headers,
    )
    submit_resp.raise_for_status()
    session_id = submit_resp.json()["session_id"]

    for _ in range(_MAX_POLLS):
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
        status_resp = await client.get(f"{gateway_url}/sessions/{session_id}", headers=headers)
        status_resp.raise_for_status()
        status_data = status_resp.json()
        status = status_data.get("status")

        if status == "completed":
            for artifact in status_data.get("artifacts", []):
                if artifact.get("transform_name") == transform.name:
                    return artifact.get("data") or {}
            raise PipelineRunError(
                f"session {session_id} ({transform.name}) completed but produced no matching artifact"
            )
        if status in ("failed", "rejected"):
            raise PipelineRunError(f"session {session_id} ({transform.name}) {status}")

    raise PipelineRunError(f"session {session_id} ({transform.name}) timed out waiting for completion")


def _render_solo_yaml(transform: TransformSpec) -> str:
    import yaml as _yaml

    spec = {
        "pipeline": {"name": f"physics-hypothesis-{transform.name}", "version": "1.0"},
        "transforms": [
            {"name": transform.name, "type": transform.type, "config": transform.config}
        ],
    }
    return _yaml.safe_dump(spec, sort_keys=False)


async def run_physics_hypothesis(
    hypothesis: str,
    gateway_url: str,
    token: str,
    pipeline_path: Path,
    models_path: Path,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    """Runs physics_hypothesis.yaml's full wave 1 -> 2 -> 3 DAG, LLM steps
    against `gateway_url`, deterministic checks in-process. Returns a dict
    shaped like a completed (or failed) gateway session.

    `transport` is exposed only so tests can inject an `httpx.MockTransport`
    instead of hitting a real gateway; production callers leave it unset.
    """
    from ._pipeline_spec import render_pipeline_yaml

    text = render_pipeline_yaml(pipeline_path, models_path)
    spec = PipelineSpec.from_yaml_text(text)
    transforms = spec.by_name()
    artifacts: dict[str, dict[str, Any]] = {}
    # No single gateway session covers this whole run anymore (each LLM step
    # is its own session) — synthesize one id so callers still have a stable
    # handle for run-artifact bookkeeping (see scripts/publish_review.py).
    session_id = f"local-{uuid.uuid4().hex[:12]}"

    try:
        async with httpx.AsyncClient(timeout=30.0, transport=transport) as client:
            extractor = transforms["Extractor"]
            artifacts["Extractor"] = await _submit_single_node(
                client, gateway_url, token, extractor, {"hypothesis": hypothesis}
            )

            extractor_input = {"Extractor": artifacts["Extractor"]}

            for name, fn in _LOCAL_TRANSFORMS.items():
                node = next(t for t in transforms.values() if t.type == name)
                artifacts[node.name] = await fn(extractor_input, node.config, _DUMMY_CTX)

            theory_critic = transforms["theory_critic"]
            artifacts["theory_critic"] = await _submit_single_node(
                client, gateway_url, token, theory_critic, extractor_input
            )

            devils_advocate = transforms["devils_advocate"]
            wave1_input = {dep: artifacts[dep] for dep in devils_advocate.deps}
            artifacts["devils_advocate"] = await _submit_single_node(
                client, gateway_url, token, devils_advocate, wave1_input
            )

            synthesizer = transforms["synthesizer"]
            wave2_input = {dep: artifacts[dep] for dep in synthesizer.deps}
            artifacts["synthesizer"] = await _submit_single_node(
                client, gateway_url, token, synthesizer, wave2_input
            )
    except NonRetryableTransformError as e:
        return {
            "status": "failed",
            "session_id": session_id,
            "error": str(e),
            "artifacts": [
                {"transform_name": name, "data": data} for name, data in artifacts.items()
            ],
        }

    return {
        "status": "completed",
        "session_id": session_id,
        "artifacts": [{"transform_name": name, "data": data} for name, data in artifacts.items()],
    }
