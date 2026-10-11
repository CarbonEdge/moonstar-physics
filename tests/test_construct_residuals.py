"""P4.3 residual diagnostics: point residuals, dominant terms, bounded simplification."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
import sympy

from moonstar_physics import construct_residuals as cr
from moonstar_physics.construct_spec import load_construct_spec

_ROOT = Path(__file__).parent.parent
_SPEC = load_construct_spec(_ROOT / "constructs" / "analytic-3d-mhd-equilibrium.yaml")
_WRONG = {"objects": {"B": ["x", "y", "z"], "psi": "(sqrt(x**2+y**2)-1)**2+z**2", "p": "1-psi"}}


def test_failed_force_balance_gets_points_terms_and_lorentz_vs_grad_p():
    diag = cr.diagnose_gate_failures(_SPEC, _WRONG, ["force_balance"], symbolic=False)
    fb = diag["force_balance"]
    assert set(fb["residual_at_points"]) == set(cr._POINT_NAMES) and len(fb["residual_at_points"]["axis"]) == 3
    assert set(fb["lorentz_vs_grad_p"]) == {"curl_B_cross_B", "grad_p"}
    assert fb["components"][0]["dominant_terms"]            # expandable residual -> ranked terms
    assert fb["points"]["axis"][0] == pytest.approx(1.0, abs=0.1)   # axis = psi minimum, the ring R=1


def test_only_failed_gate_criteria_are_diagnosed_and_bad_candidates_degrade_to_empty():
    assert cr.diagnose_gate_failures(_SPEC, _WRONG, ["psi_nonneg"], symbolic=False) == {}
    assert cr.diagnose_gate_failures(_SPEC, {"objects": {}}, ["force_balance"], symbolic=False) == {}


def test_simplify_many_returns_closed_forms_and_skips_oversized_expressions():
    x = sympy.Symbol("x")
    big = sum(sympy.sin(x * i) * x**i for i in range(1, 80))
    out = cr.simplify_many_with_timeout([sympy.sin(x) ** 2 + sympy.cos(x) ** 2 - 1 + x, big])
    assert out[0] == x and out[1] is None


def _sleepy_worker(texts, queue):  # module level: the spawn start method must be able to pickle it
    time.sleep(60)


def test_simplify_timeout_terminates_the_child_instead_of_hanging(monkeypatch):
    monkeypatch.setattr(cr, "_simplify_worker", _sleepy_worker)
    t0 = time.monotonic()
    out = cr.simplify_many_with_timeout([sympy.Symbol("x") + 1], timeout=1.0)
    assert out == [None] and time.monotonic() - t0 < 10


def test_feedback_diagnostics_are_size_capped():
    from moonstar_physics.construct_pipeline import _DIAG_MAX_CHARS, _cap_diagnostics
    huge = {"force_balance": {"residual_at_points": {"axis": [1.0]}, "components": [{"s": "x" * 100}] * 200,
                              "lorentz_vs_grad_p": {"k": [1.0] * 5}}}
    capped = _cap_diagnostics(huge)
    assert len(json.dumps(capped)) <= _DIAG_MAX_CHARS and "residual_at_points" in capped["force_balance"]
    assert _cap_diagnostics(None) is None


def test_diagnostics_work_for_a_spec_without_psi_or_p():
    spec = load_construct_spec(_ROOT / "constructs" / "beltrami-force-free.yaml")
    cand = {"objects": {"B": ["sin(z)+cos(y)", "sin(x)+cos(z)", "sin(y)+cos(x)"]}, "params": {"lam": 2.0}}
    diag = cr.diagnose_gate_failures(spec, cand, ["beltrami"], symbolic=False)
    row = diag["beltrami"]
    assert len(row["residual_at_points"]["axis"]) == 3 and "lorentz_vs_grad_p" not in row
    assert any(abs(v) > 0.1 for v in row["residual_at_points"]["axis"])        # curl B - 2B = -B != 0


def _hang_worker(spec_path, candidate, failed, queue):  # module level: picklable for spawn
    time.sleep(120)


def test_diagnose_with_timeout_returns_empty_and_kills_the_child_on_a_hang(monkeypatch):
    monkeypatch.setattr(cr, "_diagnose_worker", _hang_worker)
    t0 = time.monotonic()
    out = cr.diagnose_with_timeout(str(_ROOT / "constructs" / "analytic-3d-mhd-equilibrium.yaml"), _WRONG, ["force_balance"], timeout=1.5)
    assert out == {} and time.monotonic() - t0 < 15


def test_diagnose_with_timeout_matches_the_in_process_result():
    path = str(_ROOT / "constructs" / "analytic-3d-mhd-equilibrium.yaml")
    out = cr.diagnose_with_timeout(path, _WRONG, ["force_balance"], timeout=120)
    assert set(out["force_balance"]["residual_at_points"]) == set(cr._POINT_NAMES)
