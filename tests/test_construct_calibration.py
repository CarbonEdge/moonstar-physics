"""End-to-end calibration for the Phase 1 construct checker: known-positive,
known-bad, and partial-credit candidates through both transforms."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SPEC = str(_ROOT / "constructs" / "analytic-3d-mhd-equilibrium.yaml")
_SCRIPT = _ROOT / "scripts" / "check_construct_candidate.py"
_IOTA2_PATH = _ROOT / "tests" / "fixtures" / "iota2_candidate.json"


def _load_script():
    spec = importlib.util.spec_from_file_location("check_construct_candidate", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _statuses(out: dict) -> dict[str, str]:
    return {row["id"]: row["status"] for row in out["checklist"]}


async def test_known_positive_published_field_is_partial_with_only_iota_unverified():
    """Landreman's published iota=2 field: every Phase 1 check met; iota_nonzero
    needs the Phase 2 sandbox template, so the honest verdict is PARTIAL."""
    check = _load_script().check_candidate
    out = await check(_SPEC, json.loads(_IOTA2_PATH.read_text()))
    assert out["verdict"] == "PARTIAL"
    assert out["unmet_hard"] == []
    assert out["unverified_hard"] == ["iota_nonzero"]


async def test_known_bad_divergence_is_not_found():
    check = _load_script().check_candidate
    cand = {"objects": {"B": ["x", "y", "z"], "psi": "x**2+y**2+z**2", "p": "1-psi"}}
    out = await check(_SPEC, cand)
    assert out["verdict"] == "NOT_FOUND"


async def test_partial_credit_axisymmetric_equilibrium():
    check = _load_script().check_candidate
    cand = {"objects": {"B": ["-y", "x", "0"], "psi": "x**2+y**2", "p": "1-psi"}}
    out = await check(_SPEC, cand)
    assert out["verdict"] == "PARTIAL"
    assert "nonaxisym" in out["unmet_hard"]


async def test_trivial_zero_field_never_constructed():
    check = _load_script().check_candidate
    cand = {"objects": {"B": ["0", "0", "0"], "psi": "x**2+y**2+4*z**2", "p": "1"}}
    out = await check(_SPEC, cand)
    assert out["verdict"] != "CONSTRUCTED"
    assert "p_nonconstant" in out["unmet_hard"]


async def test_undefined_everywhere_candidate_is_not_found():
    check = _load_script().check_candidate
    cand = {"objects": {"B": ["sqrt(-1-x**2)", "0", "0"], "psi": "x**2", "p": "1-psi"}}
    out = await check(_SPEC, cand)
    assert out["verdict"] == "NOT_FOUND"
    assert _statuses(out)["div_free"] == "unverified"


def test_cli_prints_verdict_first_and_exits_nonzero_unless_constructed():
    proc = subprocess.run(
        [sys.executable, str(_SCRIPT), _SPEC, str(_IOTA2_PATH)],
        capture_output=True, text=True, timeout=120,
    )
    first_line = proc.stdout.splitlines()[0]
    assert first_line == "VERDICT: PARTIAL"
    assert "iota_nonzero" in proc.stdout
    assert proc.returncode == 1


def test_cli_usage_error_on_missing_args():
    proc = subprocess.run([sys.executable, str(_SCRIPT)], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 2
    assert "usage" in (proc.stderr + proc.stdout).lower()


async def test_iota2_end_to_end_is_constructed_with_sandbox_stage(monkeypatch):
    """Phase 2 promotes Landreman's iota=2 field from PARTIAL (Phase 1) to CONSTRUCTED."""
    from moonstar_physics import iota_trace_transform as iota_mod
    from moonstar_physics._compat import SessionContext
    from moonstar_physics.construct_criteria_transform import ConstructCriteriaTransform
    from moonstar_physics.iota_trace_transform import IotaTraceTransform
    from moonstar_physics.vector_calculus_check_transform import VectorCalculusCheckTransform
    from .iota_helpers import fake_sandbox

    monkeypatch.setattr(iota_mod, "_run_sandbox", fake_sandbox)
    _IOTA2 = json.loads(_IOTA2_PATH.read_text(encoding="utf-8"))
    inp = {"Generator_A": {"response": json.dumps(_IOTA2)}}
    checks = await VectorCalculusCheckTransform(inp, {"spec_path": _SPEC, "source": "Generator_A"}, SessionContext())
    iota = await IotaTraceTransform(inp, {"spec_path": _SPEC, "source": "Generator_A"}, SessionContext())
    out = await ConstructCriteriaTransform(
        {"checks": checks, "iota": iota},
        {"spec_path": _SPEC, "sources": ["checks", "iota"]}, SessionContext(),
    )
    assert out["verdict"] == "CONSTRUCTED"
    assert {r["id"]: r["status"] for r in out["checklist"]}["iota_noninteger"] == "unmet"


