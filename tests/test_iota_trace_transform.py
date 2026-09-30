from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from moonstar_physics import iota_trace_transform as mod
from moonstar_physics._compat import SessionContext
from moonstar_physics.iota_trace_transform import IotaTraceTransform

from .iota_helpers import fake_sandbox

_ROOT = Path(__file__).parent.parent
_SPEC = str(_ROOT / "constructs" / "analytic-3d-mhd-equilibrium.yaml")
_FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "iota2_candidate.json").read_text(encoding="utf-8"))
_CTX = SessionContext()


def _inp(candidate: dict, name: str = "Generator_A") -> dict:
    return {name: {"response": json.dumps(candidate)}}


def _by_id(out: dict) -> dict:
    return {r["id"]: r for r in out["results"]}


async def test_iota2_fixture_integer_iota_passes_nonzero_fails_noninteger(monkeypatch):
    monkeypatch.setattr(mod, "_run_sandbox", fake_sandbox)
    out = await IotaTraceTransform(_inp(_FIXTURE), {"spec_path": _SPEC}, _CTX)
    rows = _by_id(out)
    assert set(rows) == {"iota_nonzero", "iota_noninteger"}
    assert rows["iota_nonzero"]["status"] == "pass"
    assert rows["iota_noninteger"]["status"] == "fail"     # iota = -2 is an integer
    assert abs(rows["iota_nonzero"]["iota"] + 2.0) < 1e-4
    assert "RESULT:" in out["stdout"] and "numpy" in out["script"]
    assert out["dof_values"] == {"epsilon": pytest.approx(0.475)}   # midpoint of [0.05, 0.9]


async def test_params_override_dof_midpoint(monkeypatch):
    seen = {}

    async def spy(script, timeout_seconds):
        seen["script"] = script
        return {"ran": True, "result": {"iota": 0.5}, "detail": None, "stdout": "", "exit_code": 0}

    monkeypatch.setattr(mod, "_run_sandbox", spy)
    out = await IotaTraceTransform(_inp({**_FIXTURE, "params": {"epsilon": 0.2}}), {"spec_path": _SPEC}, _CTX)
    assert out["dof_values"] == {"epsilon": 0.2}
    assert _by_id(out)["iota_noninteger"]["status"] == "pass"     # 0.5 is not an integer
    assert _by_id(out)["iota_nonzero"]["status"] == "pass"


async def test_zero_iota_fails_nonzero(monkeypatch):
    async def zero(script, timeout_seconds):
        return {"ran": True, "result": {"iota": 0.0}, "detail": None, "stdout": "", "exit_code": 0}

    monkeypatch.setattr(mod, "_run_sandbox", zero)
    out = await IotaTraceTransform(_inp(_FIXTURE), {"spec_path": _SPEC}, _CTX)
    assert _by_id(out)["iota_nonzero"]["status"] == "fail"


@pytest.mark.parametrize("sandbox_return", [
    {"ran": False, "result": None, "detail": "sandbox run exceeded 60s timeout", "stdout": "", "exit_code": None},
    {"ran": True, "result": {"error": "toroidal field component vanishes"}, "detail": None, "stdout": "", "exit_code": 0},
    {"ran": True, "result": {"unexpected": 1}, "detail": None, "stdout": "", "exit_code": 0},
])
async def test_untrustworthy_trace_is_error_never_pass(monkeypatch, sandbox_return):
    async def bad(script, timeout_seconds):
        return sandbox_return

    monkeypatch.setattr(mod, "_run_sandbox", bad)
    out = await IotaTraceTransform(_inp(_FIXTURE), {"spec_path": _SPEC}, _CTX)
    assert {r["status"] for r in out["results"]} == {"error"}
    assert all(r["detail"] for r in out["results"])


async def test_bad_candidate_is_error_and_sandbox_is_not_called(monkeypatch):
    async def boom(script, timeout_seconds):
        raise AssertionError("sandbox must not run for a rejected candidate")

    monkeypatch.setattr(mod, "_run_sandbox", boom)
    bad = {"objects": {"B": ["x", "y", "q"], "psi": "x", "p": "x"}}    # unknown symbol q
    out = await IotaTraceTransform(_inp(bad), {"spec_path": _SPEC}, _CTX)
    assert {r["status"] for r in out["results"]} == {"error"}
    assert "candidate rejected" in out["results"][0]["detail"]


async def test_custom_source_name(monkeypatch):
    monkeypatch.setattr(mod, "_run_sandbox", fake_sandbox)
    out = await IotaTraceTransform(_inp(_FIXTURE, "Generator_B"), {"spec_path": _SPEC, "source": "Generator_B"}, _CTX)
    assert _by_id(out)["iota_nonzero"]["status"] == "pass"


def _docker_image_present() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(
            ["docker", "image", "inspect", "moonstar-physics-experiment-runner"],
            capture_output=True, timeout=20,
        ).returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


@pytest.mark.skipif(not _docker_image_present(), reason="sandbox image not built (scripts/build_sandbox_image.sh)")
async def test_real_docker_sandbox_gives_minus_two():
    out = await IotaTraceTransform(_inp(_FIXTURE), {"spec_path": _SPEC, "timeout_seconds": 120}, _CTX)
    row = _by_id(out)["iota_nonzero"]
    assert row["status"] == "pass", out["stdout"]
    assert abs(row["iota"] + 2.0) < 1e-4


def _sandbox_returning(result):
    async def fake(script, timeout_seconds):
        return {"ran": True, "result": result, "detail": None, "stdout": "", "exit_code": 0}
    return fake


async def test_sheared_seeds_are_judged_on_every_surface(monkeypatch):
    monkeypatch.setattr(mod, "_run_sandbox", _sandbox_returning(
        {"iota": 1.9, "iota_seeds": [1.956, 1.837], "iota_spread": 0.119}))
    rows = _by_id(await IotaTraceTransform(_inp(_FIXTURE), {"spec_path": _SPEC}, _CTX))
    assert rows["iota_nonzero"]["status"] == "pass"
    assert rows["iota_noninteger"]["status"] == "pass"
    assert rows["iota_nonzero"]["iota_spread"] == pytest.approx(0.119)


async def test_sign_change_between_surfaces_fails_nonzero(monkeypatch):
    monkeypatch.setattr(mod, "_run_sandbox", _sandbox_returning({"iota": 0.0, "iota_seeds": [0.4, -0.4]}))
    rows = _by_id(await IotaTraceTransform(_inp(_FIXTURE), {"spec_path": _SPEC}, _CTX))
    assert rows["iota_nonzero"]["status"] == "fail"


async def test_one_surface_near_an_integer_fails_noninteger(monkeypatch):
    monkeypatch.setattr(mod, "_run_sandbox", _sandbox_returning({"iota": 2.15, "iota_seeds": [2.0004, 2.3]}))
    rows = _by_id(await IotaTraceTransform(_inp(_FIXTURE), {"spec_path": _SPEC}, _CTX))
    assert rows["iota_nonzero"]["status"] == "pass"
    assert rows["iota_noninteger"]["status"] == "fail"