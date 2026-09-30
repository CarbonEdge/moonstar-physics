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


def _resolve_candidate(candidate: dict[str, Any], dof_names: list[str]):
    """Returns (B, psi, p) as sympy objects in terms of x, y, z and the DOF symbols."""
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

    b_raw = objects.get("B")
    if not (isinstance(b_raw, list) and len(b_raw) == 3):
        raise _CandidateError("objects.B must be a list of exactly 3 expression strings")
    B = tuple(parse(t) for t in b_raw)
    psi = parse(objects.get("psi"))
    p = parse(objects.get("p"), ("psi",)).subs(sympy.Symbol("psi"), psi)

    allowed = {sympy.Symbol(n) for n in base}
    for label, expr in [("B[0]", B[0]), ("B[1]", B[1]), ("B[2]", B[2]), ("psi", psi), ("p", p)]:
        extra = expr.free_symbols - allowed
        if extra:
            raise _CandidateError(
                f"{label} has unresolved symbol(s) {sorted(str(s) for s in extra)}"
            )
    return B, psi, p


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


def _check_numeric(criterion, env, arg_syms, arrays):
    target = env.get(criterion.target)
    if target is None:
        raise CriterionExprError(f"unknown target {criterion.target!r}")

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

    # axisymmetry_breaking: compare B(R p) with R B(p) for a rotation R about z.
    if not isinstance(target, tuple):
        raise CriterionExprError("kind 'axisymmetry_breaking' needs a vector target")
    c, s = np.cos(_ROTATION_ANGLE), np.sin(_ROTATION_ANGLE)
    x, y = arrays[0], arrays[1]
    rotated = [c * x - s * y, s * x + c * y, *arrays[2:]]
    bx, by, bz = _evaluate(list(target), arg_syms, arrays)
    rx, ry, rz = _evaluate(list(target), arg_syms, rotated)
    mask = _valid_mask([bx, by, bz, rx, ry, rz])
    n_valid = int(mask.sum())
    if n_valid < _MIN_VALID:
        return _too_few(criterion, n_valid)
    dev = np.maximum.reduce([
        np.abs(rx - (c * bx - s * by)), np.abs(ry - (s * bx + c * by)), np.abs(rz - bz),
    ])[mask].max()
    return _result(criterion, "pass" if dev > _BREAK_TOLERANCE else "fail",
                   n_valid=n_valid, value=float(dev))


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
        B, psi, p = _resolve_candidate(candidate, dof_names)
    except (_CandidateError, UnsafeExpressionError) as e:
        return {
            "results": [_result(c, "error", detail=f"candidate rejected: {e}") for c in checkable],
            **base_out,
        }

    fixed = candidate.get("params") if isinstance(candidate.get("params"), dict) else {}
    arg_syms = [*COORDS, *(sympy.Symbol(n) for n in dof_names)]
    arrays = _sample(spec, fixed, np.random.default_rng(seed))
    env = {"B": B, "psi": psi, "p": p}

    results = []
    for c in checkable:
        try:
            if c.check == "numeric_sample":
                results.append(_check_numeric(c, env, arg_syms, arrays))
            else:
                results.append(_check_gate(c, env, arg_syms, arrays, tolerance))
        except CriterionExprError as e:
            results.append(_result(c, "error", detail=f"criterion rejected: {e}"))
    return {"results": results, **base_out}