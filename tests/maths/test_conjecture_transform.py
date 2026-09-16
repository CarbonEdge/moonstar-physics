"""Tests for ConjectureCheckTransform."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from moonstar_physics._compat import SessionContext

from moonstar_physics.maths.conjecture_transform import ConjectureCheckTransform


@pytest.fixture
def ctx() -> AsyncMock:
    return AsyncMock(spec=SessionContext)


def _extractor_input(payload: dict) -> dict:
    return {"Extractor": {"response": json.dumps(payload)}}


# --- primality ---

async def test_primality_true_positive(ctx):
    payload = {
        "claim_type": "conjecture",
        "conjecture_claim": {"conjecture_type": "primality", "n": 17, "claimed_value": True},
    }
    result = await ConjectureCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "consistent"


async def test_primality_false_claim_on_composite(ctx):
    payload = {
        "claim_type": "conjecture",
        "conjecture_claim": {"conjecture_type": "primality", "n": 4, "claimed_value": True},
    }
    result = await ConjectureCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "violated"


async def test_primality_missing_n_is_not_applicable(ctx):
    payload = {
        "claim_type": "conjecture",
        "conjecture_claim": {"conjecture_type": "primality", "claimed_value": True},
    }
    result = await ConjectureCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


# --- diophantine ---

async def test_diophantine_single_variable_solution_found(ctx):
    """x^2 - 4 = 0 has an integer solution (x=2) within a small bound."""
    payload = {
        "claim_type": "conjecture",
        "conjecture_claim": {
            "conjecture_type": "diophantine",
            "equation": "x**2 - 4",
            "variables": ["x"],
            "bound": 10,
            "claimed_value": True,
        },
    }
    result = await ConjectureCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "consistent"


async def test_diophantine_two_variables_solution_found(ctx):
    """x^2 + y^2 = 25 has an integer solution (3, 4) within bound=10."""
    payload = {
        "claim_type": "conjecture",
        "conjecture_claim": {
            "conjecture_type": "diophantine",
            "equation": "x**2 + y**2 - 25",
            "variables": ["x", "y"],
            "bound": 10,
            "claimed_value": True,
        },
    }
    result = await ConjectureCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "consistent"


async def test_diophantine_no_solution_within_bound_is_not_applicable(ctx):
    """x^2 + 1 = 0 has no real (let alone integer) solution — absence of a
    solution within a bounded search must never be reported as 'violated',
    only 'not_applicable' (absence of evidence isn't evidence of absence)."""
    payload = {
        "claim_type": "conjecture",
        "conjecture_claim": {
            "conjecture_type": "diophantine",
            "equation": "x**2 + 1",
            "variables": ["x"],
            "bound": 5,
            "claimed_value": True,
        },
    }
    result = await ConjectureCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_diophantine_over_variable_cap_is_not_applicable(ctx):
    payload = {
        "claim_type": "conjecture",
        "conjecture_claim": {
            "conjecture_type": "diophantine",
            "equation": "x + y + z",
            "variables": ["x", "y", "z"],
            "bound": 10,
            "claimed_value": True,
        },
    }
    result = await ConjectureCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_diophantine_bound_is_capped_at_1000(ctx):
    """Requesting a bound above the 1000-per-variable cap doesn't error —
    it's silently clamped, still finds the in-range solution."""
    payload = {
        "claim_type": "conjecture",
        "conjecture_claim": {
            "conjecture_type": "diophantine",
            "equation": "x**2 - 4",
            "variables": ["x"],
            "bound": 10_000_000,
            "claimed_value": True,
        },
    }
    result = await ConjectureCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "consistent"


# --- sequence_formula ---

async def test_sequence_formula_exact_integer_match(ctx):
    payload = {
        "claim_type": "conjecture",
        "conjecture_claim": {
            "conjecture_type": "sequence_formula",
            "formula": "n**2",
            "variables": ["n"],
            "index": 5,
            "claimed_value": 25,
        },
    }
    result = await ConjectureCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "consistent"


async def test_sequence_formula_integer_mismatch_is_violated(ctx):
    payload = {
        "claim_type": "conjecture",
        "conjecture_claim": {
            "conjecture_type": "sequence_formula",
            "formula": "n**2",
            "variables": ["n"],
            "index": 5,
            "claimed_value": 26,
        },
    }
    result = await ConjectureCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "violated"


async def test_sequence_formula_real_valued_within_tolerance(ctx):
    payload = {
        "claim_type": "conjecture",
        "conjecture_claim": {
            "conjecture_type": "sequence_formula",
            "formula": "1/n",
            "variables": ["n"],
            "index": 4,
            "claimed_value": 0.25,
        },
    }
    result = await ConjectureCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "consistent"


async def test_sequence_formula_missing_index_is_not_applicable(ctx):
    payload = {
        "claim_type": "conjecture",
        "conjecture_claim": {
            "conjecture_type": "sequence_formula",
            "formula": "n**2",
            "variables": ["n"],
            "claimed_value": 25,
        },
    }
    result = await ConjectureCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


# --- dispatch / envelope ---

async def test_unrecognized_conjecture_type_is_not_applicable(ctx):
    payload = {
        "claim_type": "conjecture",
        "conjecture_claim": {"conjecture_type": "collatz_like_thing"},
    }
    result = await ConjectureCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_non_conjecture_claim_type_is_not_applicable(ctx):
    payload = {"claim_type": "identity", "identity_claim": {"lhs": "1", "rhs": "1", "variables": []}}
    result = await ConjectureCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
