"""Tests for the fixed iota field-line-trace script template. Scripts are run
with the host interpreter (tests/iota_helpers.py); a Docker run is covered
separately in test_iota_trace_transform.py."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import sympy

from moonstar_physics.iota_trace_template import IotaTemplateError, build_iota_script
from moonstar_physics.vector_calculus_check_transform import _resolve_candidate

from .iota_helpers import run_script_locally

_FIXTURE = Path(__file__).parent / "fixtures" / "iota2_candidate.json"
_BOX = {"x": (-1.5, 1.5), "y": (-1.5, 1.5), "z": (-0.5, 0.5)}


def _script_for(candidate: dict, dof_values: dict[str, float] | None = None) -> str:
    B, psi, _p = _resolve_candidate(candidate, ["epsilon"])
    return build_iota_script(B, psi, dof_values or {"epsilon": 0.3}, _BOX)


def _torus_candidate(b: list[str]) -> dict:
    # psi = 0 on the circle rho=1, z=0; B given by the caller.
    return {"objects": {"B": b, "psi": "(sqrt(x**2+y**2)-1)**2+z**2", "p": "1-psi"}}


def test_iota2_fixture_traces_to_minus_two():
    out = run_script_locally(_script_for(json.loads(_FIXTURE.read_text(encoding="utf-8"))))
    assert "error" not in out, out
    assert abs(out["iota"] + 2.0) < 1e-4          # sign convention pinned: theta from +rho toward +z
    assert max(out["iota_seeds"]) - min(out["iota_seeds"]) < 1e-3
    assert out["psi_drift"] < 1e-6
    assert out["axis_psi_min"] < 1e-6


def test_pure_toroidal_field_has_zero_iota():
    out = run_script_locally(_script_for(_torus_candidate(["-y", "x", "0"])))
    assert "error" not in out, out
    assert abs(out["iota"]) < 1e-6


def test_psi_without_zero_minimum_is_an_error_not_a_pass():
    cand = {"objects": {"B": ["-y", "x", "0"], "psi": "x**2+y**2+z**2+1", "p": "1-psi"}}
    out = run_script_locally(_script_for(cand))
    assert set(out) == {"error"} and "zero minimum" in out["error"]


def test_vanishing_toroidal_component_is_an_error():
    out = run_script_locally(_script_for(_torus_candidate(["0", "0", "1"])))
    assert set(out) == {"error"} and "toroidal" in out["error"]


def test_field_line_leaving_the_psi_surface_is_an_error():
    # B_z drifts the line off the psi = const surface: B . grad(psi) != 0.
    out = run_script_locally(_script_for(_torus_candidate(["-y", "x", "0.3"])))
    assert set(out) == {"error"} and "psi" in out["error"]


def test_non_finite_field_is_an_error():
    out = run_script_locally(_script_for(_torus_candidate(["-y", "x", "sqrt(-1-x**2)"])))
    assert set(out) == {"error"}


def test_unresolved_symbol_is_rejected_at_build_time():
    q = sympy.Symbol("q")
    x, y = sympy.symbols("x y")
    with pytest.raises(IotaTemplateError):
        build_iota_script([-y, x, q], x**2 + y**2, {}, _BOX)


def test_script_contains_only_fixed_imports_and_no_dunder():
    script = _script_for(json.loads(_FIXTURE.read_text(encoding="utf-8")))
    imports = sorted(re.findall(r"^(?:import|from) (\S+)", script, flags=re.M))
    assert imports == ["json", "numpy", "scipy.integrate", "scipy.optimize"]
    body = script.replace("__main__", "").replace("__name__", "")
    assert "__" not in body


def test_sheared_equilibrium_reports_spread_instead_of_erroring():
    cand = json.loads((Path(__file__).parent / "fixtures" / "solovev_candidate.json").read_text(encoding="utf-8"))
    out = run_script_locally(_script_for(cand))
    assert "error" not in out, out
    assert out["iota_spread"] > 1e-2                       # magnetic shear
    assert all(1.5 < v < 2.5 for v in out["iota_seeds"])
    assert out["psi_drift"] < 1e-6