"""VectorCalculusCheckTransform — checks a construct candidate (B, psi, p
as strings) against a ConstructSpec's checkable criteria.

Candidate strings are parsed one scalar at a time through safe_parse_expr
(named intermediates in an ordered "defs" map are substituted in order),
differentiated symbolically, then evaluated numerically with lambdify at
random points inside the spec's sample box, with degrees of freedom drawn
from their ranges (or fixed via the candidate's "params"). Points where
the candidate is undefined (NaN/complex) are discarded; if fewer than
_MIN_VALID survive the criterion is an *error*, never a pass — a
candidate that is undefined everywhere must not look consistent.

Pass/fail is numeric (max abs residual <= tolerance). This is evidence,
not proof: 20000 random draws at 1e-8 catches wrong fields decisively
but does not certify an identity symbolically.
"""
from __future__ import annotations

import json
from typing import Any

import numpy as np
import sympy

from ._compat import NonRetryableTransformError, SessionContext
from .construct_spec import ConstructSpec, Criterion, load_construct_spec
from .maths._safe_parse import UnsafeExpressionError, safe_parse_expr
from .vector_calculus import COORDS, CriterionExprError, evaluate_expr, residual_components

_N_DRAWS = 20000
_MIN_VALID = 200
_SEED = 0
_DEFAULT_TOLERANCE = 1e-8
_NONNEGATIVE_SLACK = 1e-12
_CONSTANT_TOLERANCE = 1e-6
_ROTATION_ANGLE = 0.7
_BREAK_TOLERANCE = 1e-6
_NEST_PHIS = (0.0, np.pi / 2, np.pi, 3 * np.pi / 2)
_NEST_GRID = 61
_NEST_RAYS = 8
_NEST_RAY_POINTS = 100
_NEST_DECREASE_TOL = 1e-9
_NEST_RELATIVE_TOL = 1e-4   # absorbs the residual error of the located axis
_CHECKABLE = frozenset({"divergence_zero", "identity_zero", "numeric_sample"})


class _CandidateError(ValueError):
    """The candidate could not be parsed/resolved into (B, psi, p)."""


def _load_candidate(input: dict[str, Any], source: str) -> dict[str, Any]:
    block = input.get(source)
    if not isinstance(block, dict):
        raise NonRetryableTransformError(
            f"Expected a {source!r} dependency in input — is this transform's "
            "`input:` wired to the generator step?"
        )
    raw = block.get("response")
    if not isinstance(raw, str):
        raise NonRetryableTransformError(f"{source!r} artifact has no string 'response' field")
    try:
        candidate = json.loads(raw)
    except json.JSONDecodeError as e:
        raise NonRetryableTransformError(f"{source!r} response is not valid JSON: {e}") from e
    if not isinstance(candidate, dict):
        raise NonRetryableTransformError(f"{source!r} response must be a JSON object")
    return candidate


_DEFAULT_UNKNOWNS = (
    {"name": "B", "kind": "vector_field"},
    {"name": "psi", "kind": "scalar_field"},
    {"name": "p", "kind": "scalar_field", "of": "psi"},
)