async def test_solovev_equilibrium_is_constructed_under_the_second_spec(monkeypatch):
    """Known-answer control: a correct sheared axisymmetric equilibrium must be CONSTRUCTED."""
    import json as _json
    from pathlib import Path as _P
    from moonstar_physics import iota_trace_transform as iota_mod
    from moonstar_physics._compat import SessionContext
    from moonstar_physics.construct_criteria_transform import ConstructCriteriaTransform
    from moonstar_physics.iota_trace_transform import IotaTraceTransform
    from moonstar_physics.vector_calculus_check_transform import VectorCalculusCheckTransform
    from .iota_helpers import fake_sandbox

    monkeypatch.setattr(iota_mod, "_run_sandbox", fake_sandbox)
    root = _P(__file__).parent.parent
    spec = str(root / "constructs" / "axisymmetric-mhd-equilibrium.yaml")
    cand = _json.loads((_P(__file__).parent / "fixtures" / "solovev_candidate.json").read_text(encoding="utf-8"))
    inp = {"G": {"response": _json.dumps(cand)}}
    ctx = SessionContext()
    checks = await VectorCalculusCheckTransform(inp, {"spec_path": spec, "source": "G"}, ctx)
    iota = await IotaTraceTransform(inp, {"spec_path": spec, "source": "G"}, ctx)
    out = await ConstructCriteriaTransform({"checks": checks, "iota": iota}, {"spec_path": spec, "sources": ["checks", "iota"]}, ctx)
    assert out["verdict"] == "CONSTRUCTED", out["checklist"]
    assert out["unmet_hard"] == [] and out["unverified_hard"] == []


async def test_z_independent_screw_pinch_is_not_constructed(monkeypatch):
    """Regression: a live run called this CONSTRUCTED because the tracer accepted an axis on the z-axis."""
    import json as _json
    from pathlib import Path as _P
    from moonstar_physics import iota_trace_transform as iota_mod
    from moonstar_physics._compat import SessionContext
    from moonstar_physics.construct_criteria_transform import ConstructCriteriaTransform
    from moonstar_physics.iota_trace_transform import IotaTraceTransform
    from moonstar_physics.vector_calculus_check_transform import VectorCalculusCheckTransform
    from .iota_helpers import fake_sandbox

    monkeypatch.setattr(iota_mod, "_run_sandbox", fake_sandbox)
    root = _P(__file__).parent.parent
    spec = str(root / "constructs" / "analytic-3d-mhd-equilibrium.yaml")
    cand = _json.loads((_P(__file__).parent / "fixtures" / "screw_pinch_candidate.json").read_text(encoding="utf-8"))
    inp = {"G": {"response": _json.dumps(cand)}}
    ctx = SessionContext()
    checks = await VectorCalculusCheckTransform(inp, {"spec_path": spec, "source": "G"}, ctx)
    iota = await IotaTraceTransform(inp, {"spec_path": spec, "source": "G", "timeout_seconds": 120}, ctx)
    out = await ConstructCriteriaTransform({"checks": checks, "iota": iota}, {"spec_path": spec, "sources": ["checks", "iota"]}, ctx)
    assert out["verdict"] == "PARTIAL", out["checklist"]
    assert out["unverified_hard"] == ["iota_nonzero"]
    detail = next(r for r in out["checklist"] if r["id"] == "iota_nonzero")["evidence"]["detail"]
    assert "z-axis" in detail

