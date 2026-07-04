"""Tests for QMCalculationTransform — checked against known closed-form QM results."""
from __future__ import annotations

import json
import math
from unittest.mock import AsyncMock

import pytest
from moonstar_core import SessionContext

from moonstar_physics.qm_calc_transform import QMCalculationTransform


@pytest.fixture
def ctx() -> AsyncMock:
    return AsyncMock(spec=SessionContext)


def _extractor_input(payload: dict) -> dict:
    return {"Extractor": {"response": json.dumps(payload)}}


async def test_infinite_well_electron_1nm_ground_state(ctx):
    """Textbook result: electron in a 1nm infinite well, n=1, is ~0.376 eV."""
    payload = {
        "system_params": {"type": "infinite_well", "width_nm": 1.0, "mass": "electron", "n": 1},
        "claimed_values": {"energy_ev": 0.376},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["system_type"] == "infinite_well"
    assert result["computed"] == pytest.approx(0.376, rel=1e-2)
    assert result["verdict"] == "consistent"


async def test_hydrogen_ground_state_energy(ctx):
    payload = {
        "system_params": {"type": "hydrogen_energy_level", "n": 1},
        "claimed_values": {"energy_ev": -13.6},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["computed"] == pytest.approx(-13.605693, rel=1e-3)
    assert result["verdict"] == "consistent"


async def test_hydrogen_second_level_energy(ctx):
    payload = {"system_params": {"type": "hydrogen_energy_level", "n": 2}}
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["computed"] == pytest.approx(-3.4014, rel=1e-3)
    assert result["verdict"] == "not_applicable"  # no claimed_values given to compare


async def test_claimed_value_mismatch_is_violated(ctx):
    payload = {
        "system_params": {"type": "hydrogen_energy_level", "n": 1},
        "claimed_values": {"energy_ev": -1.0},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "violated"


async def test_harmonic_oscillator_ground_state(ctx):
    hbar = 1.054571817e-34
    omega = 1.0e14
    expected_ev = (hbar * omega * 0.5) / 1.602176634e-19
    payload = {"system_params": {"type": "harmonic_oscillator", "omega_rad_s": omega, "n": 0}}
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["computed"] == pytest.approx(expected_ev, rel=1e-6)


async def test_uncertainty_bound(ctx):
    hbar = 1.054571817e-34
    delta_x = 1e-10
    expected = hbar / (2 * delta_x)
    payload = {"system_params": {"type": "uncertainty_bound", "delta_x_m": delta_x}}
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["computed"] == pytest.approx(expected, rel=1e-9)
    assert result["result_key"] == "delta_p_min_kg_m_s"


async def test_unrecognized_system_type_is_not_applicable(ctx):
    payload = {"system_params": {"type": "quantum_tunneling_through_a_wall"}}
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_missing_system_params_is_not_applicable(ctx):
    payload = {"hypothesis_type": "decay"}
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_missing_required_param_is_not_applicable(ctx):
    payload = {"system_params": {"type": "infinite_well", "n": 1}}  # no width_nm
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_infinite_well_non_numeric_width_is_not_applicable(ctx):
    """Non-numeric width should return not_applicable, not raise ValueError."""
    payload = {
        "system_params": {"type": "infinite_well", "width_nm": "1 nm", "mass": "electron", "n": 1},
        "claimed_values": {"energy_ev": 0.376},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["computed"] is None


async def test_infinite_well_zero_width_is_not_applicable(ctx):
    """Zero width should return not_applicable (division by zero), not raise ZeroDivisionError."""
    payload = {
        "system_params": {"type": "infinite_well", "width_nm": 0, "mass": "electron", "n": 1},
        "claimed_values": {"energy_ev": 0.376},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["computed"] is None


async def test_harmonic_oscillator_non_numeric_omega_is_not_applicable(ctx):
    """Non-numeric omega should return not_applicable, not raise ValueError."""
    payload = {
        "system_params": {"type": "harmonic_oscillator", "omega_rad_s": "1e14 rad/s", "n": 0},
        "claimed_values": {"energy_ev": 3.27e-21},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["computed"] is None


async def test_harmonic_oscillator_zero_omega_is_not_applicable(ctx):
    """Zero omega should return not_applicable, not raise division by zero."""
    payload = {
        "system_params": {"type": "harmonic_oscillator", "omega_rad_s": 0, "n": 0},
        "claimed_values": {"energy_ev": 0},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["computed"] is None


async def test_hydrogen_non_numeric_n_is_not_applicable(ctx):
    """Non-numeric n should return not_applicable, not raise ValueError."""
    payload = {
        "system_params": {"type": "hydrogen_energy_level", "n": "first"},
        "claimed_values": {"energy_ev": -13.6},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["computed"] is None


async def test_hydrogen_zero_n_is_not_applicable(ctx):
    """Zero n should return not_applicable (division by zero), not raise ZeroDivisionError."""
    payload = {
        "system_params": {"type": "hydrogen_energy_level", "n": 0},
        "claimed_values": {"energy_ev": -13.6},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["computed"] is None


async def test_uncertainty_non_numeric_delta_x_is_not_applicable(ctx):
    """Non-numeric delta_x_m should return not_applicable, not raise ValueError."""
    payload = {
        "system_params": {"type": "uncertainty_bound", "delta_x_m": "1e-10 m"},
        "claimed_values": {"delta_p_min_kg_m_s": 5.27e-25},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["computed"] is None


async def test_uncertainty_zero_delta_x_is_not_applicable(ctx):
    """Zero delta_x_m should return not_applicable (division by zero), not raise ZeroDivisionError."""
    payload = {
        "system_params": {"type": "uncertainty_bound", "delta_x_m": 0},
        "claimed_values": {"delta_p_min_kg_m_s": 5.27e-25},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["computed"] is None


async def test_infinite_well_non_numeric_n_is_not_applicable(ctx):
    """Non-numeric n should return not_applicable, not raise TypeError."""
    payload = {
        "system_params": {"type": "infinite_well", "width_nm": 1.0, "mass": "electron", "n": "first"},
        "claimed_values": {"energy_ev": 0.376},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["computed"] is None


async def test_infinite_well_zero_n_is_not_applicable(ctx):
    """Zero n should return not_applicable (n must be >= 1 for infinite well), not raise error."""
    payload = {
        "system_params": {"type": "infinite_well", "width_nm": 1.0, "mass": "electron", "n": 0},
        "claimed_values": {"energy_ev": 0.376},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["computed"] is None


async def test_infinite_well_zero_mass_is_not_applicable(ctx):
    """Zero mass should return not_applicable (division by zero), not raise ZeroDivisionError."""
    payload = {
        "system_params": {"type": "infinite_well", "width_nm": 1.0, "mass": 0, "n": 1},
        "claimed_values": {"energy_ev": 0.376},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["computed"] is None


async def test_harmonic_oscillator_non_numeric_n_is_not_applicable(ctx):
    """Non-numeric n should return not_applicable, not raise TypeError."""
    payload = {
        "system_params": {"type": "harmonic_oscillator", "omega_rad_s": 1.0e14, "n": "second"},
        "claimed_values": {"energy_ev": 3.27e-21},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["computed"] is None


async def test_non_numeric_claimed_value_is_not_applicable(ctx):
    """Non-numeric claimed value should return not_applicable, not raise ValueError/TypeError."""
    payload = {
        "system_params": {"type": "hydrogen_energy_level", "n": 1},
        "claimed_values": {"energy_ev": "approximately -13.6 eV"},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["computed"] is not None  # computed should still work
    assert "not numeric" in result.get("detail", "").lower()


async def test_list_claimed_value_is_not_applicable(ctx):
    """List as claimed value should return not_applicable, not raise TypeError."""
    payload = {
        "system_params": {"type": "hydrogen_energy_level", "n": 1},
        "claimed_values": {"energy_ev": [-13.6, -13.605]},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["computed"] is not None


async def test_dict_claimed_value_is_not_applicable(ctx):
    """Dict as claimed value should return not_applicable, not raise TypeError."""
    payload = {
        "system_params": {"type": "hydrogen_energy_level", "n": 1},
        "claimed_values": {"energy_ev": {"value": -13.605, "unit": "eV"}},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["computed"] is not None


async def test_bool_mass_is_not_applicable(ctx):
    """Boolean mass should return not_applicable (bool is not a valid mass), not coerce to 1."""
    payload = {
        "system_params": {"type": "infinite_well", "width_nm": 1.0, "mass": True, "n": 1},
        "claimed_values": {"energy_ev": 0.376},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["computed"] is None


async def test_nan_width_is_not_applicable(ctx):
    """NaN width should return not_applicable, not silently produce NaN result."""
    payload = {
        "system_params": {"type": "infinite_well", "width_nm": float('nan'), "mass": "electron", "n": 1},
        "claimed_values": {"energy_ev": 0.376},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["computed"] is None


async def test_infinity_width_is_not_applicable(ctx):
    """Infinity width should return not_applicable, not produce Infinity result."""
    payload = {
        "system_params": {"type": "infinite_well", "width_nm": float('inf'), "mass": "electron", "n": 1},
        "claimed_values": {"energy_ev": 0.376},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["computed"] is None


# --- Third-round defensive-pass regression tests ---
# Each case below is JSON-valid but shaped wrong relative to the expected
# schema. None of these should ever raise; all must resolve to
# verdict == "not_applicable".


async def test_oversized_n_from_json_inf_literal_is_not_applicable(ctx):
    """n parsed from a JSON literal like 1e400 becomes float('inf'); int(inf) must
    not raise an uncaught OverflowError (finding 1)."""
    payload = {
        "system_params": {"type": "hydrogen_energy_level", "n": json.loads("1e400")},
        "claimed_values": {"energy_ev": -13.6},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["computed"] is None


async def test_huge_finite_n_does_not_raise_overflow_in_arithmetic(ctx):
    """A finite-but-astronomically-large n (e.g. int(1e300)) converts fine via
    int(), but squaring/dividing it against a float downstream can raise
    OverflowError ('int too large to convert to float'). Must not raise."""
    payload = {
        "system_params": {"type": "hydrogen_energy_level", "n": 10 ** 300},
        "claimed_values": {"energy_ev": -13.6},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_huge_finite_width_does_not_raise_overflow_in_infinite_well(ctx):
    """A huge finite width_nm can overflow when squared as a float. Must not raise."""
    payload = {
        "system_params": {"type": "infinite_well", "width_nm": 1e200, "mass": "electron", "n": 1},
        "claimed_values": {"energy_ev": 0.376},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_string_system_params_is_not_applicable(ctx):
    """system_params that is JSON-valid but not a dict (a string) must not raise
    AttributeError from .get() (finding 2)."""
    payload = {"system_params": "not a dict", "claimed_values": {"energy_ev": -13.6}}
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_list_system_params_is_not_applicable(ctx):
    """system_params as a list must not raise AttributeError (finding 2)."""
    payload = {"system_params": ["type", "infinite_well"], "claimed_values": {}}
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_number_system_params_is_not_applicable(ctx):
    """system_params as a bare number must not raise AttributeError (finding 2)."""
    payload = {"system_params": 42, "claimed_values": {}}
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_bool_system_params_is_not_applicable(ctx):
    """system_params as a bare bool must not raise AttributeError (finding 2)."""
    payload = {"system_params": True, "claimed_values": {}}
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_list_type_value_is_not_applicable(ctx):
    """type being an unhashable JSON value (a list) must not raise
    TypeError: unhashable type on the `in _CALCULATORS` check (finding 3)."""
    payload = {"system_params": {"type": ["infinite_well"]}, "claimed_values": {}}
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_dict_type_value_is_not_applicable(ctx):
    """type being an unhashable JSON value (a dict) must not raise
    TypeError: unhashable type on the `in _CALCULATORS` check (finding 3)."""
    payload = {"system_params": {"type": {"nested": "value"}}, "claimed_values": {}}
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_string_claimed_values_is_not_applicable(ctx):
    """claimed_values that is JSON-valid but not a dict (a string) must not raise
    AttributeError from .get() (finding 4)."""
    payload = {
        "system_params": {"type": "hydrogen_energy_level", "n": 1},
        "claimed_values": "not a dict",
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["computed"] is not None


async def test_list_claimed_values_container_is_not_applicable(ctx):
    """claimed_values as a top-level list (not a dict of values) must not raise
    AttributeError from .get() (finding 4)."""
    payload = {
        "system_params": {"type": "hydrogen_energy_level", "n": 1},
        "claimed_values": [-13.6, -3.4],
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["computed"] is not None


async def test_nan_mass_is_not_applicable(ctx):
    """NaN mass should return not_applicable, not silently produce a NaN result
    (finding 5)."""
    payload = {
        "system_params": {"type": "infinite_well", "width_nm": 1.0, "mass": float("nan"), "n": 1},
        "claimed_values": {"energy_ev": 0.376},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["computed"] is None


async def test_infinite_mass_is_not_applicable(ctx):
    """Infinity mass should return not_applicable, not silently produce an
    Infinity/zero result (finding 5)."""
    payload = {
        "system_params": {"type": "infinite_well", "width_nm": 1.0, "mass": float("inf"), "n": 1},
        "claimed_values": {"energy_ev": 0.376},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["computed"] is None


async def test_oversized_numeric_literal_is_not_applicable(ctx):
    """A JSON integer literal too large for float() (e.g. a 400-digit
    number) raises OverflowError from float(value) inside _safe_float —
    must resolve to not_applicable, not an uncaught exception."""
    payload = {
        "system_params": {"type": "infinite_well", "width_nm": 10**400, "mass": "electron", "n": 1},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["computed"] is None


async def test_oversized_claimed_value_is_not_applicable(ctx):
    """An oversized numeric literal in claimed_values must not crash the
    final comparison via float(claimed)."""
    payload = {
        "system_params": {"type": "hydrogen_energy_level", "n": 1},
        "claimed_values": {"energy_ev": 10**400},
    }
    result = await QMCalculationTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
