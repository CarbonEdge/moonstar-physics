"""Structure test for pipelines/construct.yaml — node names/deps/types that
run_construct relies on. No network."""
from __future__ import annotations

import json
from pathlib import Path

from moonstar_physics._pipeline_spec import PipelineSpec, render_pipeline_yaml

_ROOT = Path(__file__).parent.parent
_PIPELINE = _ROOT / "pipelines" / "construct.yaml"
_MODELS = _ROOT / "pipelines" / "models.json"


def _spec() -> PipelineSpec:
    return PipelineSpec.from_yaml_text(render_pipeline_yaml(_PIPELINE, _MODELS))


def test_models_json_has_construct_entries():
    models = json.loads(_MODELS.read_text(encoding="utf-8"))
    assert models["MODEL_PLANNER"] and models["MODEL_GENERATOR"] and models["MODEL_CONSTRUCT_REVIEW"]
    assert models["MODEL_GENERATOR"] == "deepseek/deepseek-v4-pro"      # hard work only
    assert models["MODEL_PLANNER"] == models["MODEL_CONSTRUCT_REVIEW"] == "~deepseek/deepseek-v4-flash-latest"


def test_no_unfilled_placeholders():
    assert "{{" not in render_pipeline_yaml(_PIPELINE, _MODELS)


def test_node_names_and_types():
    by_name = _spec().by_name()
    assert {n: t.type for n, t in by_name.items()} == {
        "Planner": "LlmTransform", "Derive_A": "LlmTransform", "Derive_B": "LlmTransform",
        "Generator_A": "LlmTransform", "Generator_B": "LlmTransform",
        "checks_a": "VectorCalculusCheckTransform", "checks_b": "VectorCalculusCheckTransform",
        "iota_a": "IotaTraceTransform", "iota_b": "IotaTraceTransform",
        "criteria_a": "ConstructCriteriaTransform", "criteria_b": "ConstructCriteriaTransform",
        "construct_critic": "LlmTransform", "devils_advocate": "LlmTransform",
        "synthesizer": "LlmTransform",
    }


def test_dependency_graph():
    by_name = _spec().by_name()
    assert {n: sorted(t.deps) for n, t in by_name.items()} == {
        "Planner": [], "Derive_A": ["Planner"], "Derive_B": ["Planner"],
        "Generator_A": ["Derive_A"], "Generator_B": ["Derive_B"],
        "checks_a": ["Generator_A"], "iota_a": ["Generator_A"], "criteria_a": ["checks_a", "iota_a"],
        "checks_b": ["Generator_B"], "iota_b": ["Generator_B"], "criteria_b": ["checks_b", "iota_b"],
        "construct_critic": ["criteria_a", "criteria_b"],
        "devils_advocate": ["construct_critic"],
        "synthesizer": ["construct_critic", "devils_advocate"],
    }


def test_local_nodes_name_their_sources_and_carry_no_spec_path():
    by_name = _spec().by_name()
    for label in ("a", "b"):
        gen = f"Generator_{label.upper()}"
        assert by_name[f"checks_{label}"].config["source"] == gen
        assert by_name[f"iota_{label}"].config["source"] == gen
        assert by_name[f"criteria_{label}"].config["sources"] == ["checks", "iota"]
    assert all("spec_path" not in t.config for t in by_name.values())


def test_llm_nodes_have_model_and_system_prompt():
    for t in _spec().transforms:
        if t.type == "LlmTransform":
            assert t.config["model"] and "/" in t.config["model"], t.name
            assert len(t.config["system"]) > 200, t.name
            assert t.config["max_tokens"] >= 1000, t.name


def test_generator_prompt_states_the_json_schema_and_no_prose_rule():
    gen = _spec().by_name()["Generator_A"].config["system"]
    for needle in ('"defs"', '"objects"', '"params"', "Cartesian", "ONLY the JSON"):
        assert needle in gen
    assert _spec().by_name()["Generator_A"].config["system"] == _spec().by_name()["Generator_B"].config["system"]


def test_derive_uses_pro_and_a_timeout_above_the_gateway_default():
    by_name = _spec().by_name()
    models = json.loads(_MODELS.read_text(encoding="utf-8"))
    for name in ("Derive_A", "Derive_B"):
        cfg = by_name[name].config
        assert cfg["model"] == models["MODEL_GENERATOR"]
        assert cfg["timeout_seconds"] > 180          # moonstar-rs default is 180 s
        assert cfg["max_tokens"] >= 16000            # reasoning counts against it
    assert by_name["Derive_A"].config == by_name["Derive_B"].config


def test_formalise_step_is_cheap_and_low_reasoning():
    cfg = _spec().by_name()["Generator_A"].config
    models = json.loads(_MODELS.read_text(encoding="utf-8"))
    assert cfg["model"] == models["MODEL_CONSTRUCT_REVIEW"]
    assert cfg["reasoning"] == {"effort": "low"}
    assert "derivation" in cfg["system"] and "Do NOT re-derive" in cfg["system"]

