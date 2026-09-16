"""Tests for scripts/publish_review.py's retry and error-isolation logic.

The script isn't part of the pip package (see its module docstring), so it's
imported the same way tests/test_hypothesis_script.py does it: by adding
scripts/ to sys.path directly. submit_and_wait (the one network call) is
mocked out with unittest.mock.AsyncMock so no real gateway is needed.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import publish_review  # noqa: E402
from _pipeline_client import PipelineRunError  # noqa: E402


def _completed_status(transform_name: str, response: str, session_id: str = "sess-1") -> dict:
    return {
        "status": "completed",
        "session_id": session_id,
        "artifacts": [{"transform_name": transform_name, "data": {"response": response}}],
    }


async def test_summarize_paper_succeeds_without_retry_when_chunk_summary_completes_first_try():
    chunk_status = _completed_status("chunk_summarizer", "chunk summary ok")
    reduce_status = _completed_status("reduce_summarizer", "final summary text")

    mock_submit = AsyncMock(side_effect=[chunk_status, reduce_status])
    with patch.object(publish_review, "submit_and_wait", mock_submit):
        result = await publish_review._summarize_paper(
            client=None, gateway_url="http://x", token="t", title="Paper", text="one " * 10
        )

    assert result == "final summary text"
    assert mock_submit.call_count == 2  # one chunk + one reduce, no retries


async def test_summarize_paper_retries_once_on_bad_status_then_succeeds():
    bad_status = {"status": "failed"}
    good_chunk_status = _completed_status("chunk_summarizer", "recovered chunk summary")
    reduce_status = _completed_status("reduce_summarizer", "final summary text")

    mock_submit = AsyncMock(side_effect=[bad_status, good_chunk_status, reduce_status])
    with patch.object(publish_review, "submit_and_wait", mock_submit):
        result = await publish_review._summarize_paper(
            client=None, gateway_url="http://x", token="t", title="Paper", text="one " * 10
        )

    assert result == "final summary text"
    assert mock_submit.call_count == 3  # failed chunk attempt + retry + reduce


async def test_summarize_paper_retries_once_on_exception_then_succeeds():
    good_chunk_status = _completed_status("chunk_summarizer", "recovered chunk summary")
    reduce_status = _completed_status("reduce_summarizer", "final summary text")

    mock_submit = AsyncMock(side_effect=[PipelineRunError("timeout"), good_chunk_status, reduce_status])
    with patch.object(publish_review, "submit_and_wait", mock_submit):
        result = await publish_review._summarize_paper(
            client=None, gateway_url="http://x", token="t", title="Paper", text="one " * 10
        )

    assert result == "final summary text"
    assert mock_submit.call_count == 3


async def test_summarize_paper_raises_after_both_attempts_fail():
    mock_submit = AsyncMock(side_effect=[{"status": "failed"}, PipelineRunError("timeout again")])
    with patch.object(publish_review, "submit_and_wait", mock_submit):
        with pytest.raises(PipelineRunError, match="chunk 1"):
            await publish_review._summarize_paper(
                client=None, gateway_url="http://x", token="t", title="Paper", text="one " * 10
            )

    assert mock_submit.call_count == 2  # no reduce call after chunk failure


async def test_test_hypothesis_returns_error_verdict_on_pipeline_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(publish_review, "_REVIEWS_DIR", tmp_path / "reviews")
    mock_run = AsyncMock(side_effect=publish_review.local_pipeline.PipelineRunError("boom"))

    with patch.object(publish_review.local_pipeline, "run_physics_hypothesis", mock_run):
        result = await publish_review._test_hypothesis(
            client=None, gateway_url="http://x", token="t", slug="paper-slug",
            hypothesis="some hypothesis", index=1,
        )

    assert result.verdict == "ERROR"
    assert result.run_path is None


async def test_test_hypothesis_returns_error_verdict_on_non_completed_status(tmp_path, monkeypatch):
    monkeypatch.setattr(publish_review, "_REVIEWS_DIR", tmp_path / "reviews")
    mock_run = AsyncMock(return_value={"status": "failed", "session_id": "abc"})

    with patch.object(publish_review.local_pipeline, "run_physics_hypothesis", mock_run):
        result = await publish_review._test_hypothesis(
            client=None, gateway_url="http://x", token="t", slug="paper-slug",
            hypothesis="some hypothesis", index=1,
        )

    assert result.verdict == "ERROR"
    assert result.run_path == "runs/abc.json"
    run_file = tmp_path / "reviews" / "paper-slug" / "runs" / "abc.json"
    assert run_file.exists()


async def test_test_hypothesis_routes_to_proof_pipeline_when_requested(tmp_path, monkeypatch):
    monkeypatch.setattr(publish_review, "_REVIEWS_DIR", tmp_path / "reviews")
    mock_run = AsyncMock(
        return_value={
            "status": "completed",
            "session_id": "proof-1",
            "artifacts": [
                {"transform_name": "identity_checks", "data": {"verdict": "consistent"}},
                {"transform_name": "synthesizer", "data": {"response": "VERDICT: PLAUSIBLE\n\nchecks out"}},
            ],
        }
    )

    with patch.object(publish_review.local_pipeline, "run_proof_hypothesis", mock_run):
        result = await publish_review._test_hypothesis(
            client=None, gateway_url="http://x", token="t", slug="paper-slug",
            hypothesis="some hypothesis", index=1, review_pipeline="proof_algebra",
        )

    mock_run.assert_awaited_once()
    called_pipeline_path = mock_run.await_args.args[3]
    assert called_pipeline_path.name == "proof_hypothesis.yaml"
    assert result.verdict == "PLAUSIBLE"
    assert result.wave1_results == {"identity_checks": {"verdict": "consistent"}}


async def test_test_hypothesis_routes_to_numerical_pipeline_when_requested(tmp_path, monkeypatch):
    monkeypatch.setattr(publish_review, "_REVIEWS_DIR", tmp_path / "reviews")
    mock_run = AsyncMock(
        return_value={
            "status": "completed",
            "session_id": "numerical-1",
            "artifacts": [
                {"transform_name": "identity_checks", "data": {"verdict": "consistent"}},
                {"transform_name": "evidence_critic", "data": {"verdict": "corroborates"}},
                {"transform_name": "synthesizer", "data": {"response": "VERDICT: PLAUSIBLE\n\nchecks out"}},
            ],
        }
    )

    with patch.object(publish_review.local_pipeline, "run_proof_hypothesis_numerical", mock_run):
        result = await publish_review._test_hypothesis(
            client=None, gateway_url="http://x", token="t", slug="paper-slug",
            hypothesis="some hypothesis", index=1,
            review_pipeline="proof_algebra", numerical_evidence=True, paper_summary="a summary",
        )

    mock_run.assert_awaited_once()
    called_args = mock_run.await_args.args
    assert called_args[0] == "some hypothesis"
    assert called_args[1] == "a summary"
    called_pipeline_path = mock_run.await_args.args[4]
    assert called_pipeline_path.name == "proof_hypothesis_numerical.yaml"
    assert result.verdict == "PLAUSIBLE"
    assert result.wave1_results == {
        "identity_checks": {"verdict": "consistent"},
        "evidence_critic": {"verdict": "corroborates"},
    }


async def test_test_hypothesis_defaults_numerical_evidence_to_false(tmp_path, monkeypatch):
    # numerical_evidence=True is meaningless without review_pipeline="proof_algebra"
    # and must never be passed by a caller that only sets review_pipeline
    # to "proof_algebra" without opting in — the default keeps existing
    # proof_algebra callers (from the Phase 1 plan's own tests) on the
    # non-numerical path.
    monkeypatch.setattr(publish_review, "_REVIEWS_DIR", tmp_path / "reviews")
    mock_run = AsyncMock(
        return_value={
            "status": "completed",
            "session_id": "proof-1",
            "artifacts": [
                {"transform_name": "identity_checks", "data": {"verdict": "consistent"}},
                {"transform_name": "synthesizer", "data": {"response": "VERDICT: PLAUSIBLE\n\nchecks out"}},
            ],
        }
    )

    with patch.object(publish_review.local_pipeline, "run_proof_hypothesis", mock_run):
        result = await publish_review._test_hypothesis(
            client=None, gateway_url="http://x", token="t", slug="paper-slug",
            hypothesis="some hypothesis", index=1, review_pipeline="proof_algebra",
        )

    mock_run.assert_awaited_once()
    assert result.verdict == "PLAUSIBLE"
