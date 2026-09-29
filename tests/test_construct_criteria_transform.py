"""Tests for ConstructCriteriaTransform — pure-code merge of checker output
into a met/unmet/unverified checklist and a CONSTRUCTED/PARTIAL/NOT_FOUND verdict."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from moonstar_physics._compat import NonRetryableTransformError, SessionContext
from moonstar_physics.construct_criteria_transform import ConstructCriteriaTransform

_SPEC = str(Path(__file__).resolve().parents[1] / "constructs" / "analytic-3d-mhd-equilibrium.yaml")

_CHECKABLE_HARD = ("div_free", "flux_surface", "force_balance", "psi_nonneg",
                   "psi_nonconstant", "p_nonconstant", "nonaxisym")


@pytest.fixture
def ctx() -> AsyncMock:
    return AsyncMock(spec=SessionContext)


def _results(**overrides: str) -> dict:
    statuses = {cid: "pass" for cid in _CHECKABLE_HARD}
    statuses.update(overrides)
    return {"checks": {"results": [
        {"id": cid, "check": "x", "status": st} for cid, st in statuses.items()
    ]}}


async def _run(inp, ctx, **config):
    return await ConstructCriteriaTransform(inp, {"spec_path": _SPEC, **config}, ctx)


def _status(out: dict, cid: str) -> str:
    return next(row["status"] for row in out["checklist"] if row["id"] == cid)


async def test_all_checkable_pass_but_iota_unverified_is_partial(ctx):
    out = await _run(_results(), ctx)
    assert out["verdict"] == "PARTIAL"
    assert out["unverified_hard"] == ["iota_nonzero"]
    assert out["unmet_hard"] == []
    assert _status(out, "iota_nonzero") == "unverified"
    assert _status(out, "div_free") == "met"


async def test_soft_criteria_reported_but_never_gate(ctx):
    out = await _run(_results(), ctx)
    soft = {row["id"]: row for row in out["checklist"] if not row["hard"]}
    assert set(soft) == {"iota_noninteger", "novel"}
    assert all(row["status"] == "unverified" for row in soft.values())
    assert out["verdict"] == "PARTIAL"   # unverified soft criteria do not change the verdict


async def test_gate_failure_is_not_found(ctx):
    out = await _run(_results(div_free="fail"), ctx)
    assert out["verdict"] == "NOT_FOUND"
    assert "div_free" in out["unmet_hard"]


async def test_gate_error_is_not_found(ctx):
    out = await _run(_results(force_balance="error"), ctx)
    assert out["verdict"] == "NOT_FOUND"
    assert _status(out, "force_balance") == "unverified"


async def test_non_gate_failure_is_partial(ctx):
    out = await _run(_results(nonaxisym="fail"), ctx)
    assert out["verdict"] == "PARTIAL"
    assert out["unmet_hard"] == ["nonaxisym"]


async def test_missing_result_is_unverified_not_met(ctx):
    inp = _results()
    inp["checks"]["results"] = [r for r in inp["checks"]["results"] if r["id"] != "flux_surface"]
    out = await _run(inp, ctx)
    assert _status(out, "flux_surface") == "unverified"
    assert out["verdict"] == "NOT_FOUND"


async def test_constructed_when_every_hard_criterion_is_met(ctx):
    inp = _results()
    inp["checks"]["results"].append({"id": "iota_nonzero", "check": "sandbox_experiment", "status": "pass"})
    out = await _run(inp, ctx)
    assert out["verdict"] == "CONSTRUCTED"
    assert out["unmet_hard"] == [] and out["unverified_hard"] == []


async def test_evidence_is_attached(ctx):
    inp = _results()
    inp["checks"]["results"][0]["max_residual"] = 1e-14
    out = await _run(inp, ctx)
    assert out["checklist"][0]["evidence"]["max_residual"] == 1e-14


async def test_custom_source(ctx):
    inp = {"vc": _results()["checks"]}
    out = await _run(inp, ctx, source="vc")
    assert out["verdict"] == "PARTIAL"


@pytest.mark.parametrize("bad", [{}, {"checks": "no"}, {"checks": {"results": "no"}}])
async def test_malformed_input_raises(ctx, bad):
    with pytest.raises(NonRetryableTransformError):
        await _run(bad, ctx)


_MHD_SPEC = str(Path(__file__).parent.parent / "constructs" / "analytic-3d-mhd-equilibrium.yaml")


def _all_pass_checks() -> dict:
    ids = ["div_free", "flux_surface", "force_balance", "psi_nonneg",
           "psi_nonconstant", "p_nonconstant", "nonaxisym"]
    return {"results": [{"id": i, "check": "x", "status": "pass"} for i in ids]}


async def test_sources_merge_checker_and_iota_rows_into_constructed():
    iota = {"results": [
        {"id": "iota_nonzero", "check": "sandbox_experiment", "status": "pass", "iota": -2.0},
        {"id": "iota_noninteger", "check": "sandbox_experiment", "status": "fail", "iota": -2.0},
    ]}
    out = await ConstructCriteriaTransform(
        {"checks": _all_pass_checks(), "iota": iota},
        {"spec_path": _MHD_SPEC, "sources": ["checks", "iota"]}, SessionContext(),
    )
    assert out["verdict"] == "CONSTRUCTED"
    soft = {r["id"]: r["status"] for r in out["checklist"] if not r["hard"]}
    assert soft["iota_noninteger"] == "unmet"          # integer iota is visible, not hidden
    assert soft["novel"] == "unverified"


async def test_iota_error_keeps_verdict_partial():
    iota = {"results": [
        {"id": "iota_nonzero", "check": "sandbox_experiment", "status": "error", "detail": "no zero minimum"},
    ]}
    out = await ConstructCriteriaTransform(
        {"checks": _all_pass_checks(), "iota": iota},
        {"spec_path": _MHD_SPEC, "sources": ["checks", "iota"]}, SessionContext(),
    )
    assert out["verdict"] == "PARTIAL"
    assert out["unverified_hard"] == ["iota_nonzero"]


async def test_missing_listed_source_is_an_error():
    with pytest.raises(NonRetryableTransformError):
        await ConstructCriteriaTransform(
            {"checks": _all_pass_checks()},
            {"spec_path": _MHD_SPEC, "sources": ["checks", "iota"]}, SessionContext(),
        )


async def test_single_source_config_still_works():
    out = await ConstructCriteriaTransform(
        {"checks": _all_pass_checks()}, {"spec_path": _MHD_SPEC, "source": "checks"}, SessionContext(),
    )
    assert out["verdict"] == "PARTIAL"                 # iota_nonzero unverified, as in Phase 1