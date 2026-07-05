"""Tests for scripts/build_site.py's pure-logic helpers (filesystem only,
no Jinja2 rendering — that's covered by test_html_render.py).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import build_site as script  # noqa: E402
from moonstar_physics.paper_review.review_model import ReviewData


def _sample_review_dict(slug: str) -> dict:
    return {
        "slug": slug,
        "title": "Sample Paper",
        "authors": ["A. Author"],
        "draft_date": None,
        "pdf_path": f"papers/pdfs/{slug}.pdf",
        "source_url": None,
        "summary": "A summary.",
        "hypothesis_results": [],
    }


def test_load_reviews_reads_all_review_data_json(tmp_path, monkeypatch):
    reviews_dir = tmp_path / "reviews"
    (reviews_dir / "paper-a").mkdir(parents=True)
    (reviews_dir / "paper-a" / "review_data.json").write_text(
        json.dumps(_sample_review_dict("paper-a")), encoding="utf-8"
    )
    monkeypatch.setattr(script, "_REVIEWS_DIR", reviews_dir)

    reviews = script._load_reviews()

    assert len(reviews) == 1
    assert isinstance(reviews[0], ReviewData)
    assert reviews[0].slug == "paper-a"


def test_load_reviews_returns_empty_list_when_no_reviews(tmp_path, monkeypatch):
    monkeypatch.setattr(script, "_REVIEWS_DIR", tmp_path / "reviews")
    assert script._load_reviews() == []


def test_copy_assets_copies_pdf_and_run_files(tmp_path, monkeypatch):
    (tmp_path / "papers" / "pdfs").mkdir(parents=True)
    (tmp_path / "papers" / "pdfs" / "paper-a.pdf").write_bytes(b"%PDF-fake")
    runs_dir = tmp_path / "reviews" / "paper-a" / "runs"
    runs_dir.mkdir(parents=True)
    (runs_dir / "session-1.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(script, "_ROOT_DIR", tmp_path)
    monkeypatch.setattr(script, "_REVIEWS_DIR", tmp_path / "reviews")
    monkeypatch.setattr(script, "_DOCS_DIR", tmp_path / "docs")

    review = ReviewData.from_dict(_sample_review_dict("paper-a"))
    script._copy_assets(review)

    assert (tmp_path / "docs" / "papers" / "paper-a.pdf").exists()
    assert (tmp_path / "docs" / "reviews" / "paper-a" / "runs" / "session-1.json").exists()


def test_copy_assets_skips_missing_pdf_without_error(tmp_path, monkeypatch):
    monkeypatch.setattr(script, "_ROOT_DIR", tmp_path)
    monkeypatch.setattr(script, "_REVIEWS_DIR", tmp_path / "reviews")
    monkeypatch.setattr(script, "_DOCS_DIR", tmp_path / "docs")

    review = ReviewData.from_dict(_sample_review_dict("no-pdf-paper"))
    script._copy_assets(review)  # must not raise

    assert not (tmp_path / "docs" / "papers" / "no-pdf-paper.pdf").exists()
