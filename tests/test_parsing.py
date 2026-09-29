"""Tests for the shared Extractor-output parsing contract."""
from __future__ import annotations

import json

import pytest
from moonstar_physics._compat import NonRetryableTransformError
from moonstar_physics._parsing import parse_extractor_output


def test_parses_unfenced_json():
    payload = {"hypothesis_type": "decay", "particles_involved": ["muon"]}
    input_ = {"Extractor": {"response": json.dumps(payload)}}
    assert parse_extractor_output(input_) == payload


def test_parses_fenced_json():
    payload = {"hypothesis_type": "decay", "particles_involved": ["muon"]}
    fenced = "```json\n" + json.dumps(payload) + "\n```"
    input_ = {"Extractor": {"response": fenced}}
    assert parse_extractor_output(input_) == payload


def test_parses_fenced_json_without_language_tag():
    payload = {"hypothesis_type": "decay"}
    fenced = "```\n" + json.dumps(payload) + "\n```"
    input_ = {"Extractor": {"response": fenced}}
    assert parse_extractor_output(input_) == payload


def test_missing_extractor_key_raises():
    with pytest.raises(NonRetryableTransformError):
        parse_extractor_output({})


def test_extractor_not_a_dict_raises():
    with pytest.raises(NonRetryableTransformError):
        parse_extractor_output({"Extractor": "not a dict"})


def test_missing_response_field_raises():
    with pytest.raises(NonRetryableTransformError):
        parse_extractor_output({"Extractor": {}})


def test_malformed_json_raises():
    with pytest.raises(NonRetryableTransformError):
        parse_extractor_output({"Extractor": {"response": "{not json"}})


def test_json_array_instead_of_object_raises():
    with pytest.raises(NonRetryableTransformError):
        parse_extractor_output({"Extractor": {"response": "[1, 2, 3]"}})


def test_safe_parse_supports_atan2_for_toroidal_angles():
    import sympy
    from moonstar_physics.maths._safe_parse import safe_parse_expr

    expr = safe_parse_expr("atan2(y, x)", ["x", "y"])
    assert expr.func == sympy.atan2
    x, y = sympy.symbols("x y")
    assert sympy.diff(expr, x) == -y / (x**2 + y**2)