def _resolve_env(candidate: dict[str, Any], dof_names: list[str], unknowns=_DEFAULT_UNKNOWNS) -> dict[str, Any]:
    """The spec's unknowns as sympy objects in x, y, z and the DOF symbols: a vector_field is a
    3-tuple, a scalar_field a scalar; `of: other` lets a scalar be written in terms of another
    unknown's name (p in terms of psi). The DOF names are also bound, so criteria may use them."""
    objects = candidate.get("objects")
    if not isinstance(objects, dict):
        raise _CandidateError("candidate has no 'objects' mapping")
    defs = candidate.get("defs") or {}
    if not isinstance(defs, dict):
        raise _CandidateError("'defs' must be a mapping of name -> expression")

    base = ["x", "y", "z", *dof_names]
    resolved: dict[str, sympy.Expr] = {}

    def parse(text: Any, extra: tuple[str, ...] = ()) -> sympy.Expr:
        expr = safe_parse_expr(text, base + list(resolved) + list(extra))
        return expr.subs({sympy.Symbol(n): v for n, v in resolved.items()})

    all_def_names = set(defs.keys())
    for name, text in defs.items():
        if name in base:
            raise _CandidateError(f"def {name!r} would shadow a coordinate or free parameter")
        resolved[name] = parse(text)
        forward = resolved[name].free_symbols & {
            sympy.Symbol(n) for n in (all_def_names - set(resolved.keys()))
        }
        if forward:
            raise _CandidateError(
                f"def {name!r} references future def(s): {sorted(str(s) for s in forward)}"
            )

    allowed = {sympy.Symbol(n) for n in base}
    env: dict[str, Any] = {}
    for u in unknowns:
        name = u["name"]
        if u.get("kind") == "vector_field":
            raw = objects.get(name)
            if not (isinstance(raw, list) and len(raw) == 3):
                raise _CandidateError(f"objects.{name} must be a list of exactly 3 expression strings")
            env[name] = tuple(parse(t) for t in raw)
        else:
            of = u.get("of")
            expr = parse(objects.get(name), (of,) if of else ())
            env[name] = expr.subs(sympy.Symbol(of), env[of]) if of else expr
        parts = env[name] if isinstance(env[name], tuple) else (env[name],)
        for i, expr in enumerate(parts):
            extra = expr.free_symbols - allowed
            if extra:
                label = f"{name}[{i}]" if isinstance(env[name], tuple) else name
                raise _CandidateError(f"{label} has unresolved symbol(s) {sorted(str(s) for s in extra)}")
    for d in dof_names:
        env.setdefault(d, sympy.Symbol(d))
    return env


def _resolve_candidate(candidate: dict[str, Any], dof_names: list[str]):
    """Returns (B, psi, p) as sympy objects in terms of x, y, z and the DOF symbols (MHD specs)."""
    env = _resolve_env(candidate, dof_names)
    return env["B"], env["psi"], env["p"]


def _sample(spec: ConstructSpec, fixed: dict[str, Any], rng: np.random.Generator):
    arrays = [rng.uniform(*spec.sample_box[axis], _N_DRAWS) for axis in ("x", "y", "z")]
    for dof in spec.degrees_of_freedom:
        if dof.name in fixed:
            arrays.append(np.full(_N_DRAWS, float(fixed[dof.name])))
        else:
            arrays.append(rng.uniform(dof.low, dof.high, _N_DRAWS))
    return arrays


def _evaluate(exprs: list[sympy.Expr], arg_syms: list[sympy.Symbol], arrays: list[np.ndarray]):
    fn = sympy.lambdify(arg_syms, list(exprs), "numpy", cse=True)
    with np.errstate(all="ignore"):
        raw = fn(*arrays)
    out = []
    for value in raw:
        arr = np.asarray(value)
        if np.iscomplexobj(arr):
            arr = np.where(np.abs(arr.imag) <= 1e-12, arr.real, np.nan)
        out.append(np.broadcast_to(arr.astype(float), (_N_DRAWS,)))
    return out


def _valid_mask(arrs: list[np.ndarray]) -> np.ndarray:
    return np.all([np.isfinite(a) for a in arrs], axis=0)


def _result(criterion: Criterion, status: str, **extra: Any) -> dict[str, Any]:
    return {"id": criterion.id, "check": criterion.check, "status": status, **extra}


def _too_few(criterion: Criterion, n_valid: int) -> dict[str, Any]:
    return _result(
        criterion, "error", n_valid=n_valid,
        detail=f"only {n_valid} valid sample point(s) (< {_MIN_VALID}); candidate undefined in sample box",
    )


def _check_gate(criterion, env, arg_syms, arrays, tolerance):
    value = evaluate_expr(criterion.expr, env)
    comps = residual_components(value)
    arrs = _evaluate(comps, arg_syms, arrays)
    mask = _valid_mask(arrs)
    n_valid = int(mask.sum())
    if n_valid < _MIN_VALID:
        return _too_few(criterion, n_valid)
    max_res = float(max(np.abs(a[mask]).max() for a in arrs))
    return _result(
        criterion, "pass" if max_res <= tolerance else "fail",
        n_valid=n_valid, max_residual=max_res,
    )


