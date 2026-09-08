"""Loads and validates a paper's YAML definition (papers/<slug>.yaml):
metadata plus the curated list of hypotheses to test.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


class PaperSpecError(ValueError):
    """Raised when a paper YAML file is missing required fields or malformed."""


@dataclass
class PaperSpec:
    slug: str
    title: str
    authors: list[str]
    draft_date: str | None
    pdf: str
    source_url: str | None
    hypotheses: list[str]
    # Override for chunking.chunk_text's words_per_chunk default (3000).
    # Only needed for papers long enough to exceed max_chunks (20) at the
    # default chunk size — widening the chunk size keeps the chunk COUNT
    # (and therefore LLM-call budget) within the existing cap rather than
    # raising the cap itself.
    words_per_chunk: int | None = None


def _require_string(data: dict, key: str, path: Path) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PaperSpecError(f"{path}: '{key}' is required and must be a non-empty string")
    return value


def _require_string_list(data: dict, key: str, path: Path) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list) or not value or not all(isinstance(v, str) for v in value):
        raise PaperSpecError(f"{path}: '{key}' is required and must be a non-empty list of strings")
    return value


def _optional_string(data: dict, key: str, path: Path) -> str | None:
    value = data.get(key)
    if value is not None and not isinstance(value, str):
        raise PaperSpecError(f"{path}: '{key}' must be a string if present")
    return value


def _optional_positive_int(data: dict, key: str, path: Path) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PaperSpecError(f"{path}: '{key}' must be a positive integer if present")
    return value


def load_paper_spec(path: Path) -> PaperSpec:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise PaperSpecError(f"{path}: invalid YAML: {e}") from e

    if not isinstance(data, dict):
        raise PaperSpecError(f"{path}: top-level YAML must be a mapping")

    return PaperSpec(
        slug=path.stem,
        title=_require_string(data, "title", path),
        authors=_require_string_list(data, "authors", path),
        draft_date=_optional_string(data, "draft_date", path),
        pdf=_require_string(data, "pdf", path),
        source_url=_optional_string(data, "source_url", path),
        hypotheses=_require_string_list(data, "hypotheses", path),
        words_per_chunk=_optional_positive_int(data, "words_per_chunk", path),
    )
