"""Tests for VectorCalculusCheckTransform — candidate (B, psi, p) strings
checked against a ConstructSpec by symbolic differentiation + numeric
residuals at random in-domain points."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from moonstar_physics._compat import NonRetryableTransformError, SessionContext
from moonstar_physics.vector_calculus_check_transform import VectorCalculusCheckTransform

_ROOT = Path(__file__).resolve().parents[1]
_SPEC = str(_ROOT / "constructs" / "analytic-3d-mhd-equilibrium.yaml")
_IOTA2 = json.loads((_ROOT / "tests" / "fixtures" / "iota2_candidate.json").read_text())


@pytest.fixture
def ctx() -> AsyncMock:
    return AsyncMock(spec=SessionContext)


def _input(candidate) -> dict:
    return {"Generator_A": {"response": json.dumps(candidate)}}


async def _run(candidate, ctx, **config):
    cfg = {"spec_path": _SPEC, **config}
    out = await VectorCalculusCheckTransform(_input(candidate), cfg, ctx)
    return {r["id"]: r for r in out["results"]}, out


async def test_published_iota2_field_passes_every_checkable_criterion(ctx):
    by_id, out = await _run(_IOTA2, ctx)
    for cid in ("div_free", "flux_surface", "force_balance", "psi_nonneg",
                "psi_nonconstant", "p_nonconstant", "nonaxisym"):
        assert by_id[cid]["status"] == "pass", (cid, by_id[cid])
    assert by_id["div_free"]["max_residual"] < 1e-8
    assert by_id["force_balance"]["n_valid"] >= 200
    assert "iota_nonzero" not in by_id      # sandbox_experiment is Phase 2
    assert "novel" not in by_id             # manual
    assert out["_model"] == "none"


async def test_divergence_violation_fails_div_and_reports_residual(ctx):
    cand = {"objects": {"B": ["x", "y", "z"], "psi": "x**2+y**2+z**2", "p": "1-psi"}}
    by_id, _ = await _run(cand, ctx)
    assert by_id["div_free"]["status"] == "fail"
    assert by_id["div_free"]["max_residual"] == pytest.approx(3.0)


async def test_axisymmetric_relabel_fails_nonaxisym_but_passes_gates(ctx):
    # B = (-y, x, 0), psi = x^2+y^2, p = 1 - psi: exact equilibrium, but rotationally symmetric.
    cand = {"objects": {"B": ["-y", "x", "0"], "psi": "x**2+y**2", "p": "1-psi"}}
    by_id, _ = await _run(cand, ctx)
    assert by_id["div_free"]["status"] == "pass"
    assert by_id["flux_surface"]["status"] == "pass"
    assert by_id["force_balance"]["status"] == "pass"
    assert by_id["nonaxisym"]["status"] == "fail"


async def test_trivial_zero_field_caught_by_nonconstant_pressure(ctx):
    cand = {"objects": {"B": ["0", "0", "0"], "psi": "x**2+y**2+4*z**2", "p": "1"}}
    by_id, _ = await _run(cand, ctx)
    assert by_id["div_free"]["status"] == "pass"
    assert by_id["force_balance"]["status"] == "pass"   # vacuous...
    assert by_id["p_nonconstant"]["status"] == "fail"    # ...and this is what catches it


async def test_force_balance_violation_fails(ctx):
    cand = {"objects": {"B": ["-y", "x", "0"], "psi": "x**2+y**2", "p": "1-2*psi"}}
    by_id, _ = await _run(cand, ctx)
    assert by_id["force_balance"]["status"] == "fail"


async def test_negative_psi_fails_nonnegative(ctx):
    cand = {"objects": {"B": ["-y", "x", "0"], "psi": "-(x**2+y**2)-0.1", "p": "1-psi"}}
    by_id, _ = await _run(cand, ctx)
    assert by_id["psi_nonneg"]["status"] == "fail"


async def test_no_valid_sample_points_is_error_not_pass(ctx):
    cand = {"objects": {"B": ["sqrt(-1-x**2)", "0", "0"], "psi": "x**2", "p": "1-psi"}}
    by_id, _ = await _run(cand, ctx)
    assert by_id["div_free"]["status"] == "error"
    assert by_id["div_free"]["n_valid"] < 200
    assert "valid" in by_id["div_free"]["detail"]


async def test_unresolved_symbol_is_per_criterion_error(ctx):
    cand = {"objects": {"B": ["q", "0", "0"], "psi": "x**2", "p": "1-psi"}}
    by_id, _ = await _run(cand, ctx)
    assert by_id["div_free"]["status"] == "error"
    assert "q" in by_id["div_free"]["detail"]


async def test_forward_reference_in_defs_is_error(ctx):
    cand = {
        "defs": {"u": "v+1", "v": "x"},
        "objects": {"B": ["u", "0", "0"], "psi": "x**2", "p": "1-psi"},
    }
    by_id, _ = await _run(cand, ctx)
    assert by_id["div_free"]["status"] == "error"
    assert "v" in by_id["div_free"]["detail"]


async def test_def_shadowing_coordinate_or_parameter_is_error(ctx):
    for name in ("x", "epsilon"):
        cand = {
            "defs": {name: "1"},
            "objects": {"B": ["0", "0", "0"], "psi": "x**2", "p": "1-psi"},
        }
        by_id, _ = await _run(cand, ctx)
        assert by_id["div_free"]["status"] == "error", name
        assert "shadow" in by_id["div_free"]["detail"]


async def test_over_complex_expression_is_error_not_crash(ctx):
    big = "+".join(f"sin(x*{i})" for i in range(1, 120))
    cand = {"objects": {"B": [big, "0", "0"], "psi": "x**2", "p": "1-psi"}}
    by_id, _ = await _run(cand, ctx)
    assert all(r["status"] == "error" for r in by_id.values())


async def test_params_fix_a_degree_of_freedom(ctx):
    cand = dict(_IOTA2, params={"epsilon": 0.25})
    by_id, _ = await _run(cand, ctx)
    assert by_id["force_balance"]["status"] == "pass"


async def test_tolerance_config_is_respected(ctx):
    cand = {"objects": {"B": ["x", "y", "z"], "psi": "x**2+y**2+z**2", "p": "1-psi"}}
    by_id, _ = await _run(cand, ctx, tolerance=10.0)
    assert by_id["div_free"]["status"] == "pass"


@pytest.mark.parametrize(
    "bad_input",
    [
        {},
        {"Generator_A": "not a dict"},
        {"Generator_A": {"response": 5}},
        {"Generator_A": {"response": "not json"}},
        {"Generator_A": {"response": "[1, 2]"}},
    ],
)
async def test_malformed_input_shape_raises(ctx, bad_input):
    with pytest.raises(NonRetryableTransformError):
        await VectorCalculusCheckTransform(bad_input, {"spec_path": _SPEC}, ctx)


async def test_missing_objects_is_error_results_not_exception(ctx):
    by_id, _ = await _run({"nothing": True}, ctx)
    assert all(r["status"] == "error" for r in by_id.values())


async def test_custom_source_name(ctx):
    inp = {"Gen_B": {"response": json.dumps(_IOTA2)}}
    out = await VectorCalculusCheckTransform(inp, {"spec_path": _SPEC, "source": "Gen_B"}, ctx)
    assert {r["id"]: r["status"] for r in out["results"]}["div_free"] == "pass"