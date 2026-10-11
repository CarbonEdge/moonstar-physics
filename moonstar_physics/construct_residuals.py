"""Residual diagnostics for failed gate criteria (P4.3) - actionable feedback.

"force_balance residual 1.8e5" tells a model nothing. For each failed gate
criterion this reports, deterministically and with no LLM:
  (c) the residual vector at five labelled points of the meridional plane
      (axis, inboard, outboard, top, bottom; the axis is the grid minimum of psi),
  (b) per residual component, the dominant terms of the expanded residual ranked
      by their size at those points,
  (a) per residual component, a simplified closed form - only when the
      expression is small and simplification finishes inside a hard timeout
      (run in a child process, so a sympy blow-up cannot hang the pipeline),
and, for any criterion whose expression is a force balance, (curl B) x B and
grad p side by side so the model can see which one to change.
Everything is capped in size; any failure degrades to fewer fields, never an error.
This is evidence for the next repair, not a verdict.
"""
from __future__ import annotations

import math
import multiprocessing as mp
from typing import Any

import numpy as np
import sympy

from .construct_spec import GATE_CHECKS, ConstructSpec
from .maths._safe_parse import UnsafeExpressionError
from .vector_calculus import COORDS, CriterionExprError, cross, curl, evaluate_expr, grad, residual_components
from .vector_calculus_check_transform import _DEFAULT_UNKNOWNS, _CandidateError, _resolve_env

SIMPLIFY_TIMEOUT_SECONDS = 6.0
_OPS_CAP_SIMPLIFY = 250
_OPS_CAP_EXPAND = 800
_MAX_TERMS = 3
_MAX_EXPR_CHARS = 400
_GRID = 41
_POINT_NAMES = ("axis", "inboard", "outboard", "top", "bottom")


def _simplify_worker(texts: list[str], queue) -> None:
    for t in texts:
        try:
            queue.put(sympy.srepr(sympy.simplify(sympy.sympify(t))))
        except Exception:  # noqa: BLE001 - any failure just means "no closed form"
            queue.put(None)


def simplify_many_with_timeout(exprs: list[sympy.Expr], timeout: float | None = None) -> list[sympy.Expr | None]:
    """simplify() each expr in ONE child process under a shared deadline. Entries are None
    when too big / too slow / failed. Never raises, never hangs (the child is terminated)."""
    import queue as _q
    import time

    out: list[sympy.Expr | None] = [None] * len(exprs)
    todo = [i for i, e in enumerate(exprs) if sympy.count_ops(e) <= _OPS_CAP_SIMPLIFY]
    if not todo:
        return out
    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    proc = ctx.Process(target=_simplify_worker, args=([sympy.srepr(exprs[i]) for i in todo], queue), daemon=True)
    proc.start()
    deadline = time.monotonic() + (SIMPLIFY_TIMEOUT_SECONDS if timeout is None else timeout)
    try:
        for i in todo:
            try:
                text = queue.get(timeout=max(deadline - time.monotonic(), 0.01))
            except _q.Empty:
                break
            out[i] = sympy.sympify(text) if text else None
    finally:
        proc.join(0.2)
        if proc.is_alive():
            proc.terminate()
            proc.join(1)
    return out


def labelled_points(
    psi: sympy.Expr | None, spec: ConstructSpec, dof: dict[str, float]
) -> dict[str, tuple[float, float, float]]:
    """Five (x, y, z) points in the phi=0 half-plane. With a flux function psi the axis is its
    grid minimum; without one (e.g. a Beltrami spec) the box centre of that half-plane."""
    rho_hi = math.hypot(max(abs(v) for v in spec.sample_box["x"]), max(abs(v) for v in spec.sample_box["y"]))
    z_lo, z_hi = spec.sample_box["z"]
    if psi is None:
        r0, z0 = 0.5 * (0.05 + rho_hi), 0.5 * (z_lo + z_hi)
    else:
        rho = np.linspace(0.05, rho_hi, _GRID)
        zs = np.linspace(z_lo, z_hi, _GRID)
        rr, zz = np.meshgrid(rho, zs)
        syms = [*COORDS, *(sympy.Symbol(n) for n in dof)]
        fn = sympy.lambdify(syms, psi, "numpy")
        with np.errstate(all="ignore"):
            vals = np.asarray(fn(rr, np.zeros_like(rr), zz, *dof.values()), dtype=float)
        vals = np.where(np.isfinite(vals), vals, np.inf)
        iz, ir = np.unravel_index(int(np.argmin(vals)), vals.shape)
        r0, z0 = float(rho[ir]), float(zs[iz])
    dr, dz = 0.3 * (rho_hi - 0.05), 0.3 * (z_hi - z_lo)
    return {
        "axis": (r0, 0.0, z0), "inboard": (max(r0 - dr, 0.05), 0.0, z0), "outboard": (r0 + dr, 0.0, z0),
        "top": (r0, 0.0, z0 + dz), "bottom": (r0, 0.0, z0 - dz),
    }


