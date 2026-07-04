"""QMCalculationTransform — closed-form calculations for a fixed set of
solvable QM systems: infinite square well, quantum harmonic oscillator,
hydrogen-like energy levels, and the position-momentum uncertainty bound.

Not a general QM solver — v1 deliberately covers only textbook closed-form
cases. Anything else returns verdict="not_applicable" rather than a wrong
answer.
"""
from __future__ import annotations

import math
from typing import Any

from moonstar_core import SessionContext

from ._parsing import parse_extractor_output

_HBAR = 1.054571817e-34  # J*s
_EV_TO_JOULE = 1.602176634e-19
_ELECTRON_MASS_KG = 9.1093837015e-31
_PROTON_MASS_KG = 1.67262192369e-27
_HYDROGEN_GROUND_STATE_EV = -13.605693


def _mass_kg(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            mass = float(value)
        except (ValueError, TypeError, OverflowError):
            return None
        if not math.isfinite(mass):
            return None
        if mass == 0:
            return None
        return mass
    if value == "electron":
        return _ELECTRON_MASS_KG
    if value == "proton":
        return _PROTON_MASS_KG
    return None


def _safe_float(value: Any, allow_zero: bool = True) -> float | None:
    """Safely convert a value to float.

    Returns None if:
    - value is None
    - conversion fails (ValueError/TypeError)
    - zero when not allowed
    - value is NaN or Infinity
    """
    if value is None:
        return None
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    if not math.isfinite(result):
        return None
    if not allow_zero and result == 0:
        return None
    return result


def _safe_int(value: Any, allow_zero: bool = True) -> int | None:
    """Safely convert a value to int.

    Returns None if:
    - value is None
    - conversion fails (ValueError/TypeError)
    - zero when not allowed
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
    return result


def _infinite_well_energy_ev(params: dict[str, Any]) -> float | None:
    width_nm = _safe_float(params.get("width_nm"), allow_zero=False)
    n = _safe_int(params.get("n", 1), allow_zero=False)
    mass_kg = _mass_kg(params.get("mass", "electron"))
    if width_nm is None or n is None or mass_kg is None:
        return None
    try:
        width_m = width_nm * 1e-9
        energy_j = (n**2) * (math.pi**2) * (_HBAR**2) / (2 * mass_kg * width_m**2)
        result = energy_j / _EV_TO_JOULE
    except (OverflowError, ZeroDivisionError, ValueError, ArithmeticError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _harmonic_oscillator_energy_ev(params: dict[str, Any]) -> float | None:
    omega = _safe_float(params.get("omega_rad_s"), allow_zero=False)
    n = _safe_int(params.get("n", 0), allow_zero=True)
    if omega is None or n is None:
        return None
    try:
        energy_j = _HBAR * omega * (n + 0.5)
        result = energy_j / _EV_TO_JOULE
    except (OverflowError, ZeroDivisionError, ValueError, ArithmeticError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _hydrogen_energy_ev(params: dict[str, Any]) -> float | None:
    n = _safe_int(params.get("n"), allow_zero=False)
    if n is None:
        return None
    try:
        result = _HYDROGEN_GROUND_STATE_EV / (n ** 2)
    except (OverflowError, ZeroDivisionError, ValueError, ArithmeticError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _uncertainty_min_momentum(params: dict[str, Any]) -> float | None:
    delta_x_m = _safe_float(params.get("delta_x_m"), allow_zero=False)
    if delta_x_m is None:
        return None
    try:
        result = _HBAR / (2.0 * delta_x_m)
    except (OverflowError, ZeroDivisionError, ValueError, ArithmeticError):
        return None
    if not math.isfinite(result):
        return None
    return result


# Maps system type -> (claimed_values key to compare against, calculator fn)
_CALCULATORS: dict[str, tuple[str, Any]] = {
    "infinite_well": ("energy_ev", _infinite_well_energy_ev),
    "harmonic_oscillator": ("energy_ev", _harmonic_oscillator_energy_ev),
    "hydrogen_energy_level": ("energy_ev", _hydrogen_energy_ev),
    "uncertainty_bound": ("delta_p_min_kg_m_s", _uncertainty_min_momentum),
}

_RELATIVE_TOLERANCE = 0.05


async def QMCalculationTransform(
    input: dict[str, Any], config: dict[str, Any], ctx: SessionContext
) -> dict[str, Any]:
    parsed = parse_extractor_output(input)
    system_params = parsed.get("system_params") or {}
    if not isinstance(system_params, dict):
        system_params = {}
    system_type = system_params.get("type")
    system_type_is_valid_key = isinstance(system_type, str)

    def _result(computed, claimed, verdict, detail=None) -> dict[str, Any]:
        out: dict[str, Any] = {
            "system_type": system_type,
            "result_key": (
                _CALCULATORS[system_type][0]
                if system_type_is_valid_key and system_type in _CALCULATORS
                else None
            ),
            "computed": computed,
            "claimed": claimed,
            "verdict": verdict,
            "_model": "none",
            "_provider": "none",
            "_input_tokens": 0,
            "_output_tokens": 0,
        }
        if detail is not None:
            out["detail"] = detail
        return out

    if not system_type_is_valid_key or system_type not in _CALCULATORS:
        return _result(None, None, "not_applicable", f"no calculator for system type {system_type!r}")

    result_key, calculator = _CALCULATORS[system_type]
    computed = calculator(system_params)

    if computed is None:
        return _result(None, None, "not_applicable", "required parameters missing for this system type")

    claimed_values = parsed.get("claimed_values") or {}
    if not isinstance(claimed_values, dict):
        claimed_values = {}
    claimed = claimed_values.get(result_key)

    if claimed is None:
        return _result(computed, None, "not_applicable", "no claimed value provided to compare against")

    claimed_float = _safe_float(claimed, allow_zero=True)
    if claimed_float is None:
        return _result(computed, claimed, "not_applicable", f"claimed value {claimed!r} is not numeric")

    tolerance = abs(computed) * _RELATIVE_TOLERANCE + 1e-12
    verdict = "consistent" if abs(claimed_float - computed) <= tolerance else "violated"
    return _result(computed, claimed, verdict)