def _check_nested(criterion, target, arg_syms, spec, fixed):
    """psi must increase monotonically along rays leaving its minimum in the meridional
    plane (several toroidal angles): a second well or a ridge means the surfaces are not nested."""
    if isinstance(target, tuple):
        raise CriterionExprError("kind 'nested_surfaces' needs a scalar target")
    rho_hi = float(np.hypot(max(abs(v) for v in spec.sample_box["x"]), max(abs(v) for v in spec.sample_box["y"])))
    z_lo, z_hi = spec.sample_box["z"]
    dof = [float(fixed[d.name]) if d.name in fixed else (d.low + d.high) / 2 for d in spec.degrees_of_freedom]
    fn = sympy.lambdify(arg_syms, target, "numpy")

    def psi_at(rho, z, phi):
        rho, z = np.asarray(rho, dtype=float), np.asarray(z, dtype=float)
        with np.errstate(all="ignore"):
            v = np.asarray(fn(rho * np.cos(phi), rho * np.sin(phi), z, *(np.full_like(rho, d) for d in dof)))
        v = np.broadcast_to(v, rho.shape)
        return np.where(np.isfinite(v) & (np.abs(v.imag if np.iscomplexobj(v) else 0) < 1e-12), v.real if np.iscomplexobj(v) else v, np.nan)

    n_rays = n_bad = 0
    first_bad = None
    rr, zz = np.meshgrid(np.linspace(0.05, rho_hi, _NEST_GRID), np.linspace(z_lo, z_hi, _NEST_GRID))
    for phi in _NEST_PHIS:
        grid = psi_at(rr, zz, phi)
        if int(np.isfinite(grid).sum()) < _MIN_VALID:
            return _too_few(criterion, int(np.isfinite(grid).sum()))
        iz, ir = np.unravel_index(int(np.nanargmin(grid)), grid.shape)
        r0, z0 = float(rr[iz, ir]), float(zz[iz, ir])
        from scipy.optimize import minimize  # refine the coarse grid minimum to the true axis
        res = minimize(
            lambda u: float(np.nan_to_num(psi_at(np.array([u[0]]), np.array([u[1]]), phi)[0], nan=1e300)),
            [r0, z0], method="Nelder-Mead", options={"xatol": 1e-9, "fatol": 1e-14},
        )
        if 0.05 <= res.x[0] <= rho_hi and z_lo <= res.x[1] <= z_hi:
            r0, z0 = float(res.x[0]), float(res.x[1])
        for k in range(_NEST_RAYS):
            ang = k * 2 * np.pi / _NEST_RAYS
            dr, dz = np.cos(ang), np.sin(ang)
            reach = min(
                ((rho_hi - r0) / dr) if dr > 1e-12 else ((r0 - 0.05) / -dr) if dr < -1e-12 else np.inf,
                ((z_hi - z0) / dz) if dz > 1e-12 else ((z0 - z_lo) / -dz) if dz < -1e-12 else np.inf,
            )
            if not np.isfinite(reach) or reach <= 1e-9:
                continue                       # the minimum sits on the box edge in this direction
            t = np.linspace(0.0, reach, _NEST_RAY_POINTS)
            vals = psi_at(r0 + t * dr, z0 + t * dz, phi)
            vals = vals[: int(np.argmax(~np.isfinite(vals)))] if not np.isfinite(vals).all() else vals
            if vals.size < 3:
                return _result(criterion, "error", detail="psi undefined along a ray from its minimum")
            # Allowed: psi rises out of the axis, then may peak and fall to the end of its domain
            # (published equilibria are only defined on the toroidal region). A FALL FOLLOWED BY A
            # RISE is a second well / ridge: the surfaces are not nested.
            span = float(np.max(vals) - np.min(vals))
            tol = _NEST_DECREASE_TOL * (1.0 + float(np.max(np.abs(vals)))) + _NEST_RELATIVE_TOL * span
            diffs = np.diff(vals)
            fell = np.flatnonzero(diffs < -tol)
            n_rays += 1
            if fell.size and np.any(diffs[fell[0]:] > tol):
                n_bad += 1
                first_bad = first_bad or (
                    f"phi={phi:.2f}, ray angle={ang:.2f}: psi falls then rises again (a second well or ridge)"
                )
            elif vals[0] > float(np.min(vals)) + tol and fell.size and fell[0] == 0:
                n_bad += 1                      # the 'axis' is not the minimum along this ray
                first_bad = first_bad or f"phi={phi:.2f}, ray angle={ang:.2f}: psi falls immediately from its minimum"
    if n_rays == 0:
        return _result(criterion, "error", detail="no usable rays from the psi minimum")
    return _result(criterion, "pass" if n_bad == 0 else "fail", n_rays=n_rays, n_bad_rays=n_bad,
                   **({"detail": first_bad} if first_bad else {}))


