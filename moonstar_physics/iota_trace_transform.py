"""IotaTraceTransform — fills the fixed field-line-trace template with a
generator candidate, runs it in the existing Docker sandbox, and maps the
result onto the spec's `sandbox_experiment` criteria (iota_nonzero /
iota_noninteger). Output rows have the same shape as
VectorCalculusCheckTransform's so ConstructCriteriaTransform can merge them.

Never `pass`es on a trace it can't trust: sandbox failure, an `error` in the
script's RESULT, or a missing `iota` all become `error` (-> "unverified").
"""
from __future__ import annotations

import json
from typing import Any

from ._compat import SessionContext
from .construct_spec import Criterion, load_construct_spec
from .iota_trace_template import IotaTemplateError, build_iota_script
from .maths._safe_parse import UnsafeExpressionError
from .numerical_experiment_transform import NumericalExperimentTransform
from .vector_calculus_check_transform import _CandidateError, _load_candidate, _resolve_candidate

_IOTA_ZERO_TOL = 1e-3
_INTEGER_TOL = 1e-3
_DEFAULT_TIMEOUT_SECONDS = 60
_CTX = SessionContext()
_META = {"_model": "none", "_provider": "none", "_input_tokens": 0, "_output_tokens": 0}


async def _run_sandbox(script: str, timeout_seconds: int) -> dict[str, Any]:
    return await NumericalExperimentTransform(
        {"IotaTrace": {"response": json.dumps({"code": script})}},
        {"timeout_seconds": timeout_seconds},
        _CTX,
    )


def _row(c: Criterion, status: str, **extra: Any) -> dict[str, Any]:
    return {"id": c.id, "check": c.check, "status": status, **extra}


def _judge(c: Criterion, iotas: list[float], iota: float, extra: dict[str, Any]) -> dict[str, Any]:
    """Judged on every seed surface: iota may differ between surfaces (magnetic shear)."""
    if c.kind == "iota_nonzero":
        same_sign = all(v > 0 for v in iotas) or all(v < 0 for v in iotas)
        ok = same_sign and all(abs(v) > _IOTA_ZERO_TOL for v in iotas)
    else:  # iota_noninteger; construct_spec guarantees the kind is known
        ok = all(abs(v - round(v)) > _INTEGER_TOL for v in iotas)
    return _row(c, "pass" if ok else "fail", iota=iota, **extra)


async def IotaTraceTransform(
    input: dict[str, Any], config: dict[str, Any], ctx: SessionContext
) -> dict[str, Any]:
    spec = load_construct_spec(config["spec_path"])
    source = config.get("source", "Generator_A")
    timeout = int(config.get("timeout_seconds", _DEFAULT_TIMEOUT_SECONDS))
    targets = [c for c in spec.criteria if c.check == "sandbox_experiment"]
    candidate = _load_candidate(input, source)

    def all_error(detail: str, **extra: Any) -> dict[str, Any]:
        return {"results": [_row(c, "error", detail=detail) for c in targets], **extra, **_META}

    if not targets:
        return {"results": [], **_META}

    dof_names = [d.name for d in spec.degrees_of_freedom]
    fixed = candidate.get("params") if isinstance(candidate.get("params"), dict) else {}
    try:
        B, psi, _p = _resolve_candidate(candidate, dof_names)
        dof_values = {
            d.name: float(fixed[d.name]) if d.name in fixed else (d.low + d.high) / 2
            for d in spec.degrees_of_freedom
        }
        script = build_iota_script(B, psi, dof_values, spec.sample_box)
    except (_CandidateError, UnsafeExpressionError, IotaTemplateError, TypeError, ValueError) as e:
        return all_error(f"candidate rejected: {e}")

    sandbox = await _run_sandbox(script, timeout)
    stdout = sandbox.get("stdout", "")
    common = {"script": script, "stdout": stdout, "dof_values": dof_values}
    result = sandbox.get("result")
    if not sandbox.get("ran"):
        return all_error(str(sandbox.get("detail")), **common)
    if not isinstance(result, dict) or "error" in result or not isinstance(result.get("iota"), (int, float)):
        detail = result.get("error") if isinstance(result, dict) and "error" in result else "no numeric 'iota' in RESULT"
        return all_error(str(detail), **common)

    seeds = result.get("iota_seeds")
    if isinstance(seeds, list) and seeds and all(isinstance(v, (int, float)) for v in seeds):
        iotas = [float(v) for v in seeds]
    else:
        iotas = [float(result["iota"])]
    extra = {
        "iota_seeds": result.get("iota_seeds"),
        "iota_spread": result.get("iota_spread"),
        "psi_drift": result.get("psi_drift"),
    }
    return {
        "results": [_judge(c, iotas, float(result["iota"]), extra) for c in targets],
        **common, **_META,
    }