def _at(exprs: list[sympy.Expr], points: dict[str, tuple[float, float, float]], dof: dict[str, float]):
    syms = [*COORDS, *(sympy.Symbol(n) for n in dof)]
    fn = sympy.lambdify(syms, exprs, "numpy")
    out = {}
    for name, (x, y, z) in points.items():
        with np.errstate(all="ignore"):
            vals = [complex(v) for v in fn(x, y, z, *dof.values())]
        out[name] = [float(v.real) if abs(v.imag) < 1e-12 and math.isfinite(v.real) else None for v in vals]
    return out


def _dominant_terms(comp: sympy.Expr, points, dof) -> list[str] | None:
    if sympy.count_ops(comp) > _OPS_CAP_EXPAND:
        return None
    try:
        terms = sympy.Add.make_args(sympy.expand(comp))
        scored = []
        for t in terms:
            at = _at([t], points, dof)
            size = max((abs(v[0]) for v in at.values() if v[0] is not None), default=0.0)
            scored.append((size, t))
    except Exception:  # noqa: BLE001
        return None
    scored.sort(key=lambda s: -s[0])
    return [f"{str(t)[:120]}  (~{s:.3g})" for s, t in scored[:_MAX_TERMS]]


def diagnose_gate_failures(
    spec: ConstructSpec, candidate: dict[str, Any], failed_ids: list[str], *, symbolic: bool = True
) -> dict[str, Any]:
    """{criterion_id: {points, components, ...}} for the failed gate criteria."""
    dof_names = [d.name for d in spec.degrees_of_freedom]
    try:
        env = _resolve_env(candidate, dof_names, spec.unknowns or _DEFAULT_UNKNOWNS)
    except (_CandidateError, UnsafeExpressionError, ValueError, TypeError):
        return {}
    fixed = candidate.get("params") if isinstance(candidate.get("params"), dict) else {}
    dof = {d.name: float(fixed.get(d.name, (d.low + d.high) / 2)) for d in spec.degrees_of_freedom}
    psi = env.get("psi") if not isinstance(env.get("psi"), tuple) else None
    try:
        points = labelled_points(psi, spec, dof)
    except Exception:  # noqa: BLE001
        return {}
    out: dict[str, Any] = {}
    for c in spec.criteria:
        if c.id not in failed_ids or c.check not in GATE_CHECKS:
            continue
        entry: dict[str, Any] = {}
        try:
            comps = list(residual_components(evaluate_expr(c.expr, env)))
            entry["residual_at_points"] = _at(comps, points, dof)
            entry["components"] = []
            simple_all = simplify_many_with_timeout(comps) if symbolic else [None] * len(comps)
            for i, comp in enumerate(comps):
                row: dict[str, Any] = {"index": i}
                terms = _dominant_terms(comp, points, dof)
                if terms:
                    row["dominant_terms"] = terms
                if simple_all[i] is not None:
                    text = str(simple_all[i])
                    row["simplified"] = text if len(text) <= _MAX_EXPR_CHARS else text[:_MAX_EXPR_CHARS] + "..."
                entry["components"].append(row)
            B, p = env.get("B"), env.get("p")
            if (isinstance(B, tuple) and p is not None and not isinstance(p, tuple)
                    and all(w in (c.expr or "") for w in ("curl", "grad", "cross"))):
                entry["lorentz_vs_grad_p"] = {
                    "curl_B_cross_B": _at(list(cross(curl(B), B)), points, dof),
                    "grad_p": _at(list(grad(p)), points, dof),
                }
        except (CriterionExprError, Exception):  # noqa: BLE001 - degrade, never fail the run
            continue
        entry["points"] = {k: list(v) for k, v in points.items()}
        out[c.id] = entry
    return out


DIAGNOSE_TIMEOUT_SECONDS = 60.0


def _diagnose_worker(spec_path: str, candidate: dict[str, Any], failed: list[str], queue) -> None:
    from .construct_spec import load_construct_spec
    try:
        queue.put(diagnose_gate_failures(load_construct_spec(spec_path), candidate, failed))
    except Exception:  # noqa: BLE001
        queue.put({})


def diagnose_with_timeout(
    spec_path: str, candidate: dict[str, Any], failed: list[str], timeout: float | None = None
) -> dict[str, Any]:
    """diagnose_gate_failures in a child process under a HARD deadline; {} on timeout/failure.

    A live run (2026-10-04, run 9) lost ~3 h past its wallclock budget because the diagnostics
    ran in an uncancellable thread on a pathological expression. A child process can always be
    killed, so a pipeline run can never be held hostage by diagnostics.
    """
    import queue as _q

    ctx = mp.get_context("spawn")
    q = ctx.Queue()
    proc = ctx.Process(target=_diagnose_worker, args=(str(spec_path), candidate, failed, q))
    proc.start()
    try:
        return q.get(timeout=DIAGNOSE_TIMEOUT_SECONDS if timeout is None else timeout)
    except _q.Empty:
        return {}
    finally:
        proc.join(0.5)
        if proc.is_alive():
            proc.terminate()
            proc.join(2)
