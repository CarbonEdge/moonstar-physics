"""Validates the proof_hypothesis.yaml dependency graph — same approach as
test_physics_hypothesis_pipeline.py."""
from __future__ import annotations

from pathlib import Path

from moonstar_physics._pipeline_spec import PipelineSpec

_PIPELINE_PATH = Path(__file__).parent.parent / "pipelines" / "proof_hypothesis.yaml"

_WAVE_1_NAMES = ["identity_checks", "proof_critic"]


def _load_spec_with_placeholders_filled() -> PipelineSpec:
    text = _PIPELINE_PATH.read_text(encoding="utf-8")
    for key in ("MODEL_EXTRACTOR", "MODEL_CRITIC", "MODEL_DECISION_MAKER"):
        text = text.replace("{{" + key + "}}", "test/placeholder-model")
    return PipelineSpec.from_yaml_text(text)


def test_pipeline_loads():
    spec = _load_spec_with_placeholders_filled()
    names = [t.name for t in spec.transforms]
    assert names == [
        "Extractor",
        "identity_checks",
        "proof_critic",
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
    assert by_name["identity_checks"].type == "AlgebraicClaimsCheckTransform"
    assert by_name["proof_critic"].type == "LlmTransform"


def test_budget_is_raised_relative_to_physics_hypothesis():
    import yaml

    data = yaml.safe_load(_PIPELINE_PATH.read_text(encoding="utf-8"))
    assert data["budget"]["max_usd"] == 1.00
    assert data["budget"]["max_wallclock_seconds"] == 180
