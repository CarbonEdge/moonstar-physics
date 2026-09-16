"""IdentityCheckTransform — verifies a claimed lhs == rhs identity via
symbolic simplification, falling back to numeric sampling only to avoid
false positives when symbolic simplification doesn't reduce a genuinely
true identity to exactly 0 (e.g. identities that need a real-domain
assumption sympy's default simplify doesn't apply to a bare Symbol).

Numeric agreement never upgrades a result to "consistent" — 5 sample
points is suggestive, not proof. It only prevents a symbolic-simplify
miss from being reported as a false "violated".
"""
from __future__ import annotations

import random
from typing import Any

import sympy
from .._compat import SessionContext
from .._parsing import parse_extractor_output

from ._safe_parse import UnsafeExpressionError, safe_parse_expr

_NUMERIC_SAMPLES = 5
_SAMPLE_RANGE = 10
_NUMERIC_TOLERANCE = 1e-9
_RANDOM_SEED = 42


def _numeric_disagreement(diff: sympy.Expr, free_symbols: list[sympy.Symbol]) -> bool | None:
    """Returns True if a sampled point disagrees (diff != 0), False if all
    sampled points agree, None if no point could be evaluated at all."""
    if not free_symbols:
        try:
            value = complex(diff.evalf())
        except (TypeError, ValueError):
            return None
        return abs(value) > _NUMERIC_TOLERANCE

    rng = random.Random(_RANDOM_SEED)
    evaluated_any = False
    for _ in range(_NUMERIC_SAMPLES):
        point = {
            sym: sympy.Rational(rng.randint(-_SAMPLE_RANGE * 10, _SAMPLE_RANGE * 10), 10)
            for sym in free_symbols
        }
        try:
            value = complex(diff.evalf(subs=point))
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if value != value:  # NaN
            continue
        evaluated_any = True
        if abs(value) > _NUMERIC_TOLERANCE:
            return True
    return False if evaluated_any else None


async def IdentityCheckTransform(
    input: dict[str, Any], config: dict[str, Any], ctx: SessionContext
) -> dict[str, Any]:
    parsed = parse_extractor_output(input)

    def _not_applicable(detail: str) -> dict[str, Any]:
        return {
            "verdict": "not_applicable",
            "detail": detail,
            "_model": "none",
            "_provider": "none",
            "_input_tokens": 0,
            "_output_tokens": 0,
        }

    if parsed.get("claim_type") != "identity":
        return _not_applicable("claim_type is not 'identity'")

    claim = parsed.get("identity_claim") or {}
    lhs_text = claim.get("lhs")
    rhs_text = claim.get("rhs")
    variables = claim.get("variables") or []

    if not lhs_text or not rhs_text:
        return _not_applicable("identity_claim.lhs and .rhs are both required")

    try:
        lhs = safe_parse_expr(lhs_text, variables)
        rhs = safe_parse_expr(rhs_text, variables)
    except UnsafeExpressionError as e:
        return _not_applicable(f"expression rejected: {e}")

    diff = sympy.simplify(lhs - rhs)

    base: dict[str, Any] = {
        "lhs": lhs_text,
        "rhs": rhs_text,
        "diff": str(diff),
        "_model": "none",
        "_provider": "none",
        "_input_tokens": 0,
        "_output_tokens": 0,
    }

    if diff == 0:
        return {**base, "verdict": "consistent"}

    free_symbols = sorted(diff.free_symbols, key=str)
    disagreement = _numeric_disagreement(diff, free_symbols)

    if disagreement is True:
        return {**base, "verdict": "violated"}
    if disagreement is False:
        return {
            **base,
            "verdict": "not_applicable",
            "detail": "symbolic diff was nonzero but numeric sampling found no disagreement",
        }
    return {
        **base,
        "verdict": "not_applicable",
        "detail": "symbolic diff was nonzero but numeric sampling could not evaluate any point",
    }
