"""The in-memory/on-disk data model for a published paper review.

publish_review.py builds a ReviewData, persists it as
reviews/<slug>/review_data.json (via to_dict()), and renders it to
reviews/<slug>/review.md. build_site.py later reloads it (via from_dict())
to render the GitHub Pages HTML, without re-parsing markdown.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class HypothesisResult:
    hypothesis: str
    verdict: str
    writeup: str
    wave1_results: dict[str, Any] = field(default_factory=dict)
    run_path: str | None = None


@dataclass
class ReviewData:
    slug: str
    title: str
    authors: list[str]
    draft_date: str | None
    pdf_path: str
    source_url: str | None
    summary: str
    hypothesis_results: list[HypothesisResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ReviewData:
        hypothesis_results = [
            HypothesisResult(**hr) for hr in data.get("hypothesis_results", [])
        ]
        return ReviewData(
            slug=data["slug"],
            title=data["title"],
            authors=data["authors"],
            draft_date=data.get("draft_date"),
            pdf_path=data["pdf_path"],
            source_url=data.get("source_url"),
            summary=data["summary"],
            hypothesis_results=hypothesis_results,
        )
