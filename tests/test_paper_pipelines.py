"""Validates paper_chunk_summary.yaml and paper_reduce_summary.yaml — same
approach as test_physics_hypothesis_pipeline.py: parse via PipelineSpec
(the class the gateway worker actually uses), not hand-rolled YAML checks.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from moonstar_executor.models import PipelineSpec

_PIPELINES_DIR = Path(__file__).parent.parent / "pipelines"


def _load_spec(filename: str) -> PipelineSpec:
    text = (_PIPELINES_DIR / filename).read_text(encoding="utf-8")
    text = text.replace("{{MODEL_SUMMARIZER}}", "test/placeholder-model")
    data = yaml.safe_load(text)
    return PipelineSpec.model_validate({**data["pipeline"], "transforms": data["transforms"]})


def test_paper_chunk_summary_pipeline_loads():
    spec = _load_spec("paper_chunk_summary.yaml")
    assert [t.name for t in spec.transforms] == ["chunk_summarizer"]


def test_paper_chunk_summary_transform_is_llm_transform_with_no_deps():
    spec = _load_spec("paper_chunk_summary.yaml")
    transform = spec.transforms[0]
    assert transform.type == "LlmTransform"
    assert transform.deps == []


def test_paper_reduce_summary_pipeline_loads():
    spec = _load_spec("paper_reduce_summary.yaml")
    assert [t.name for t in spec.transforms] == ["reduce_summarizer"]


def test_paper_reduce_summary_transform_is_llm_transform_with_no_deps():
    spec = _load_spec("paper_reduce_summary.yaml")
    transform = spec.transforms[0]
    assert transform.type == "LlmTransform"
    assert transform.deps == []


def test_models_json_declares_summarizer_model():
    import json

    models = json.loads((_PIPELINES_DIR / "models.json").read_text(encoding="utf-8"))
    assert "MODEL_SUMMARIZER" in models
