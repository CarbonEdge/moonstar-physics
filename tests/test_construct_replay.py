"""replay_candidate reproduces the deterministic pipeline verdicts without any LLM."""
from __future__ import annotations

import json
from pathlib import Path

from moonstar_physics import iota_trace_transform
from moonstar_physics.construct_replay import replay_candidate

from .iota_helpers import fake_sandbox

_ROOT = Path(__file__).parent.parent
_MHD = _ROOT / "constructs" / "analytic-3d-mhd-equilibrium.yaml"
_FIX = Path(__file__).parent / "fixtures"


async def test_replay_known_positive_is_constructed(monkeypatch):
    monkeypatch.setattr(iota_trace_transform, "_run_sandbox", fake_sandbox)
    cand = json.loads((_FIX / "iota2_candidate.json").read_text(encoding="utf-8"))
    out = await replay_candidate(_MHD, cand)
    assert out["verdict"] == "CONSTRUCTED"


async def test_replay_skips_the_sandbox_when_the_gate_fails(monkeypatch):
    async def boom(script, timeout_seconds):
        raise AssertionError("sandbox must not run when the gate failed")

    monkeypatch.setattr(iota_trace_transform, "_run_sandbox", boom)
    bad = {"objects": {"B": ["x", "y", "z"], "psi": "x**2+y**2+z**2", "p": "1-psi"}}
    out = await replay_candidate(_MHD, bad)
    assert out["verdict"] == "NOT_FOUND" and "iota_nonzero" in out["unverified_hard"]


async def test_replay_seed_is_passed_through(monkeypatch):
    monkeypatch.setattr(iota_trace_transform, "_run_sandbox", fake_sandbox)
    cand = json.loads((_FIX / "iota2_candidate.json").read_text(encoding="utf-8"))
    a = await replay_candidate(_MHD, cand, seed=1)
    b = await replay_candidate(_MHD, cand, seed=2)
    ra = next(r for r in a["checklist"] if r["id"] == "div_free")["evidence"]["max_residual"]
    rb = next(r for r in b["checklist"] if r["id"] == "div_free")["evidence"]["max_residual"]
    assert ra != rb
