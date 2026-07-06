"""Tests for moonstar_physics.paper_review.scienceopen."""
from __future__ import annotations

from moonstar_physics.paper_review.review_model import HypothesisResult, ReviewData
from moonstar_physics.paper_review.scienceopen import (
    Citation,
    build_scienceopen_metadata,
    format_citation,
    render_abstract,
    render_methodology,
    render_references,
)


def _review(**overrides) -> ReviewData:
    defaults = dict(
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
                writeup="Writeup.",
                wave1_results={},
                run_path="runs/session-1.json",
            ),
        ],
    )
    defaults.update(overrides)
    return ReviewData(**defaults)


def test_format_citation_single_author_with_url():
    citation = format_citation(_review(source_url="https://example.com/paper"))
    assert citation == Citation(text="Eric Weinstein (2021). Geometric Unity.", url="https://example.com/paper")


def test_format_citation_uses_n_d_when_draft_date_missing():
    citation = format_citation(_review(draft_date=None))
    assert citation.text == "Eric Weinstein (n.d.). Geometric Unity."


def test_format_citation_joins_two_authors_with_and():
    citation = format_citation(_review(authors=["A. Author", "B. Author"]))
    assert citation.text == "A. Author and B. Author (2021). Geometric Unity."


def test_format_citation_joins_three_authors_with_oxford_comma():
    citation = format_citation(_review(authors=["A. Author", "B. Author", "C. Author"]))
    assert citation.text == "A. Author, B. Author, and C. Author (2021). Geometric Unity."


def test_render_references_includes_url_when_present():
    md = render_references(_review(source_url="https://example.com/paper"))
    assert md == "## References\n\n1. Eric Weinstein (2021). Geometric Unity. https://example.com/paper\n"


def test_render_references_omits_url_when_absent():
    md = render_references(_review(source_url=None))
    assert md == "## References\n\n1. Eric Weinstein (2021). Geometric Unity.\n"


def test_render_abstract_includes_title_authors_and_count():
    abstract = render_abstract(_review())
    assert "Geometric Unity" in abstract
    assert "Eric Weinstein" in abstract
    assert "testing 1 curated claim" in abstract


def test_render_abstract_pluralizes_claim_count():
    review = _review(
        hypothesis_results=[
            HypothesisResult(hypothesis="A", verdict="CONSISTENT", writeup="", wave1_results={}, run_path=None),
            HypothesisResult(hypothesis="B", verdict="INCONSISTENT", writeup="", wave1_results={}, run_path=None),
        ]
    )
    abstract = render_abstract(review)
    assert "testing 2 curated claims" in abstract


def test_render_abstract_includes_verdict_tally_sorted_alphabetically():
    review = _review(
        hypothesis_results=[
            HypothesisResult(hypothesis="A", verdict="INCONSISTENT", writeup="", wave1_results={}, run_path=None),
            HypothesisResult(hypothesis="B", verdict="INCONCLUSIVE", writeup="", wave1_results={}, run_path=None),
            HypothesisResult(hypothesis="C", verdict="INCONSISTENT", writeup="", wave1_results={}, run_path=None),
            HypothesisResult(hypothesis="D", verdict="INCONCLUSIVE", writeup="", wave1_results={}, run_path=None),
        ]
    )
    abstract = render_abstract(review)
    assert "Verdicts: 2 inconclusive, 2 inconsistent." in abstract


def test_render_abstract_handles_no_hypotheses():
    review = _review(hypothesis_results=[])
    abstract = render_abstract(review)
    assert "Verdicts: no hypotheses tested." in abstract


def test_render_methodology_names_models_from_config():
    text = render_methodology({"MODEL_EXTRACTOR": "provider/extractor-model", "MODEL_CRITIC": "provider/critic-model"})
    assert "provider/extractor-model" in text
    assert "provider/critic-model" in text


def test_render_methodology_falls_back_to_unknown_for_missing_keys():
    text = render_methodology({})
    assert "unknown" in text


def test_build_scienceopen_metadata_shape():
    review = _review(source_url="https://example.com/paper")
    author = {"name": "Melvin Chotu", "orcid": "0000-0000-0000-0000"}
    models = {"MODEL_EXTRACTOR": "x", "MODEL_CRITIC": "y"}

    metadata = build_scienceopen_metadata(review, author, models)

    assert metadata["submission_title"] == "AI-Assisted Hypothesis Verification of Geometric Unity: A Moonstar Physics Review"
    assert metadata["abstract"] == render_abstract(review)
    assert metadata["authors"] == [author]
    assert metadata["references"] == ["Eric Weinstein (2021). Geometric Unity. https://example.com/paper"]
    assert metadata["pdf_path"] == "reviews/geometric-unity/review.pdf"
    assert "keywords" in metadata
    assert "license_note" in metadata
