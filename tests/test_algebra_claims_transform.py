"""Tests for AlgebraicClaimsCheckTransform — loops IdentityCheckTransform
over a proof hypothesis's transcribed algebraic sub-claims and aggregates
the per-claim verdicts."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from moonstar_physics._compat import SessionContext
from moonstar_physics.algebra_claims_transform import AlgebraicClaimsCheckTransform


@pytest.fixture
def ctx() -> AsyncMock:
    return AsyncMock(spec=SessionContext)


def _extractor_input(payload: dict) -> dict:
    return {"Extractor": {"response": json.dumps(payload)}}


async def test_empty_claims_list_is_not_applicable(ctx):
    payload = {"proof_context": "no equations stated", "algebraic_claims": []}
    result = await AlgebraicClaimsCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_missing_claims_key_is_not_applicable(ctx):
    payload = {"proof_context": "no equations stated"}
    result = await AlgebraicClaimsCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_non_list_claims_is_not_applicable(ctx):
    payload = {"proof_context": "x", "algebraic_claims": "not-a-list"}
    result = await AlgebraicClaimsCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_all_consistent_claims_yield_consistent(ctx):
    payload = {
        "proof_context": "x",
        "algebraic_claims": [
            {"description": "a+d=1", "lhs": "(Rational(1,2)+h)+(Rational(1,2)-h)", "rhs": "1", "variables": ["h"]},
            {"description": "trivial", "lhs": "2 + 2", "rhs": "4", "variables": []},
        ],
    }
    result = await AlgebraicClaimsCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "consistent"
    assert [c["verdict"] for c in result["checked_claims"]] == ["consistent", "consistent"]


async def test_one_violated_claim_makes_whole_result_violated(ctx):
    payload = {
        "proof_context": "x",
        "algebraic_claims": [
            {"description": "good", "lhs": "2 + 2", "rhs": "4", "variables": []},
            {"description": "bad", "lhs": "2 + 2", "rhs": "5", "variables": []},
        ],
    }
    result = await AlgebraicClaimsCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "violated"
    assert [c["verdict"] for c in result["checked_claims"]] == ["consistent", "violated"]


async def test_all_not_applicable_claims_yield_not_applicable(ctx):
    payload = {
        "proof_context": "x",
        "algebraic_claims": [
            {"description": "malformed", "lhs": "x +", "rhs": "1", "variables": ["x"]},
        ],
    }
    result = await AlgebraicClaimsCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["checked_claims"] == [{"description": "malformed", "verdict": "not_applicable"}]


async def test_malformed_claim_entry_counts_as_not_applicable(ctx):
    payload = {"proof_context": "x", "algebraic_claims": ["not-a-dict"]}
    result = await AlgebraicClaimsCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["checked_claims"][0]["verdict"] == "not_applicable"