def _check_numeric(criterion, env, arg_syms, arrays, spec=None, fixed=None):
    target = env.get(criterion.target)
    if target is None:
        # a derived quantity written in the criterion language, e.g. "curl(u)"
        try:
            target = evaluate_expr(criterion.target, env)
        except CriterionExprError as e:
            raise CriterionExprError(f"unknown target {criterion.target!r}: {e}") from e
    if criterion.kind == "nested_surfaces":
        return _check_nested(criterion, target, arg_syms, spec, fixed or {})

    if criterion.kind == "nonzero":
        comps = list(target) if isinstance(target, tuple) else [target]
        arrs = _evaluate(comps, arg_syms, arrays)
        mask = _valid_mask(arrs)
        n_valid = int(mask.sum())
        if n_valid < _MIN_VALID:
            return _too_few(criterion, n_valid)
        peak = float(max(np.abs(a[mask]).max() for a in arrs))
        return _result(criterion, "pass" if peak > _CONSTANT_TOLERANCE else "fail", n_valid=n_valid, value=peak)

    if criterion.kind in ("nonnegative", "nonconstant"):
        if isinstance(target, tuple):
            raise CriterionExprError(f"kind {criterion.kind!r} needs a scalar target")
        (vals,) = _evaluate([target], arg_syms, arrays)
        mask = np.isfinite(vals)
        n_valid = int(mask.sum())
        if n_valid < _MIN_VALID:
            return _too_few(criterion, n_valid)
        if criterion.kind == "nonnegative":
            low = float(vals[mask].min())
            return _result(criterion, "pass" if low >= -_NONNEGATIVE_SLACK else "fail",
                           n_valid=n_valid, value=low)
        spread = float(vals[mask].max() - vals[mask].min())
        return _result(criterion, "pass" if spread > _CONSTANT_TOLERANCE else "fail",
                       n_valid=n_valid, value=spread)

    # axisymmetry_breaking: the field must NOT be rotation-symmetric about ANY vertical axis.
    if not isinstance(target, tuple):
        raise CriterionExprError("kind 'axisymmetry_breaking' needs a vector target")
    dev, center, n_valid = axisymmetry_deviation(target, arg_syms, arrays)
    if n_valid < _MIN_VALID:
        return _too_few(criterion, n_valid)
    return _result(criterion, "pass" if dev > _BREAK_TOLERANCE else "fail",
                   n_valid=n_valid, value=float(dev), best_axis_xy=[float(center[0]), float(center[1])])


