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