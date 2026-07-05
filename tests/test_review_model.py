"""Tests for moonstar_physics.paper_review.review_model."""
from __future__ import annotations

from moonstar_physics.paper_review.review_model import HypothesisResult, ReviewData


def _sample_review() -> ReviewData:
    return ReviewData(
        slug="geometric-unity",
        title="Geometric Unity",
        authors=["Eric Weinstein"],
        draft_date="2021-04-01",
        pdf_path="papers/pdfs/geometric-unity.pdf",
        source_url=None,
        summary="A summary of the paper.",
        hypothesis_results=[
            HypothesisResult(
                hypothesis="Claim one.",
                verdict="CONSISTENT",
                writeup="Full writeup text.",
                wave1_results={"dimension_check": {"verdict": "consistent"}},
                run_path="runs/session-1.json",
            ),
        ],
    )


def test_to_dict_round_trips_through_from_dict():
    review = _sample_review()

    restored = ReviewData.from_dict(review.to_dict())

    assert restored == review


def test_to_dict_produces_plain_json_serializable_structure():
    import json

    review = _sample_review()
    # Must not raise — every field is JSON-serializable.
    json.dumps(review.to_dict())


def test_from_dict_handles_empty_hypothesis_results():
    data = {
        "slug": "empty-paper",
        "title": "Empty",
        "authors": ["Nobody"],
        "draft_date": None,
        "pdf_path": "papers/pdfs/empty.pdf",
        "source_url": None,
        "summary": "",
        "hypothesis_results": [],
    }

    review = ReviewData.from_dict(data)

    assert review.hypothesis_results == []
