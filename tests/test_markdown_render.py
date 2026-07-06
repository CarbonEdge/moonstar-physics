"""Tests for moonstar_physics.paper_review.markdown_render."""
from __future__ import annotations

from moonstar_physics.paper_review.markdown_render import render_review_markdown
from moonstar_physics.paper_review.review_model import HypothesisResult, ReviewData

_MODELS = {"MODEL_EXTRACTOR": "provider/extractor-model", "MODEL_CRITIC": "provider/critic-model"}


def _review(**overrides) -> ReviewData:
    defaults = dict(
        slug="geometric-unity",
        title="Geometric Unity",
        authors=["Eric Weinstein"],
        draft_date="2021-04-01",
        pdf_path="papers/pdfs/geometric-unity.pdf",
        source_url=None,
        summary="A summary of the paper's central claims.",
        hypothesis_results=[
            HypothesisResult(
                hypothesis="The observerse has dimension 14.",
                verdict="CONSISTENT",
                writeup="Full conversational writeup here.",
                wave1_results={"dimension_check": {"verdict": "consistent"}},
                run_path="runs/session-1.json",
            ),
        ],
    )
    defaults.update(overrides)
    return ReviewData(**defaults)


def test_includes_title_and_authors():
    md = render_review_markdown(_review(), _MODELS)
    assert "# Geometric Unity" in md
    assert "**Authors:** Eric Weinstein" in md


def test_pdf_link_is_root_relative_with_two_levels_up():
    md = render_review_markdown(_review(), _MODELS)
    assert "(../../papers/pdfs/geometric-unity.pdf)" in md


def test_includes_draft_date_when_present():
    md = render_review_markdown(_review(), _MODELS)
    assert "**Draft date:** 2021-04-01" in md


def test_omits_draft_date_when_absent():
    md = render_review_markdown(_review(draft_date=None), _MODELS)
    assert "**Draft date:**" not in md


def test_includes_source_url_when_present():
    md = render_review_markdown(_review(source_url="https://example.com/paper"), _MODELS)
    assert "https://example.com/paper" in md


def test_hypothesis_table_links_to_evidence_anchor():
    md = render_review_markdown(_review(), _MODELS)
    assert "| 1 | The observerse has dimension 14. | CONSISTENT | [full writeup](#hypothesis-1) |" in md
    assert "### Hypothesis 1" in md


def test_evidence_section_includes_writeup_and_wave1_results():
    md = render_review_markdown(_review(), _MODELS)
    assert "Full conversational writeup here." in md
    assert "`dimension_check`: consistent" in md


def test_evidence_section_links_to_run_path_verbatim():
    md = render_review_markdown(_review(), _MODELS)
    assert "[Raw run data](runs/session-1.json)" in md


def test_hypothesis_result_without_run_path_omits_raw_data_link():
    review = _review(
        hypothesis_results=[
            HypothesisResult(hypothesis="X", verdict="ERROR", writeup="err", wave1_results={}, run_path=None)
        ]
    )
    md = render_review_markdown(review, _MODELS)
    assert "Raw run data" not in md


def test_includes_abstract_section():
    md = render_review_markdown(_review(), _MODELS)
    assert "## Abstract" in md
    assert "AI-assisted hypothesis-verification review of Geometric Unity" in md


def test_renames_summary_heading_to_paper_summary():
    md = render_review_markdown(_review(), _MODELS)
    assert "## Paper Summary" in md
    assert "## Summary" not in md


def test_includes_methodology_section_naming_configured_models():
    md = render_review_markdown(_review(), _MODELS)
    assert "## Methodology" in md
    assert "provider/extractor-model" in md


def test_includes_references_section_at_end():
    md = render_review_markdown(_review(source_url="https://example.com/paper"), _MODELS)
    assert "## References" in md
    assert md.rstrip().endswith("1. Eric Weinstein (2021). Geometric Unity. https://example.com/paper")
