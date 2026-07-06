"""Scans reviews/*/review_data.json and renders the docs/ GitHub Pages site.

Run any time, over all published papers:
    python scripts/build_site.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

sys.path.insert(0, str(Path(__file__).parent.parent))
from moonstar_physics.paper_review.html_render import render_index_html, render_review_html
from moonstar_physics.paper_review.review_model import ReviewData

_ROOT_DIR = Path(__file__).parent.parent
_REVIEWS_DIR = _ROOT_DIR / "reviews"
_DOCS_DIR = _ROOT_DIR / "docs"
_TEMPLATES_DIR = _ROOT_DIR / "templates"
_MODELS_PATH = _ROOT_DIR / "pipelines" / "models.json"


def _load_reviews() -> list[ReviewData]:
    reviews = []
    for data_path in sorted(_REVIEWS_DIR.glob("*/review_data.json")):
        data = json.loads(data_path.read_text(encoding="utf-8"))
        reviews.append(ReviewData.from_dict(data))
    return reviews


def _copy_assets(review: ReviewData) -> None:
    docs_papers = _DOCS_DIR / "papers"
    docs_papers.mkdir(parents=True, exist_ok=True)
    src_pdf = _ROOT_DIR / review.pdf_path
    if src_pdf.exists():
        shutil.copyfile(src_pdf, docs_papers / f"{review.slug}.pdf")

    runs_src = _REVIEWS_DIR / review.slug / "runs"
    if runs_src.is_dir():
        runs_dst = _DOCS_DIR / "reviews" / review.slug / "runs"
        runs_dst.mkdir(parents=True, exist_ok=True)
        for run_file in runs_src.glob("*.json"):
            shutil.copyfile(run_file, runs_dst / run_file.name)


def build_site() -> None:
    reviews = _load_reviews()
    if not reviews:
        print("No reviews found under reviews/*/review_data.json — nothing to build.")
        return

    models = json.loads(_MODELS_PATH.read_text(encoding="utf-8"))
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
    )

    (_DOCS_DIR / "reviews").mkdir(parents=True, exist_ok=True)
    for review in reviews:
        _copy_assets(review)
        html = render_review_html(review, env, models)
        (_DOCS_DIR / "reviews" / f"{review.slug}.html").write_text(html, encoding="utf-8")
        print(f"Built docs/reviews/{review.slug}.html")

    (_DOCS_DIR / "index.html").write_text(render_index_html(reviews, env), encoding="utf-8")
    print("Built docs/index.html")


if __name__ == "__main__":
    build_site()
