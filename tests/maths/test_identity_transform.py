"""Tests for IdentityCheckTransform."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from moonstar_physics._compat import SessionContext

from moonstar_physics.maths.identity_transform import IdentityCheckTransform


@pytest.fixture
def ctx() -> AsyncMock:
    return AsyncMock(spec=SessionContext)


def _extractor_input(payload: dict) -> dict:
    return {"Extractor": {"response": json.dumps(payload)}}


async def test_polynomial_identity_is_consistent(ctx):
    """x^2 - 1 == (x-1)(x+1): simplify reduces the diff to exactly 0 directly."""
    payload = {
        "claim_type": "identity",
        "identity_claim": {"lhs": "x**2 - 1", "rhs": "(x - 1)*(x + 1)", "variables": ["x"]},
    }
    result = await IdentityCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "consistent"


async def test_constant_mismatch_is_violated(ctx):
    """2 + 2 != 5: no free variables, diff is a nonzero constant."""
    payload = {
        "claim_type": "identity",
        "identity_claim": {"lhs": "2 + 2", "rhs": "5", "variables": []},
    }
    result = await IdentityCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "violated"


async def test_non_identity_polynomial_is_violated(ctx):
    """x^2 == x does not hold for all x (only x=0,1) — genuinely not an
    identity, so both symbolic diff and numeric sampling disagree."""
    payload = {
        "claim_type": "identity",
        "identity_claim": {"lhs": "x**2", "rhs": "x", "variables": ["x"]},
    }
    result = await IdentityCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "violated"


async def test_domain_dependent_identity_is_not_applicable_not_violated(ctx):
    """sqrt(x^2) == |x| holds for all real x, but sympy's default simplify
    (no real-assumption on the bare Symbol) does not reduce this diff to
    exactly 0 — a well-known sympy limitation. Numeric sampling over real
    points agrees everywhere, so the verdict must downgrade to
    not_applicable, never confidently 'consistent' (5 samples isn't proof)
    and never 'violated' (that would be a false positive from a symbolic
    simplify miss on something that's actually true)."""
    payload = {
        "claim_type": "identity",
        "identity_claim": {"lhs": "sqrt(x**2)", "rhs": "Abs(x)", "variables": ["x"]},
    }
    result = await IdentityCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_malformed_expression_is_not_applicable(ctx):
    payload = {
        "claim_type": "identity",
        "identity_claim": {"lhs": "x +", "rhs": "1", "variables": ["x"]},
    }
    result = await IdentityCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_injection_attempt_is_not_applicable(ctx):
    payload = {
        "claim_type": "identity",
        "identity_claim": {"lhs": "__import__('os').system('echo hi')", "rhs": "0", "variables": []},
    }
    result = await IdentityCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_missing_lhs_is_not_applicable(ctx):
    payload = {
        "claim_type": "identity",
        "identity_claim": {"rhs": "1", "variables": []},
    }
    result = await IdentityCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_non_identity_claim_type_is_not_applicable(ctx):
    payload = {"claim_type": "conjecture", "conjecture_claim": {"conjecture_type": "primality", "n": 7}}
    result = await IdentityCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
