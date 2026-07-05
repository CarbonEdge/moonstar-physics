"""Tests for moonstar_physics.paper_review.html_render.

Uses the real templates/ directory so a broken template fails these tests
directly, rather than only surfacing at build_site.py runtime.
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from moonstar_physics.paper_review.html_render import render_index_html, render_review_html
from moonstar_physics.paper_review.review_model import HypothesisResult, ReviewData

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
    )


def _review() -> ReviewData:
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
                hypothesis="The observerse has dimension 14.",
                verdict="CONSISTENT",
                writeup="Full writeup text.",
                wave1_results={"dimension_check": {"verdict": "consistent"}},
                run_path="runs/session-1.json",
            ),
        ],
    )


def test_render_review_html_includes_title_and_verdict():
    html = render_review_html(_review(), _env())
    assert "Geometric Unity" in html
    assert "CONSISTENT" in html


def test_render_review_html_pdf_href_points_into_docs_papers():
    html = render_review_html(_review(), _env())
    assert 'href="../papers/geometric-unity.pdf"' in html


def test_render_review_html_run_href_points_into_slug_runs_dir():
    html = render_review_html(_review(), _env())
    assert 'href="geometric-unity/runs/session-1.json"' in html


def test_render_review_html_omits_run_link_when_no_run_path():
    review = _review()
    review.hypothesis_results[0].run_path = None
    html = render_review_html(review, _env())
    assert "Raw run data" not in html


def test_render_index_html_lists_review_with_link():
    html = render_index_html([_review()], _env())
    assert "Geometric Unity" in html
    assert 'href="reviews/geometric-unity.html"' in html
