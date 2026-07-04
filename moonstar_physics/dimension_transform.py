"""DimensionConsistencyTransform — checks dimension-counting claims common in
unification-theory papers: fiber-bundle total-space dimensions and Spin(n)
spinor representation dimensions, using a closed set of known formulas.

Not a general Lie-theory or symbolic-geometry engine — v1 deliberately covers
only the two claim types and four fiber_kind formulas below. Anything else
returns verdict="not_applicable" rather than a wrong answer, matching
QMCalculationTransform's philosophy.
"""
from __future__ import annotations

import math
from typing import Any

from moonstar_core import SessionContext
from moonstar_core.exceptions import NonRetryableTransformError

from ._parsing import parse_extractor_output

_MAX_DIMENSION = 1000  # generous ceiling for any real spacetime/representation dimension claim


def _safe_int(value: Any, allow_zero: bool = True) -> int | None:
    """Safely convert a value to a bounded non-negative int.

    The magnitude cap matters specifically because 2**(n // 2) is exact
    big-integer exponentiation with no float-overflow ceiling to catch — an
    unbounded n would hang/exhaust memory rather than raise a catchable
    exception, unlike the float arithmetic in qm_calc_transform.py.
    """
    if value is None:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    try:
        result = int(value)
    except (ValueError, TypeError, OverflowError):
        return None
    if not allow_zero and result == 0:
        return None
    if result < 0 or result > _MAX_DIMENSION:
        return None
    return result


def _spinor_dimension(n: int) -> int:
    return 2 ** (n // 2)


_FIBER_KINDS: dict[str, Any] = {
    "vector": lambda n: n,
    "symmetric_bilinear_form": lambda n: n * (n + 1) // 2,
    "antisymmetric_bilinear_form": lambda n: n * (n - 1) // 2,
    "spinor": _spinor_dimension,
}


def _check_fiber_bundle(entry: dict[str, Any]) -> dict[str, Any] | None:
    base_dimension = _safe_int(entry.get("base_dimension"))
    fiber_base_dimension = _safe_int(entry.get("fiber_base_dimension"))
    claimed_dimension = _safe_int(entry.get("claimed_dimension"))
    fiber_kind = entry.get("fiber_kind")

    if base_dimension is None or fiber_base_dimension is None or claimed_dimension is None:
        return None
    formula = _FIBER_KINDS.get(fiber_kind)
    if formula is None:
        return None

    computed = base_dimension + formula(fiber_base_dimension)
    return {
        "object": entry.get("object", "<unnamed>"),
        "claim_type": "fiber_bundle",
        "computed_dimension": computed,
        "claimed_dimension": claimed_dimension,
        "verdict": "consistent" if computed == claimed_dimension else "violated",
    }


def _check_spinor_representation(entry: dict[str, Any]) -> dict[str, Any] | None:
    n = _safe_int(entry.get("n"))
    claimed_dimension = _safe_int(entry.get("claimed_dimension"))
    if n is None or claimed_dimension is None:
        return None

    computed = _spinor_dimension(n)
    return {
        "object": entry.get("object", "<unnamed>"),
        "claim_type": "spinor_representation",
        "computed_dimension": computed,
        "claimed_dimension": claimed_dimension,
        "verdict": "consistent" if computed == claimed_dimension else "violated",
    }


_CHECKERS = {
    "fiber_bundle": _check_fiber_bundle,
    "spinor_representation": _check_spinor_representation,
}


async def DimensionConsistencyTransform(
    input: dict[str, Any], config: dict[str, Any], ctx: SessionContext
) -> dict[str, Any]:
    parsed = parse_extractor_output(input)
    claims = parsed.get("dimension_claims")

    def _not_applicable(detail: str) -> dict[str, Any]:
        return {
            "checked": [],
            "results": [],
            "verdict": "not_applicable",
            "detail": detail,
            "_model": "none",
            "_provider": "none",
            "_input_tokens": 0,
            "_output_tokens": 0,
        }

    if claims is None:
        return _not_applicable("no dimension_claims provided")
    if not isinstance(claims, list):
        raise NonRetryableTransformError(
            f"Extractor's 'dimension_claims' must be a list, got {type(claims).__name__}"
        )
    if not claims:
        return _not_applicable("dimension_claims was an empty list")

    results: list[dict[str, Any]] = []
    for entry in claims:
        if not isinstance(entry, dict):
            continue
        checker = _CHECKERS.get(entry.get("claim_type"))
        if checker is None:
            continue
        result = checker(entry)
        if result is not None:
            results.append(result)

    if not results:
        return _not_applicable("no recognized/well-formed dimension claims among the provided entries")

    verdict = "violated" if any(r["verdict"] == "violated" for r in results) else "consistent"

    return {
        "checked": [r["object"] for r in results],
        "results": results,
        "verdict": verdict,
        "_model": "none",
        "_provider": "none",
        "_input_tokens": 0,
        "_output_tokens": 0,
    }
