"""Tests for DimensionConsistencyTransform."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from moonstar_core import SessionContext
from moonstar_core.exceptions import NonRetryableTransformError

from moonstar_physics.dimension_transform import DimensionConsistencyTransform


@pytest.fixture
def ctx() -> AsyncMock:
    return AsyncMock(spec=SessionContext)


def _extractor_input(payload: dict) -> dict:
    return {"Extractor": {"response": json.dumps(payload)}}


async def test_fiber_bundle_consistent_matches_geometric_unity_claim(ctx):
    """GU's observerse: base 4D + fiber = symmetric bilinear forms on a 4D
    tangent space (metrics), dimension 4*5/2=10 -> total 14, matching GU."""
    payload = {
        "dimension_claims": [
            {
                "object": "observerse U",
                "claim_type": "fiber_bundle",
                "base_dimension": 4,
                "fiber_kind": "symmetric_bilinear_form",
                "fiber_base_dimension": 4,
                "claimed_dimension": 14,
            }
        ]
    }
    result = await DimensionConsistencyTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "consistent"
    assert result["results"][0]["computed_dimension"] == 14


async def test_spinor_representation_consistent_matches_geometric_unity_claim(ctx):
    """GU's spinor bundle S(U): Spin(14) -> complex spinor rep dimension 2^7=128."""
    payload = {
        "dimension_claims": [
            {"object": "spinor bundle S(U)", "claim_type": "spinor_representation", "n": 14, "claimed_dimension": 128}
        ]
    }
    result = await DimensionConsistencyTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "consistent"
    assert result["results"][0]["computed_dimension"] == 128


async def test_fiber_bundle_wrong_claim_is_violated(ctx):
    payload = {
        "dimension_claims": [
            {
                "object": "bogus bundle",
                "claim_type": "fiber_bundle",
                "base_dimension": 4,
                "fiber_kind": "symmetric_bilinear_form",
                "fiber_base_dimension": 4,
                "claimed_dimension": 999,
            }
        ]
    }
    result = await DimensionConsistencyTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "violated"
    assert result["results"][0]["computed_dimension"] == 14


async def test_spinor_wrong_claim_is_violated(ctx):
    payload = {
        "dimension_claims": [
            {"object": "bogus spinor", "claim_type": "spinor_representation", "n": 14, "claimed_dimension": 64}
        ]
    }
    result = await DimensionConsistencyTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "violated"


async def test_unrecognized_fiber_kind_is_not_applicable(ctx):
    payload = {
        "dimension_claims": [
            {
                "object": "weird bundle",
                "claim_type": "fiber_bundle",
                "base_dimension": 4,
                "fiber_kind": "quaternionic_form",
                "fiber_base_dimension": 4,
                "claimed_dimension": 14,
            }
        ]
    }
    result = await DimensionConsistencyTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_unrecognized_claim_type_is_not_applicable(ctx):
    payload = {
        "dimension_claims": [
            {"object": "something else", "claim_type": "cohomology_dimension", "claimed_dimension": 5}
        ]
    }
    result = await DimensionConsistencyTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_malformed_non_dict_entry_is_skipped_not_crashed(ctx):
    payload = {"dimension_claims": ["not a dict", 42, None]}
    result = await DimensionConsistencyTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_non_numeric_field_in_entry_is_skipped_not_crashed(ctx):
    payload = {
        "dimension_claims": [
            {
                "object": "bad entry",
                "claim_type": "fiber_bundle",
                "base_dimension": "four",
                "fiber_kind": "symmetric_bilinear_form",
                "fiber_base_dimension": 4,
                "claimed_dimension": 14,
            }
        ]
    }
    result = await DimensionConsistencyTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_non_list_dimension_claims_raises_nonretryable(ctx):
    payload = {"dimension_claims": "fourteen"}
    with pytest.raises(NonRetryableTransformError):
        await DimensionConsistencyTransform(_extractor_input(payload), {}, ctx)


async def test_missing_dimension_claims_is_not_applicable(ctx):
    payload = {"hypothesis_type": "property_claim"}
    result = await DimensionConsistencyTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_empty_dimension_claims_list_is_not_applicable(ctx):
    payload = {"dimension_claims": []}
    result = await DimensionConsistencyTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_mixed_claims_one_consistent_one_violated_is_overall_violated(ctx):
    payload = {
        "dimension_claims": [
            {
                "object": "observerse U",
                "claim_type": "fiber_bundle",
                "base_dimension": 4,
                "fiber_kind": "symmetric_bilinear_form",
                "fiber_base_dimension": 4,
                "claimed_dimension": 14,
            },
            {"object": "bogus spinor", "claim_type": "spinor_representation", "n": 14, "claimed_dimension": 1},
        ]
    }
    result = await DimensionConsistencyTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "violated"
    assert len(result["results"]) == 2


async def test_huge_n_does_not_hang_or_crash(ctx):
    """n far beyond any real dimension claim must be rejected instantly, not
    trigger a big-integer exponentiation blowup (2**(n//2) has no natural
    overflow ceiling the way float arithmetic does)."""
    payload = {
        "dimension_claims": [
            {"object": "absurd", "claim_type": "spinor_representation", "n": 10 ** 18, "claimed_dimension": 128}
        ]
    }
    result = await DimensionConsistencyTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_unhashable_claim_type_is_skipped_not_crashed(ctx):
    """A malformed claim_type (e.g. a list, from a broken Extractor JSON) must
    not crash dict.get() with an unhashable-type TypeError."""
    payload = {
        "dimension_claims": [
            {"object": "bad claim_type", "claim_type": ["fiber_bundle"], "claimed_dimension": 14}
        ]
    }
    result = await DimensionConsistencyTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_unhashable_fiber_kind_is_skipped_not_crashed(ctx):
    payload = {
        "dimension_claims": [
            {
                "object": "bad fiber_kind",
                "claim_type": "fiber_bundle",
                "base_dimension": 4,
                "fiber_kind": ["symmetric_bilinear_form"],
                "fiber_base_dimension": 4,
                "claimed_dimension": 14,
            }
        ]
    }
    result = await DimensionConsistencyTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_vector_and_antisymmetric_fiber_kinds(ctx):
    """Sanity-check the two fiber_kind formulas not covered by the GU example."""
    payload = {
        "dimension_claims": [
            {
                "object": "vector fiber test",
                "claim_type": "fiber_bundle",
                "base_dimension": 1,
                "fiber_kind": "vector",
                "fiber_base_dimension": 5,
                "claimed_dimension": 6,
            },
            {
                "object": "2-form fiber test",
                "claim_type": "fiber_bundle",
                "base_dimension": 0,
                "fiber_kind": "antisymmetric_bilinear_form",
                "fiber_base_dimension": 4,
                "claimed_dimension": 6,
            },
        ]
    }
    result = await DimensionConsistencyTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "consistent"
