"""Adversarial corpus: every labelled candidate must get exactly the verdict a correct checker gives.

The corpus is test data and is always committed. Labels live in tests/corpus/expected.yaml with a
written reason. A false CONSTRUCTED on any degenerate/synthetic/wrong candidate fails this test.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from moonstar_physics import iota_trace_transform
from moonstar_physics.construct_replay import replay_candidate

from .iota_helpers import fake_sandbox

_ROOT = Path(__file__).parent.parent
_CORPUS = Path(__file__).parent / "corpus"
_SPECS = {
    "mhd": _ROOT / "constructs" / "analytic-3d-mhd-equilibrium.yaml",
    "axisym": _ROOT / "constructs" / "axisymmetric-mhd-equilibrium.yaml",
}
_EXPECTED = yaml.safe_load((_CORPUS / "expected.yaml").read_text(encoding="utf-8"))
_GENUINE_PREFIXES = ("iota2_", "solovev_", "axisym_model_found")


def test_corpus_and_labels_are_in_sync_and_large_enough():
    files = {p.stem for p in _CORPUS.glob("*.json")}
    assert files == set(_EXPECTED), files ^ set(_EXPECTED)
    assert len(files) >= 12
    for name, label in _EXPECTED.items():
        assert label["spec"] in _SPECS and label["verdict"] in ("CONSTRUCTED", "PARTIAL", "NOT_FOUND")
        assert label["why"].strip(), name


def test_only_genuine_candidates_are_labelled_constructed():
    for name, label in _EXPECTED.items():
        if label["verdict"] == "CONSTRUCTED":
            assert name.startswith(_GENUINE_PREFIXES), f"{name} is labelled CONSTRUCTED but is not a known-genuine candidate"


@pytest.mark.parametrize("name", sorted(_EXPECTED))
async def test_corpus_verdict(name, monkeypatch):
    monkeypatch.setattr(iota_trace_transform, "_run_sandbox", fake_sandbox)
    label = _EXPECTED[name]
    cand = json.loads((_CORPUS / f"{name}.json").read_text(encoding="utf-8"))
    out = await replay_candidate(_SPECS[label["spec"]], cand)
    assert out["verdict"] == label["verdict"], (name, out["verdict"], out["unmet_hard"], out["unverified_hard"])
    assert sorted(out["unmet_hard"]) == sorted(label["unmet_hard"]), name
    assert sorted(out["unverified_hard"]) == sorted(label["unverified_hard"]), name
