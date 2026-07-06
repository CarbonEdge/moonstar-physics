"""Tests for scripts/_pipeline_client.py's pure-logic helpers.

Follows the same sys.path-insertion pattern as test_hypothesis_script.py,
since scripts/ isn't part of the pip package.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import _pipeline_client as client  # noqa: E402


def test_render_pipeline_yaml_substitutes_placeholders(tmp_path):
    models_path = tmp_path / "models.json"
    models_path.write_text(json.dumps({"MODEL_FOO": "provider/model-x"}), encoding="utf-8")
    pipeline_path = tmp_path / "pipeline.yaml"
    pipeline_path.write_text('model: "{{MODEL_FOO}}"\n', encoding="utf-8")

    result = client.render_pipeline_yaml(pipeline_path, models_path)

    assert result == 'model: "provider/model-x"\n'


def test_find_artifact_returns_data_for_matching_transform():
    status = {"artifacts": [{"transform_name": "synthesizer", "data": {"response": "hello"}}]}
    assert client.find_artifact(status, "synthesizer") == {"response": "hello"}


def test_find_artifact_returns_none_for_missing_transform():
    status = {"artifacts": [{"transform_name": "synthesizer", "data": {"response": "hello"}}]}
    assert client.find_artifact(status, "nonexistent") is None


def test_find_artifact_returns_empty_dict_when_data_missing():
    status = {"artifacts": [{"transform_name": "synthesizer"}]}
    assert client.find_artifact(status, "synthesizer") == {}


def test_extract_verdict_strips_markdown_emphasis():
    writeup = "Some conversational text.\n\n**INCONCLUSIVE**"
    assert client.extract_verdict(writeup) == "INCONCLUSIVE"


def test_extract_verdict_handles_plain_last_line():
    writeup = "Some text.\nCONSISTENT"
    assert client.extract_verdict(writeup) == "CONSISTENT"


def test_extract_verdict_returns_unknown_for_empty_writeup():
    assert client.extract_verdict("   \n  \n") == "UNKNOWN"


def test_extract_verdict_prefers_leading_verdict_line():
    writeup = "VERDICT: INCONSISTENT\n\nHere's a long conversational explanation that"
    assert client.extract_verdict(writeup) == "INCONSISTENT"


def test_extract_verdict_leading_verdict_line_survives_truncation():
    writeup = "VERDICT: INCONCLUSIVE\n\nAlright, let's walk through this step by step, just as"
    assert client.extract_verdict(writeup) == "INCONCLUSIVE"


def test_strip_leading_verdict_line_removes_prefix_and_blank_line():
    writeup = "VERDICT: PLAUSIBLE\n\nHere's the explanation."
    assert client.strip_leading_verdict_line(writeup) == "Here's the explanation."


def test_strip_leading_verdict_line_leaves_writeup_without_prefix_unchanged():
    writeup = "Some text.\nCONSISTENT"
    assert client.strip_leading_verdict_line(writeup) == writeup
