"""Renders ReviewData into the published GitHub Pages site's HTML pages.

Assets (PDF, raw run JSON) are copied into docs/ by build_site.py so the
published site is self-contained; hrefs computed here are relative to
where build_site.py places each page and copies each asset — NOT the
repo-relative paths stored on ReviewData, which are for the standalone
review.md instead (see markdown_render.py).
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment

from moonstar_physics.paper_review.review_model import ReviewData


def _run_href(slug: str, run_path: str | None) -> str | None:
    if not run_path:
        return None
    return f"{slug}/runs/{Path(run_path).name}"


def render_review_html(review: ReviewData, env: Environment) -> str:
    template = env.get_template("review.html.j2")
    hypotheses = [
        {
            "hypothesis": hr.hypothesis,
            "verdict": hr.verdict,
            "writeup": hr.writeup,
            "wave1_results": hr.wave1_results,
            "run_href": _run_href(review.slug, hr.run_path),
        }
        for hr in review.hypothesis_results
    ]
    return template.render(
        review=review,
        hypotheses=hypotheses,
        pdf_href=f"../papers/{review.slug}.pdf",
    )


def render_index_html(reviews: list[ReviewData], env: Environment) -> str:
    template = env.get_template("index.html.j2")
    return template.render(reviews=reviews)
