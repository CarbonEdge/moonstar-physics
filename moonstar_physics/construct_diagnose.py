"""Health metrics and a residual classification for a construct candidate.

Why: live runs produced force-balance residuals from 1e5 to 1e8 and we did not know whether
those candidates were genuinely wrong or merely singular / badly scaled. This answers that
deterministically, with no LLM, from the candidate alone.

Classification of the worst gate (div B, B.grad(psi), force balance), decided in this order:
  undefined  candidate does not resolve, or fewer than the checker's minimum (200) sample
             points are finite (a field may legitimately be defined on only part of the box)
  ok         every gate's absolute residual <= ABS_TOL (the checker's own pass rule)
  scale      some gate fails the absolute tolerance but its RELATIVE residual
             (max|res| / max of the terms being balanced) is <= REL_TOL: only the scale is large
  localised  the failing gate exceeds ABS_TOL at <= LOCALISED_FRACTION of the valid samples:
             typical of a singularity (1/R-type) or a few bad points, not of a wrong field
  wrong      everything else: the residual is large at many points
Numbers are evidence, not proof. A `localised` candidate still FAILS the checker.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import sympy

from .construct_spec import load_construct_spec
from .maths._safe_parse import UnsafeExpressionError
from .vector_calculus import COORDS, curl, grad
from .vector_calculus_check_transform import (
    _MIN_VALID, _CandidateError, _evaluate, _resolve_candidate, _sample,
)

ABS_TOL = 1e-8
REL_TOL = 1e-9
LOCALISED_FRACTION = 0.02


def _stats(res: np.ndarray, scale: np.ndarray, mask: np.ndarray) -> dict[str, float]:
    r = np.abs(res[mask])
    s = np.maximum(np.abs(scale[mask]), 1e-300)
    return {
        "abs": float(r.max()) if r.size else float("nan"),
        "rel": float((r / s).max()) if r.size else float("nan"),
        "frac_bad": float((r > ABS_TOL).mean()) if r.size else float("nan"),
    }


def candidate_health(spec_path: Any, candidate: dict[str, Any], *, seed: int = 1) -> dict[str, Any]:
    spec = load_construct_spec(spec_path)
    dof_names = [d.name for d in spec.degrees_of_freedom]
    try:
        B, psi, p = _resolve_candidate(candidate, dof_names)
    except (_CandidateError, UnsafeExpressionError, ValueError, TypeError) as e:
        return {"classification": "undefined", "error": str(e)}

    fixed = candidate.get("params") if isinstance(candidate.get("params"), dict) else {}
    arg_syms = [*COORDS, *(sympy.Symbol(n) for n in dof_names)]
    arrays = _sample(spec, fixed, np.random.default_rng(seed))

    cb = curl(tuple(B))
    gp = grad(p)
    gpsi = grad(psi)
    dBdx = [sympy.diff(B[i], COORDS[i]) for i in range(3)]
    exprs = [*B, *cb, *gp, *gpsi, *dBdx]
    try:
        v = _evaluate(exprs, arg_syms, arrays)
    except Exception as e:  # sympy/numpy failures on exotic expressions
        return {"classification": "undefined", "error": f"evaluation failed: {e}"}
    b, c, g, gs, dd = v[0:3], v[3:6], v[6:9], v[9:12], v[12:15]

    finite = np.all([np.isfinite(a) for a in v], axis=0)
    finite_fraction = float(finite.mean())
    if int(finite.sum()) < _MIN_VALID:
        return {"classification": "undefined", "finite_fraction": finite_fraction}

    bmag = np.sqrt(b[0] ** 2 + b[1] ** 2 + b[2] ** 2)
    lorentz = [c[1] * b[2] - c[2] * b[1], c[2] * b[0] - c[0] * b[2], c[0] * b[1] - c[1] * b[0]]
    force = [lorentz[i] - g[i] for i in range(3)]
    force_res = np.maximum.reduce([np.abs(f) for f in force])
    force_scale = np.maximum(
        np.maximum.reduce([np.abs(l) for l in lorentz]), np.maximum.reduce([np.abs(x) for x in g])
    )
    flux_res = b[0] * gs[0] + b[1] * gs[1] + b[2] * gs[2]
    flux_scale = bmag * np.sqrt(gs[0] ** 2 + gs[1] ** 2 + gs[2] ** 2)
    div_res = dd[0] + dd[1] + dd[2]
    div_scale = np.abs(dd[0]) + np.abs(dd[1]) + np.abs(dd[2])

    gates = {
        "div_free": _stats(div_res, div_scale, finite),
        "flux_surface": _stats(flux_res, flux_scale, finite),
        "force_balance": _stats(force_res, force_scale, finite),
    }
    bm = bmag[finite]
    out: dict[str, Any] = {
        "finite_fraction": finite_fraction,
        "b_max": float(bm.max()),
        "b_median": float(np.median(bm)),
        "b_dynamic_range": float(bm.max() / max(np.median(bm), 1e-300)),
        "curl_b_max": float(np.max(np.abs(np.stack(c))[:, finite])),
        "grad_p_max": float(np.max(np.abs(np.stack(g))[:, finite])),
        "gates": gates,
    }
    failing = {k: s for k, s in gates.items() if s["abs"] > ABS_TOL}
    if not failing:
        out["classification"] = "ok"
        return out
    worst = max(failing, key=lambda k: failing[k]["abs"])
    out["worst_gate"] = worst
    w = failing[worst]
    if all(s["rel"] <= REL_TOL for s in failing.values()):
        out["classification"] = "scale"
    elif w["frac_bad"] <= LOCALISED_FRACTION:
        out["classification"] = "localised"
    else:
        out["classification"] = "wrong"
    return out
