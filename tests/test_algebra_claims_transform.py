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
    entry = result["checked_claims"][0]
    assert entry["description"] == "malformed"
    assert entry["verdict"] == "not_applicable"
    assert entry["detail"].startswith("expression rejected:")
    assert set(entry) == {"description", "verdict", "detail"}


async def test_malformed_claim_entry_counts_as_not_applicable(ctx):
    payload = {"proof_context": "x", "algebraic_claims": ["not-a-dict"]}
    result = await AlgebraicClaimsCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
    assert result["checked_claims"][0]["verdict"] == "not_applicable"


async def test_not_applicable_entry_carries_detail_string(ctx):
    """The finding this change addresses: a not_applicable verdict must carry
    the *why* (IdentityCheckTransform's `detail`), not just a bare verdict word."""
    payload = {
        "proof_context": "x",
        "algebraic_claims": [
            {"description": "rejected expr", "lhs": "__import__('os')", "rhs": "1", "variables": []},
        ],
    }
    result = await AlgebraicClaimsCheckTransform(_extractor_input(payload), {}, ctx)
    entry = result["checked_claims"][0]
    assert entry["verdict"] == "not_applicable"
    assert isinstance(entry.get("detail"), str)
    assert entry["detail"]  # non-empty
    assert entry["detail"].startswith("expression rejected:")


async def test_consistent_entry_carries_lhs_rhs_diff(ctx):
    payload = {
        "proof_context": "x",
        "algebraic_claims": [
            {"description": "trivial", "lhs": "2 + 2", "rhs": "4", "variables": []},
        ],
    }
    result = await AlgebraicClaimsCheckTransform(_extractor_input(payload), {}, ctx)
    entry = result["checked_claims"][0]
    assert entry["verdict"] == "consistent"
    assert entry["lhs"] == "2 + 2"
    assert entry["rhs"] == "4"
    assert entry["diff"] == "0"
    # bookkeeping fields must not leak into per-claim entries
    assert not any(k.startswith("_") for k in entry)


async def test_violated_entry_carries_lhs_rhs_diff(ctx):
    payload = {
        "proof_context": "x",
        "algebraic_claims": [
            {"description": "bad", "lhs": "2 + 2", "rhs": "5", "variables": []},
        ],
    }
    result = await AlgebraicClaimsCheckTransform(_extractor_input(payload), {}, ctx)
    entry = result["checked_claims"][0]
    assert entry["verdict"] == "violated"
    assert entry["lhs"] == "2 + 2"
    assert entry["rhs"] == "5"
    assert entry["diff"] not in (None, "0")
    assert not any(k.startswith("_") for k in entry)


async def test_malformed_claim_entry_has_detail_and_no_bookkeeping_keys(ctx):
    payload = {"proof_context": "x", "algebraic_claims": ["not-a-dict"]}
    result = await AlgebraicClaimsCheckTransform(_extractor_input(payload), {}, ctx)
    entry = result["checked_claims"][0]
    assert entry == {
        "description": "<malformed claim entry>",
        "verdict": "not_applicable",
        "detail": "claim entry is not an object",
    }
