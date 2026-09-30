"""Replay a candidate through the deterministic half of the construct pipeline.

Same stages, same order and same gate rule as construct_pipeline._evaluate_candidate
(checks -> iota trace only if the symbolic gate passed -> criteria), but with no LLM and
no gateway: used by the corpus tests, the residual diagnostic and the bench tooling.
The iota trace runs through iota_trace_transform._run_sandbox, so tests monkeypatch that
(tests/iota_helpers.fake_sandbox) to avoid Docker.
"""
from __future__ import annotations

import json
from typing import Any

from ._compat import SessionContext
from .construct_criteria_transform import ConstructCriteriaTransform
from .construct_spec import GATE_CHECKS
from .iota_trace_transform import IotaTraceTransform
from .vector_calculus_check_transform import VectorCalculusCheckTransform

_CTX = SessionContext()


async def replay_candidate(
    spec_path: Any, candidate: dict[str, Any], *, seed: int = 1, iota_timeout: int = 120
) -> dict[str, Any]:
    spec_path = str(spec_path)
    inp = {"G": {"response": json.dumps(candidate)}}
    checks = await VectorCalculusCheckTransform(
        inp, {"spec_path": spec_path, "source": "G", "seed": seed}, _CTX
    )
    gate_ok = all(
        r["status"] == "pass" for r in checks["results"] if r.get("check") in GATE_CHECKS
    )
    if gate_ok:
        iota = await IotaTraceTransform(
            inp, {"spec_path": spec_path, "source": "G", "timeout_seconds": iota_timeout}, _CTX
        )
    else:
        iota = {"results": [], "skipped": "gate failed"}
    return await ConstructCriteriaTransform(
        {"checks": checks, "iota": iota},
        {"spec_path": spec_path, "sources": ["checks", "iota"]}, _CTX,
    )