def axisymmetry_deviation(target, arg_syms, arrays):
    """(deviation, centre, n_valid): the smallest max-deviation of B(R p) from R B(p) over
    rotations R by _ROTATION_ANGLE about a vertical axis through (cx, cy), minimised over the
    centre. ~0 means axisymmetric about SOME vertical axis. Testing only the z-axis let a field
    pass as 'non-axisymmetric' just because its axis was translated (a live false CONSTRUCTED)."""
    from scipy.optimize import minimize

    c, s = np.cos(_ROTATION_ANGLE), np.sin(_ROTATION_ANGLE)
    x, y = arrays[0], arrays[1]
    fn = sympy.lambdify(arg_syms, list(target), "numpy", cse=True)

    def fields(xx, yy, rest):
        with np.errstate(all="ignore"):
            out = fn(xx, yy, *rest)
        return [np.broadcast_to(np.asarray(v, dtype=float), xx.shape) for v in out]

    def deviation(center, idx=slice(None), reduce_max=True):
        cx, cy = center
        xs, ys, rest = x[idx], y[idx], [a[idx] for a in arrays[2:]]
        rx = cx + c * (xs - cx) - s * (ys - cy)
        ry = cy + s * (xs - cx) + c * (ys - cy)
        bx, by, bz = fields(xs, ys, rest)
        qx, qy, qz = fields(rx, ry, rest)
        ok = np.all([np.isfinite(t) for t in (bx, by, bz, qx, qy, qz)], axis=0)
        d = np.maximum.reduce([np.abs(qx - (c * bx - s * by)), np.abs(qy - (s * bx + c * by)), np.abs(qz - bz)])
        if not ok.any():
            return float("inf"), 0
        return (float(d[ok].max()) if reduce_max else float(np.sqrt(np.mean(d[ok] ** 2)))), int(ok.sum())

    sub = slice(0, min(len(x), 1500))
    best = (float("inf"), (0.0, 0.0))
    for start in [(0.0, 0.0), (0.3, 0.0), (-0.3, 0.0), (0.0, 0.3), (0.0, -0.3), (0.6, 0.6), (-0.6, -0.6)]:
        res = minimize(lambda u: deviation(tuple(u), sub, False)[0], start, method="Nelder-Mead",
                       options={"xatol": 1e-6, "fatol": 1e-12, "maxiter": 200})
        if res.fun < best[0]:
            best = (float(res.fun), tuple(float(v) for v in res.x))
    dev, n_valid = deviation(best[1])
    z_dev, _ = deviation((0.0, 0.0))
    if z_dev <= dev:                       # never report a worse centre than the plain z-axis
        return z_dev, (0.0, 0.0), n_valid
    return dev, best[1], n_valid


async def VectorCalculusCheckTransform(
    input: dict[str, Any], config: dict[str, Any], ctx: SessionContext
) -> dict[str, Any]:
    spec = load_construct_spec(config["spec_path"])
    source = config.get("source", "Generator_A")
    tolerance = float(config.get("tolerance", _DEFAULT_TOLERANCE))
    seed = int(config.get("seed", _SEED))
    candidate = _load_candidate(input, source)

    checkable = [c for c in spec.criteria if c.check in _CHECKABLE]
    dof_names = [d.name for d in spec.degrees_of_freedom]
    base_out = {
        "n_draws": _N_DRAWS, "seed": seed,
        "_model": "none", "_provider": "none", "_input_tokens": 0, "_output_tokens": 0,
    }

    try:
        env = _resolve_env(candidate, dof_names, spec.unknowns or _DEFAULT_UNKNOWNS)
    except (_CandidateError, UnsafeExpressionError) as e:
        return {
            "results": [_result(c, "error", detail=f"candidate rejected: {e}") for c in checkable],
            **base_out,
        }

    fixed = candidate.get("params") if isinstance(candidate.get("params"), dict) else {}
    arg_syms = [*COORDS, *(sympy.Symbol(n) for n in dof_names)]
    arrays = _sample(spec, fixed, np.random.default_rng(seed))

    results = []
    for c in checkable:
        try:
            if c.check == "numeric_sample":
                results.append(_check_numeric(c, env, arg_syms, arrays, spec, fixed))
            else:
                results.append(_check_gate(c, env, arg_syms, arrays, tolerance))
        except CriterionExprError as e:
            results.append(_result(c, "error", detail=f"criterion rejected: {e}"))
    return {"results": results, **base_out}