"""Renders ReviewData into the published GitHub Pages site's HTML pages.

Assets (PDF, raw run JSON) are copied into docs/ by build_site.py so the
published site is self-contained; hrefs computed here are relative to
where build_site.py places each page and copies each asset — NOT the
repo-relative paths stored on ReviewData, which are for the standalone
review.md instead (see markdown_render.py).
"""
from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment
from markupsafe import Markup, escape

from moonstar_physics.paper_review.review_model import ReviewData

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")


def _inline_bold_to_html(text: str) -> Markup:
    """Converts **bold** emphasis to <strong> tags without adding paragraph
    wrappers. Used for inline content like verdict fields."""
    escaped = str(escape(text))
    bolded = _BOLD_RE.sub(r"<strong>\1</strong>", escaped)
    return Markup(bolded)


def _prose_to_html(text: str) -> Markup:
    """Converts simple LLM-generated markdown prose (paragraphs separated by
    blank lines, **bold** emphasis) into safe HTML. Escapes the raw text
    first, then applies formatting — so this never introduces an injection
    vector even though the input is LLM output, not a static template."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    rendered = []
    for para in paragraphs:
        escaped = str(escape(para))
        bolded = _BOLD_RE.sub(r"<strong>\1</strong>", escaped)
        rendered.append(f"<p>{bolded}</p>")
    return Markup("\n".join(rendered))


def _run_href(slug: str, run_path: str | None) -> str | None:
    if not run_path:
        return None
    return f"{slug}/runs/{Path(run_path).name}"


def render_review_html(review: ReviewData, env: Environment) -> str:
    template = env.get_template("review.html.j2")
    hypotheses = [
        {
            "hypothesis": hr.hypothesis,
            "verdict": _inline_bold_to_html(hr.verdict) if hr.verdict else "",
            "writeup": _prose_to_html(hr.writeup),
            "wave1_results": hr.wave1_results,
            "run_href": _run_href(review.slug, hr.run_path),
        }
        for hr in review.hypothesis_results
    ]
    return template.render(
        review=review,
        hypotheses=hypotheses,
        summary_html=_prose_to_html(review.summary),
        pdf_href=f"../papers/{review.slug}.pdf",
    )


def render_index_html(reviews: list[ReviewData], env: Environment) -> str:
    template = env.get_template("index.html.j2")
    return template.render(reviews=reviews)
