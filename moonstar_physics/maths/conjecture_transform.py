"""ConjectureCheckTransform — fixed dispatch table keyed by conjecture_type,
same shape as QMCalculationTransform's _CALCULATORS dict in moonstar-physics.
A type outside the table returns not_applicable, never a guessed verdict.
"""
from __future__ import annotations

from typing import Any

import sympy
from .._compat import SessionContext
from .._parsing import parse_extractor_output

from ._safe_parse import UnsafeExpressionError, safe_parse_expr

_DIOPHANTINE_MAX_VARIABLES = 2
_DIOPHANTINE_BOUND_CAP = 1000
_SEQUENCE_RELATIVE_TOLERANCE = 0.05


def _check_primality(claim: dict[str, Any]) -> dict[str, Any] | None:
    n = claim.get("n")
    claimed_value = claim.get("claimed_value")
    if n is None or claimed_value is None:
        return None
    try:
        n_int = int(n)
    except (TypeError, ValueError):
        return None

    computed = sympy.isprime(n_int)
    claimed_bool = bool(claimed_value)
    return {
        "conjecture_type": "primality",
        "computed": computed,
        "claimed": claimed_bool,
        "verdict": "consistent" if computed == claimed_bool else "violated",
    }


def _check_diophantine(claim: dict[str, Any]) -> dict[str, Any] | None:
    equation_text = claim.get("equation")
    variables = claim.get("variables") or []
    if not equation_text or not variables:
        return None

    if len(variables) > _DIOPHANTINE_MAX_VARIABLES:
        return {
            "conjecture_type": "diophantine",
            "computed": None,
            "claimed": claim.get("claimed_value"),
            "verdict": "not_applicable",
            "detail": (
                f"{len(variables)} variables exceeds the "
                f"{_DIOPHANTINE_MAX_VARIABLES}-variable bounded-search cap"
            ),
        }

    requested_bound = claim.get("bound")
    bound = _DIOPHANTINE_BOUND_CAP if requested_bound is None else min(int(requested_bound), _DIOPHANTINE_BOUND_CAP)

    try:
        equation = safe_parse_expr(equation_text, variables)
    except UnsafeExpressionError as e:
        return {
            "conjecture_type": "diophantine",
            "computed": None,
            "claimed": claim.get("claimed_value"),
            "verdict": "not_applicable",
            "detail": f"expression rejected: {e}",
        }

    symbols = [sympy.Symbol(v) for v in variables]
    f = sympy.lambdify(symbols, equation, modules="math")

    solution: list[int] | None = None
    if len(symbols) == 1:
        for a in range(-bound, bound + 1):
            try:
                if f(a) == 0:
                    solution = [a]
                    break
            except (ValueError, ZeroDivisionError, OverflowError):
                continue
    else:
        for a in range(-bound, bound + 1):
            for b in range(-bound, bound + 1):
                try:
                    if f(a, b) == 0:
                        solution = [a, b]
                        break
                except (ValueError, ZeroDivisionError, OverflowError):
                    continue
            if solution is not None:
                break

    claimed_value = claim.get("claimed_value")
    claimed_exists = True if claimed_value is None else bool(claimed_value)

    if solution is None:
        return {
            "conjecture_type": "diophantine",
            "computed": None,
            "claimed": claimed_value,
            "verdict": "not_applicable",
            "detail": f"no solution found within bound={bound} for {len(symbols)} variable(s)",
        }

    computed_exists = True
    return {
        "conjecture_type": "diophantine",
        "computed": solution,
        "claimed": claimed_value,
        "verdict": "consistent" if computed_exists == claimed_exists else "violated",
    }


def _check_sequence_formula(claim: dict[str, Any]) -> dict[str, Any] | None:
    formula_text = claim.get("formula")
    index = claim.get("index")
    claimed_value = claim.get("claimed_value")
    if not formula_text or index is None or claimed_value is None:
        return None

    variables = claim.get("variables") or ["n"]
    try:
        formula = safe_parse_expr(formula_text, variables)
    except UnsafeExpressionError as e:
        return {
            "conjecture_type": "sequence_formula",
            "computed": None,
            "claimed": claimed_value,
            "verdict": "not_applicable",
            "detail": f"expression rejected: {e}",
        }

    index_symbol = sympy.Symbol(variables[0])
    try:
        computed = complex(formula.evalf(subs={index_symbol: index}))
    except (TypeError, ValueError):
        return {
            "conjecture_type": "sequence_formula",
            "computed": None,
            "claimed": claimed_value,
            "verdict": "not_applicable",
            "detail": "formula could not be evaluated at the given index",
        }

    if abs(computed.imag) > 1e-9:
        return {
            "conjecture_type": "sequence_formula",
            "computed": None,
            "claimed": claimed_value,
            "verdict": "not_applicable",
            "detail": "formula evaluated to a non-real value",
        }

    computed_real = computed.real

    if isinstance(claimed_value, int) and not isinstance(claimed_value, bool):
        is_match = round(computed_real) == claimed_value and abs(computed_real - claimed_value) < 1e-6
    else:
        tolerance = abs(computed_real) * _SEQUENCE_RELATIVE_TOLERANCE + 1e-12
        is_match = abs(computed_real - float(claimed_value)) <= tolerance

    return {
        "conjecture_type": "sequence_formula",
        "computed": computed_real,
        "claimed": claimed_value,
        "verdict": "consistent" if is_match else "violated",
    }


_CHECKERS = {
    "primality": _check_primality,
    "diophantine": _check_diophantine,
    "sequence_formula": _check_sequence_formula,
}


async def ConjectureCheckTransform(
    input: dict[str, Any], config: dict[str, Any], ctx: SessionContext
) -> dict[str, Any]:
    parsed = parse_extractor_output(input)

    def _not_applicable(detail: str) -> dict[str, Any]:
        return {
            "conjecture_type": None,
            "computed": None,
            "claimed": None,
            "verdict": "not_applicable",
            "detail": detail,
            "_model": "none",
            "_provider": "none",
            "_input_tokens": 0,
            "_output_tokens": 0,
        }

    if parsed.get("claim_type") != "conjecture":
        return _not_applicable("claim_type is not 'conjecture'")

    claim = parsed.get("conjecture_claim") or {}
    conjecture_type = claim.get("conjecture_type")
    checker = _CHECKERS.get(conjecture_type)
    if checker is None:
        return _not_applicable(f"no checker for conjecture_type {conjecture_type!r}")

    result = checker(claim)
    if result is None:
        return _not_applicable(f"required fields missing for conjecture_type {conjecture_type!r}")

    return {
        **result,
        "_model": "none",
        "_provider": "none",
        "_input_tokens": 0,
        "_output_tokens": 0,
    }
