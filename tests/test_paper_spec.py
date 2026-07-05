"""Tests for moonstar_physics.paper_review.paper_spec."""
from __future__ import annotations

import pytest

from moonstar_physics.paper_review.paper_spec import PaperSpecError, load_paper_spec

_VALID_YAML = """
title: "Geometric Unity"
authors: ["Eric Weinstein"]
draft_date: "2021-04-01"
pdf: "papers/pdfs/geometric-unity.pdf"
source_url: null
hypotheses:
  - "Claim one."
  - "Claim two."
"""


def test_loads_valid_paper_spec(tmp_path):
    path = tmp_path / "geometric-unity.yaml"
    path.write_text(_VALID_YAML, encoding="utf-8")

    spec = load_paper_spec(path)

    assert spec.slug == "geometric-unity"
    assert spec.title == "Geometric Unity"
    assert spec.authors == ["Eric Weinstein"]
    assert spec.draft_date == "2021-04-01"
    assert spec.pdf == "papers/pdfs/geometric-unity.pdf"
    assert spec.source_url is None
    assert spec.hypotheses == ["Claim one.", "Claim two."]


def test_optional_fields_can_be_omitted(tmp_path):
    path = tmp_path / "minimal.yaml"
    path.write_text(
        'title: "T"\nauthors: ["A"]\npdf: "papers/pdfs/t.pdf"\nhypotheses: ["h"]\n',
        encoding="utf-8",
    )

    spec = load_paper_spec(path)

    assert spec.draft_date is None
    assert spec.source_url is None


def test_invalid_yaml_raises_paper_spec_error(tmp_path):
    path = tmp_path / "broken.yaml"
    path.write_text("title: [unclosed", encoding="utf-8")

    with pytest.raises(PaperSpecError, match="invalid YAML"):
        load_paper_spec(path)


def test_non_mapping_top_level_raises(tmp_path):
    path = tmp_path / "list.yaml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")

    with pytest.raises(PaperSpecError, match="must be a mapping"):
        load_paper_spec(path)


@pytest.mark.parametrize("missing_field", ["title", "authors", "pdf", "hypotheses"])
def test_missing_required_field_raises(tmp_path, missing_field):
    fields = {
        "title": 'title: "T"',
        "authors": 'authors: ["A"]',
        "pdf": 'pdf: "papers/pdfs/t.pdf"',
        "hypotheses": 'hypotheses: ["h"]',
    }
    del fields[missing_field]
    path = tmp_path / "incomplete.yaml"
    path.write_text("\n".join(fields.values()) + "\n", encoding="utf-8")

    with pytest.raises(PaperSpecError, match=missing_field):
        load_paper_spec(path)


def test_empty_hypotheses_list_raises(tmp_path):
    path = tmp_path / "empty-hyp.yaml"
    path.write_text(
        'title: "T"\nauthors: ["A"]\npdf: "papers/pdfs/t.pdf"\nhypotheses: []\n',
        encoding="utf-8",
    )

    with pytest.raises(PaperSpecError, match="hypotheses"):
        load_paper_spec(path)
