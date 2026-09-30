"""candidate_health: classifies why a candidate fails (or that it does not)."""
from __future__ import annotations

import json
from pathlib import Path

from moonstar_physics.construct_diagnose import candidate_health

_ROOT = Path(__file__).parent.parent
_MHD = _ROOT / "constructs" / "analytic-3d-mhd-equilibrium.yaml"
_AXI = _ROOT / "constructs" / "axisymmetric-mhd-equilibrium.yaml"
_FIX = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((_FIX / name).read_text(encoding="utf-8"))


def test_known_good_field_is_ok():
    h = candidate_health(_MHD, _load("iota2_candidate.json"))
    assert h["classification"] == "ok"
    assert all(g["abs"] <= 1e-8 for g in h["gates"].values())


def test_divergent_field_is_wrong_everywhere():
    bad = {"objects": {"B": ["x", "y", "z"], "psi": "x**2+y**2+z**2", "p": "1-psi"}}
    h = candidate_health(_MHD, bad)
    assert h["classification"] == "wrong"
    assert h["gates"]["div_free"]["frac_bad"] > 0.9      # div B = 3 at essentially every point


def test_candidate_undefined_in_the_box_is_undefined():
    cand = {"objects": {"B": ["sqrt(-1-x**2)", "0", "0"], "psi": "x**2", "p": "x"}}
    assert candidate_health(_MHD, cand)["classification"] == "undefined"


def test_unresolvable_candidate_is_undefined_with_an_error():
    h = candidate_health(_MHD, {"objects": {"B": ["x", "y", "q"], "psi": "x", "p": "x"}})
    assert h["classification"] == "undefined" and "error" in h


def test_failure_at_a_few_points_is_localised():
    """A correct field plus a pressure term that only bites near one point (a singularity)."""
    cand = _load("iota2_candidate.json")
    cand["objects"]["p"] = "1-2*psi+1e-14/((x-0.3)**2+y**2+z**2)**3"
    h = candidate_health(_MHD, cand)
    assert h["classification"] == "localised", h
    assert h["worst_gate"] == "force_balance" and h["gates"]["force_balance"]["frac_bad"] <= 0.02


def test_large_field_with_tiny_relative_error_is_scale_not_wrong():
    """Solov'ev field scaled by 1e5 (p by 1e10): exact up to roundoff, but the absolute
    residual (~1e-5) exceeds the checker's 1e-8."""
    cand = _load("solovev_candidate.json")
    for k in ("BR", "BZ", "Btor"):
        cand["defs"][k] = f"1e5*({cand['defs'][k]})"
    cand["objects"]["p"] = "1e10*(1-5*psi)"
    h = candidate_health(_AXI, cand)
    assert h["classification"] == "scale", h
    assert h["gates"]["force_balance"]["abs"] > 1e-8 and h["gates"]["force_balance"]["rel"] <= 1e-9
