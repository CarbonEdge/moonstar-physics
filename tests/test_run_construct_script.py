from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import run_construct as script  # noqa: E402


def _result(verdict="PARTIAL"):
    return {
        "status": "completed", "session_id": "local-abc", "verdict": verdict, "best_candidate": "A",
        "elapsed_seconds": 12.3,
        "artifacts": [
            {"transform_name": "Planner", "data": {"response": "{}", "_model": "m/pro", "_input_tokens": 100, "_output_tokens": 50}},
            {"transform_name": "Generator_A", "data": {"response": "{}", "_model": "m/pro", "_input_tokens": 400, "_output_tokens": 900}},
            {"transform_name": "criteria_a", "data": {
                "verdict": verdict, "unmet_hard": [], "unverified_hard": ["iota_nonzero"],
                "checklist": [{"id": "div_free", "hard": True, "status": "met", "note": "",
                               "evidence": {"max_residual": 1e-12}}],
            }},
            {"transform_name": "synthesizer", "data": {"response": f"VERDICT: {verdict}\n\nreport"}},
        ],
    }


def test_save_run_writes_full_payload_under_construct_slug(tmp_path, monkeypatch):
    monkeypatch.setattr(script, "_CONSTRUCTS_DIR", tmp_path)
    path = script._save_run("my-slug", "local-abc", _result())
    assert path == tmp_path / "my-slug" / "runs" / "local-abc.json"
    assert json.loads(path.read_text(encoding="utf-8")) == _result()


def test_usage_totals_group_by_model_and_skip_artifacts_without_usage():
    assert script._usage_totals(_result()) == {"m/pro": {"input_tokens": 500, "output_tokens": 950}}


def test_format_summary_leads_with_verdict_and_states_the_language_rule():
    text = script._format_summary(_result())
    assert text.splitlines()[0] == "VERDICT: PARTIAL"
    assert "div_free" in text and "report" in text
    assert "m/pro" in text and "500" in text
    assert "not novelty" in text.lower()


def test_format_summary_for_failed_run_shows_error():
    text = script._format_summary({"status": "failed", "error": "boom", "artifacts": []})
    assert "boom" in text


def test_main_requires_token(monkeypatch, capsys):
    monkeypatch.delenv("MOONSTAR_AUTH_TOKEN", raising=False)
    assert script.main(["run_construct.py", "constructs/x.yaml"]) == 1
    assert "MOONSTAR_AUTH_TOKEN" in capsys.readouterr().err


def test_main_usage_error():
    assert script.main(["run_construct.py"]) == 2