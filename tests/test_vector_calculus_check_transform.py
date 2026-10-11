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


async def test_seed_config_changes_the_draws_and_is_reported():
    from moonstar_physics._compat import SessionContext as _Ctx
    from moonstar_physics.vector_calculus_check_transform import VectorCalculusCheckTransform as _T

    root = Path(__file__).parent.parent
    spec = str(root / "constructs" / "analytic-3d-mhd-equilibrium.yaml")
    cand = json.loads((Path(__file__).parent / "fixtures" / "iota2_candidate.json").read_text(encoding="utf-8"))
    inp = {"G": {"response": json.dumps(cand)}}

    def resid(out):
        return {r["id"]: r.get("max_residual") for r in out["results"] if r["id"] == "div_free"}

    a0 = await _T(inp, {"spec_path": spec, "source": "G"}, _Ctx())
    a0b = await _T(inp, {"spec_path": spec, "source": "G", "seed": 0}, _Ctx())
    a1 = await _T(inp, {"spec_path": spec, "source": "G", "seed": 1}, _Ctx())
    assert a0["seed"] == 0 and a1["seed"] == 1
    assert resid(a0) == resid(a0b)            # default is seed 0, reproducible
    assert resid(a0) != resid(a1)             # a different seed draws different points

def _nested_spec(tmp_path):
    import yaml
    from pathlib import Path as _P
    data = yaml.safe_load((_P(__file__).parent.parent / "constructs" / "analytic-3d-mhd-equilibrium.yaml").read_text(encoding="utf-8"))
    data["criteria"]["hard"].append({"id": "nested", "check": "numeric_sample", "kind": "nested_surfaces", "target": "psi"})
    p = tmp_path / "s.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    return str(p)


async def _nested_status(tmp_path, psi):
    import json as _j
    from moonstar_physics._compat import SessionContext
    cand = {"objects": {"B": ["-y", "x", "0"], "psi": psi, "p": "1-psi"}}
    out = await VectorCalculusCheckTransform(
        {"G": {"response": _j.dumps(cand)}}, {"spec_path": _nested_spec(tmp_path), "source": "G"}, SessionContext())
    return {r["id"]: r for r in out["results"]}["nested"]


async def test_nested_surfaces_pass_for_a_single_well_torus(tmp_path):
    assert (await _nested_status(tmp_path, "(sqrt(x**2+y**2)-1)**2+z**2"))["status"] == "pass"


async def test_nested_surfaces_fail_for_two_wells(tmp_path):
    # wells at rho=0.6 (deeper, the minimum) and rho=1.2: psi falls then rises along a ray between them
    psi = "(sqrt(x**2+y**2)-0.6)**2*(sqrt(x**2+y**2)-1.2)**2+0.002*(sqrt(x**2+y**2)-0.6)**2+z**2"
    row = await _nested_status(tmp_path, psi)
    assert row["status"] == "fail" and row["n_bad_rays"] > 0 and "second well" in row["detail"]


async def test_nested_surfaces_error_when_psi_undefined_everywhere(tmp_path):
    assert (await _nested_status(tmp_path, "sqrt(-1-x**2)"))["status"] == "error"


def test_axisymmetry_deviation_is_translation_invariant():
    import numpy as np
    import sympy
    from moonstar_physics.vector_calculus_check_transform import axisymmetry_deviation
    x, y, z = sympy.symbols("x y z")
    rng = np.random.default_rng(0)
    arrays = [rng.uniform(-1.5, 1.5, 2000), rng.uniform(-1.5, 1.5, 2000), rng.uniform(-0.5, 0.5, 2000)]
    swirl_about = lambda cx: (-(y), (x - cx), sympy.Integer(0))                      # noqa: E731
    shifted = (-(y), (x - 0.3), sympy.Integer(0))
    dev, centre, n = axisymmetry_deviation(shifted, [x, y, z], arrays)
    assert dev < 1e-6 and abs(centre[0] - 0.3) < 1e-3 and n > 1000        # axisymmetric about x=0.3
    helical = (sympy.sin(x), sympy.cos(y) + z, sympy.sin(x * y))
    assert axisymmetry_deviation(helical, [x, y, z], arrays)[0] > 1e-3    # genuinely not axisymmetric
