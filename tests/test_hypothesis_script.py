"""Tests for scripts/test_hypothesis.py's pure-logic helpers.

The script isn't part of the pip package (see its module docstring), so it's
imported the same way Task 8's manual verification step did: by adding
scripts/ to sys.path directly.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import test_hypothesis as script  # noqa: E402


def test_save_session_artifacts_writes_full_payload(tmp_path, monkeypatch):
    monkeypatch.setattr(script, "_RUNS_DIR", tmp_path / "runs")

    status_data = {"status": "completed", "artifacts": [{"transform_name": "synthesizer"}]}
    out_path = script._save_session_artifacts("session-123", status_data)

    assert out_path == tmp_path / "runs" / "session-123.json"
    assert json.loads(out_path.read_text(encoding="utf-8")) == status_data


def test_save_session_artifacts_creates_runs_dir_if_missing(tmp_path, monkeypatch):
    runs_dir = tmp_path / "nested" / "runs"
    monkeypatch.setattr(script, "_RUNS_DIR", runs_dir)
    assert not runs_dir.exists()

    script._save_session_artifacts("session-456", {"status": "failed"})

    assert runs_dir.is_dir()
    assert (runs_dir / "session-456.json").exists()
