"""Validates the physics_hypothesis.yaml dependency graph.

Uses moonstar_executor.models.PipelineSpec directly (same class the gateway
worker uses to parse pipeline YAML) rather than re-implementing YAML parsing,
so this test fails if the YAML doesn't actually match what the executor
will do with it — e.g. a stray `depends_on:` key (which TransformSpec has
no field for) would be silently ignored by Pydantic and only show up here
as a wrong `deps` list, not as a parse error.
"""
from __future__ import annotations

from pathlib import Path

from moonstar_executor.models import PipelineSpec

_PIPELINE_PATH = Path(__file__).parent.parent / "pipelines" / "physics_hypothesis.yaml"

_WAVE_1_NAMES = [
    "conservation_check",
    "qm_calculation",
    "reference_lookup",
    "dimension_check",
    "theory_critic",
]


def _load_spec_with_placeholders_filled() -> PipelineSpec:
    text = _PIPELINE_PATH.read_text(encoding="utf-8")
    for key in ("MODEL_EXTRACTOR", "MODEL_CRITIC", "MODEL_DECISION_MAKER"):
        text = text.replace("{{" + key + "}}", "test/placeholder-model")
    import yaml
    data = yaml.safe_load(text)
    return PipelineSpec.model_validate({**data["pipeline"], "transforms": data["transforms"]})


def test_pipeline_loads():
    spec = _load_spec_with_placeholders_filled()
    names = [t.name for t in spec.transforms]
    assert names == [
        "Extractor",
        "conservation_check",
        "qm_calculation",
        "reference_lookup",
        "dimension_check",
        "theory_critic",
        "devils_advocate",
        "synthesizer",
    ]


def test_wave_1_depends_only_on_extractor():
    spec = _load_spec_with_placeholders_filled()
    by_name = {t.name: t for t in spec.transforms}
    for name in _WAVE_1_NAMES:
        assert by_name[name].deps == ["Extractor"], f"{name} deps: {by_name[name].deps}"


def test_devils_advocate_depends_on_all_wave_1():
    spec = _load_spec_with_placeholders_filled()
    by_name = {t.name: t for t in spec.transforms}
    assert sorted(by_name["devils_advocate"].deps) == sorted(_WAVE_1_NAMES)


def test_synthesizer_depends_on_devils_advocate_and_all_wave_1():
    spec = _load_spec_with_placeholders_filled()
    by_name = {t.name: t for t in spec.transforms}
    assert sorted(by_name["synthesizer"].deps) == sorted([*_WAVE_1_NAMES, "devils_advocate"])


def test_wave_1_transform_types_match_registered_entry_points():
    spec = _load_spec_with_placeholders_filled()
    by_name = {t.name: t for t in spec.transforms}
    assert by_name["conservation_check"].type == "ConservationLawCheckTransform"
    assert by_name["qm_calculation"].type == "QMCalculationTransform"
    assert by_name["reference_lookup"].type == "ReferenceDataLookupTransform"
    assert by_name["dimension_check"].type == "DimensionConsistencyTransform"
    assert by_name["theory_critic"].type == "LlmTransform"
