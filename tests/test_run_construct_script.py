from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import run_construct as script  # noqa: E402


def _result(verdict="PARTIAL"):
    return {
        "status": "completed", "session_id": "local-abc", "verdict": verdict, "best_candidate": "A",
        "best_round": 2, "stop_reason": "max_rounds", "elapsed_seconds": 12.3, "cost_usd": 0.0123,
        "unpriced_models": [], "token_usage": {"m/pro": {"input_tokens": 500, "output_tokens": 950}},
        "rounds": [
            {"round": 1, "verdict": "NOT_FOUND", "best_candidate": "B", "cost_usd": 0.005, "artifacts": []},
            {"round": 2, "verdict": verdict, "best_candidate": "A", "cost_usd": 0.0073, "artifacts": []},
        ],
        "artifacts": [
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


def test_format_summary_leads_with_verdict_and_shows_rounds_and_cost():
    text = script._format_summary(_result())
    assert text.splitlines()[0] == "VERDICT: PARTIAL"
    assert "div_free" in text and "report" in text
    assert "rounds: 2" in text and "stop: max_rounds" in text and "best: round 2" in text
    assert "round 1: NOT_FOUND" in text and "round 2: PARTIAL" in text
    assert "$0.0123" in text and "m/pro" in text and "500" in text
    assert "not novelty" in text.lower()


def test_format_summary_flags_unpriced_models():
    r = _result()
    r["unpriced_models"] = ["mystery/model"]
    assert "mystery/model" in script._format_summary(r)


def test_format_summary_for_failed_run_shows_error():
    assert "boom" in script._format_summary({"status": "failed", "error": "boom", "artifacts": []})


def test_parse_args_reads_max_rounds():
    assert script._parse_args(["run_construct.py", "s.yaml"]) == ("s.yaml", None, None)
    assert script._parse_args(["run_construct.py", "s.yaml", "--max-rounds", "3"]) == ("s.yaml", 3, None)
    assert script._parse_args(["run_construct.py", "s.yaml", "--models", "m.json", "--max-rounds", "2"]) == ("s.yaml", 2, "m.json")
    assert script._parse_args(["run_construct.py", "s.yaml", "--bogus", "1"]) is None
    assert script._parse_args(["run_construct.py"]) is None
    assert script._parse_args(["run_construct.py", "s.yaml", "--max-rounds", "x"]) is None


def test_main_requires_token(monkeypatch, capsys):
    monkeypatch.delenv("MOONSTAR_AUTH_TOKEN", raising=False)
    assert script.main(["run_construct.py", "constructs/x.yaml"]) == 1
    assert "MOONSTAR_AUTH_TOKEN" in capsys.readouterr().err


def test_main_usage_error():
    assert script.main(["run_construct.py"]) == 2


def test_format_summary_distinguishes_reported_from_estimated_cost():
    exact = {**_result(), "cost_is_exact": True, "cost_truncated_usd": 0.004}
    text = script._format_summary(exact)
    assert "reported by OpenRouter" in text and "$0.0040 wasted on truncated retries" in text
    est = {**_result(), "cost_is_exact": False, "cost_reported_usd": 0.0}
    assert "ESTIMATED" in script._format_summary(est)
    partial = {**_result(), "cost_is_exact": False, "cost_reported_usd": 0.005}
    assert "$0.0050 of it reported" in script._format_summary(partial)
