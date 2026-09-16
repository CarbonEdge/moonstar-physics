"""Validates the proof_hypothesis_numerical.yaml dependency graph — same
approach as test_proof_hypothesis_pipeline.py, extended for the doubled
numerical-evidence stage."""
from __future__ import annotations

from pathlib import Path

from moonstar_physics._pipeline_spec import PipelineSpec

_PIPELINE_PATH = Path(__file__).parent.parent / "pipelines" / "proof_hypothesis_numerical.yaml"

_PHASE1_WAVE_NAMES = ["identity_checks", "proof_critic"]
_NUMERICAL_ROOT_NAMES = ["reduction_a", "reduction_b"]


def _load_spec_with_placeholders_filled() -> PipelineSpec:
    text = _PIPELINE_PATH.read_text(encoding="utf-8")
    for key in ("MODEL_EXTRACTOR", "MODEL_CRITIC", "MODEL_DECISION_MAKER"):
        text = text.replace("{{" + key + "}}", "test/placeholder-model")
    return PipelineSpec.from_yaml_text(text)


def test_pipeline_loads_with_all_12_nodes():
    spec = _load_spec_with_placeholders_filled()
    names = {t.name for t in spec.transforms}
    assert names == {
        "Extractor",
        "identity_checks",
        "proof_critic",
        "reduction_a",
        "reduction_b",
        "experiment_codegen_a",
        "experiment_codegen_b",
        "sandbox_runner_a",
        "sandbox_runner_b",
        "evidence_critic",
        "devils_advocate",
        "synthesizer",
    }


def test_phase1_nodes_depend_only_on_extractor_unchanged_from_phase1():
    spec = _load_spec_with_placeholders_filled()
    by_name = {t.name: t for t in spec.transforms}
    for name in _PHASE1_WAVE_NAMES:
        assert by_name[name].deps == ["Extractor"], f"{name} deps: {by_name[name].deps}"


def test_reduction_nodes_have_no_pipeline_deps():
    # reduction_a/b are root nodes fed via initial_input (hypothesis +
    # paper_summary), same pattern as Extractor — not wired to any
    # upstream pipeline node.
    spec = _load_spec_with_placeholders_filled()
    by_name = {t.name: t for t in spec.transforms}
    for name in _NUMERICAL_ROOT_NAMES:
        assert by_name[name].deps == [], f"{name} deps: {by_name[name].deps}"


def test_codegen_nodes_depend_on_their_own_reduction():
    spec = _load_spec_with_placeholders_filled()
    by_name = {t.name: t for t in spec.transforms}
    assert by_name["experiment_codegen_a"].deps == ["reduction_a"]
    assert by_name["experiment_codegen_b"].deps == ["reduction_b"]


def test_sandbox_nodes_depend_on_their_own_codegen():
    spec = _load_spec_with_placeholders_filled()
    by_name = {t.name: t for t in spec.transforms}
    assert by_name["sandbox_runner_a"].deps == ["experiment_codegen_a"]
    assert by_name["sandbox_runner_b"].deps == ["experiment_codegen_b"]


def test_evidence_critic_depends_on_both_reductions_and_both_sandbox_runs():
    spec = _load_spec_with_placeholders_filled()
    by_name = {t.name: t for t in spec.transforms}
    assert sorted(by_name["evidence_critic"].deps) == sorted(
        ["reduction_a", "reduction_b", "sandbox_runner_a", "sandbox_runner_b"]
    )


def test_devils_advocate_depends_on_phase1_checks_plus_evidence_critic():
    spec = _load_spec_with_placeholders_filled()
    by_name = {t.name: t for t in spec.transforms}
    assert sorted(by_name["devils_advocate"].deps) == sorted([*_PHASE1_WAVE_NAMES, "evidence_critic"])


def test_synthesizer_depends_on_everything_upstream():
    spec = _load_spec_with_placeholders_filled()
    by_name = {t.name: t for t in spec.transforms}
    assert sorted(by_name["synthesizer"].deps) == sorted(
        [*_PHASE1_WAVE_NAMES, "evidence_critic", "devils_advocate"]
    )


def test_transform_types_match_registered_entry_points():
    spec = _load_spec_with_placeholders_filled()
    by_name = {t.name: t for t in spec.transforms}
    assert by_name["identity_checks"].type == "AlgebraicClaimsCheckTransform"
    assert by_name["sandbox_runner_a"].type == "NumericalExperimentTransform"
    assert by_name["sandbox_runner_b"].type == "NumericalExperimentTransform"
    for name in ("Extractor", "proof_critic", "reduction_a", "reduction_b",
                 "experiment_codegen_a", "experiment_codegen_b", "evidence_critic",
                 "devils_advocate", "synthesizer"):
        assert by_name[name].type == "LlmTransform"


def test_reduction_a_and_b_have_identical_config_for_independent_sampling():
    # Independence comes from being two separate LLM calls, not from
    # different prompts — both nodes must run the exact same prompt/model.
    spec = _load_spec_with_placeholders_filled()
    by_name = {t.name: t for t in spec.transforms}
    assert by_name["reduction_a"].config == by_name["reduction_b"].config


def test_budget_is_raised_for_the_numerical_stage():
    import yaml

    data = yaml.safe_load(_PIPELINE_PATH.read_text(encoding="utf-8"))
    assert data["budget"]["max_usd"] == 3.00
    assert data["budget"]["max_wallclock_seconds"] == 600
