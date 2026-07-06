"""Renders a ReviewData into the standalone review.md document — the
portable artifact suitable for reading on GitHub or uploading to
ScienceOpen. Plain string building, no template engine (Jinja2 is reserved
for the HTML site layer in html_render.py).
"""
from __future__ import annotations

from moonstar_physics.paper_review.review_model import ReviewData
from moonstar_physics.paper_review.scienceopen import render_abstract, render_methodology, render_references

# review.md always lives at reviews/<slug>/review.md — two directories
# below the repo root — so repo-root-relative paths (like pdf_path) need
# this fixed prefix to resolve when the file is viewed in place.
_ROOT_RELATIVE_PREFIX = "../../"


def render_review_markdown(review: ReviewData, models: dict[str, str]) -> str:
    lines: list[str] = []
    lines.append(f"# {review.title}")
    lines.append("")
    lines.append(f"**Authors:** {', '.join(review.authors)}  ")
    if review.draft_date:
        lines.append(f"**Draft date:** {review.draft_date}  ")
    pdf_href = f"{_ROOT_RELATIVE_PREFIX}{review.pdf_path}"
    lines.append(f"**PDF:** [{review.pdf_path}]({pdf_href})  ")
    if review.source_url:
        lines.append(f"**Source:** [{review.source_url}]({review.source_url})  ")
    lines.append("")

    lines.append("## Abstract")
    lines.append("")
    lines.append(render_abstract(review))
    lines.append("")

    lines.append("## Paper Summary")
    lines.append("")
    lines.append(review.summary)
    lines.append("")

    lines.append("## Methodology")
    lines.append("")
    lines.append(render_methodology(models))
    lines.append("")

    lines.append("## Tested Hypotheses")
    lines.append("")
    lines.append("| # | Hypothesis | Verdict | Details |")
    lines.append("|---|---|---|---|")
    for i, hr in enumerate(review.hypothesis_results, start=1):
        lines.append(f"| {i} | {hr.hypothesis} | {hr.verdict} | [full writeup](#hypothesis-{i}) |")
    lines.append("")

    lines.append("## Evidence")
    lines.append("")
    for i, hr in enumerate(review.hypothesis_results, start=1):
        lines.append(f"### Hypothesis {i}")
        lines.append("")
        lines.append(f"**Claim:** {hr.hypothesis}")
        lines.append("")
        lines.append(f"**Verdict:** {hr.verdict}")
        lines.append("")
        lines.append(hr.writeup)
        lines.append("")
        if hr.wave1_results:
            lines.append("**Deterministic checks:**")
            lines.append("")
            for name in sorted(hr.wave1_results):
                result = hr.wave1_results[name]
                verdict = result.get("verdict") if isinstance(result, dict) else result
                lines.append(f"- `{name}`: {verdict}")
            lines.append("")
        if hr.run_path:
            lines.append(f"[Raw run data]({hr.run_path})")
            lines.append("")

    lines.append(render_references(review))

    return "\n".join(lines)
