"""Tests for the ConstructSpec loader/validator."""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from moonstar_physics.construct_spec import (
    ConstructSpecError,
    load_construct_spec,
    parse_construct_spec,
)

_REAL_SPEC = Path(__file__).resolve().parents[1] / "constructs" / "analytic-3d-mhd-equilibrium.yaml"


def _valid() -> dict:
    return {
        "slug": "toy",
        "title": "Toy",
        "statement": "Find a field.",
        "unknowns": [{"name": "B", "kind": "vector_field"}],
        "criteria": {
            "hard": [
                {"id": "div_free", "check": "divergence_zero", "expr": "div(B)"},
                {"id": "nonconst_p", "check": "numeric_sample", "kind": "nonconstant", "target": "p"},
            ],
            "soft": [{"id": "novel", "check": "manual", "note": "human check"}],
        },
        "mechanism_hints": ["axis torsion"],
        "degrees_of_freedom": [{"name": "epsilon", "range": [0.05, 0.9]}],
        "sample_box": {"x": [-1.5, 1.5], "y": [-1.5, 1.5], "z": [-0.5, 0.5]},
        "budget": {"max_usd": 15.0, "max_wallclock_seconds": 3600, "max_rounds": 5},
    }


def test_parses_valid_spec():
    spec = parse_construct_spec(_valid())
    assert spec.slug == "toy"
    assert [c.id for c in spec.hard_criteria()] == ["div_free", "nonconst_p"]
    assert [c.id for c in spec.soft_criteria()] == ["novel"]
    assert spec.degrees_of_freedom[0].name == "epsilon"
    assert spec.degrees_of_freedom[0].low == 0.05
    assert spec.sample_box["z"] == (-0.5, 0.5)


def test_real_spec_file_loads():
    spec = load_construct_spec(_REAL_SPEC)
    assert spec.slug == "analytic-3d-mhd-equilibrium"
    hard_ids = {c.id for c in spec.hard_criteria()}
    assert {"div_free", "flux_surface", "force_balance", "nonaxisym", "iota_nonzero"} <= hard_ids


def test_unsupported_check_rejected():
    data = _valid()
    data["criteria"]["hard"][0]["check"] = "vibes"
    with pytest.raises(ConstructSpecError, match="vibes"):
        parse_construct_spec(data)


def test_hard_manual_criterion_rejected():
    data = _valid()
    data["criteria"]["hard"].append({"id": "novel_hard", "check": "manual"})
    with pytest.raises(ConstructSpecError, match="manual"):
        parse_construct_spec(data)


def test_requires_at_least_one_hard_gate_criterion():
    data = _valid()
    data["criteria"]["hard"] = [
        {"id": "nonconst_p", "check": "numeric_sample", "kind": "nonconstant", "target": "p"}
    ]
    with pytest.raises(ConstructSpecError, match="gate"):
        parse_construct_spec(data)


def test_duplicate_criterion_ids_rejected():
    data = _valid()
    data["criteria"]["soft"].append({"id": "div_free", "check": "manual"})
    with pytest.raises(ConstructSpecError, match="duplicate"):
        parse_construct_spec(data)


def test_gate_check_requires_expr():
    data = _valid()
    del data["criteria"]["hard"][0]["expr"]
    with pytest.raises(ConstructSpecError, match="expr"):
        parse_construct_spec(data)


def test_numeric_sample_requires_known_kind_and_target():
    data = _valid()
    data["criteria"]["hard"][1]["kind"] = "sparkly"
    with pytest.raises(ConstructSpecError, match="sparkly"):
        parse_construct_spec(data)
    data = _valid()
    del data["criteria"]["hard"][1]["target"]
    with pytest.raises(ConstructSpecError, match="target"):
        parse_construct_spec(data)


def test_missing_sample_box_axis_rejected():
    data = _valid()
    del data["sample_box"]["z"]
    with pytest.raises(ConstructSpecError, match="sample_box"):
        parse_construct_spec(data)


def test_inverted_range_rejected():
    data = _valid()
    data["degrees_of_freedom"][0]["range"] = [0.9, 0.05]
    with pytest.raises(ConstructSpecError, match="range"):
        parse_construct_spec(data)


def test_external_validator_not_in_v1_schema():
    data = _valid()
    data["external_validator"] = {"tool": "desc"}
    with pytest.raises(ConstructSpecError, match="external_validator"):
        parse_construct_spec(data)


def test_parse_does_not_mutate_input():
    data = _valid()
    snapshot = copy.deepcopy(data)
    parse_construct_spec(data)
    assert data == snapshot


def test_sandbox_experiment_requires_known_kind():
    data = _valid()
    data["criteria"]["hard"].append({"id": "trace", "check": "sandbox_experiment"})
    with pytest.raises(ConstructSpecError, match="sandbox_experiment kind"):
        parse_construct_spec(data)
    data["criteria"]["hard"][-1]["kind"] = "warp_drive"
    with pytest.raises(ConstructSpecError, match="sandbox_experiment kind"):
        parse_construct_spec(data)
    data["criteria"]["hard"][-1]["kind"] = "iota_nonzero"
    assert parse_construct_spec(data).hard_criteria()[-1].kind == "iota_nonzero"


def test_real_spec_sandbox_criteria_have_kinds():
    spec = load_construct_spec(Path(__file__).parent.parent / "constructs" / "analytic-3d-mhd-equilibrium.yaml")
    kinds = {c.id: c.kind for c in spec.criteria if c.check == "sandbox_experiment"}
    assert kinds == {"iota_nonzero": "iota_nonzero", "iota_noninteger": "iota_noninteger"}


def test_second_spec_loads_and_is_axisymmetric_control():
    from pathlib import Path
    from moonstar_physics.construct_spec import load_construct_spec

    spec = load_construct_spec(Path(__file__).parent.parent / "constructs" / "axisymmetric-mhd-equilibrium.yaml")
    ids = {c.id for c in spec.criteria}
    assert "nonaxisym" not in ids and "iota_nonzero" in ids
    assert spec.degrees_of_freedom == ()