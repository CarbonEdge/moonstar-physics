"""Tests for ReferenceDataLookupTransform."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from moonstar_core import SessionContext
from moonstar_core.exceptions import NonRetryableTransformError

from moonstar_physics.reference_lookup_transform import ReferenceDataLookupTransform


@pytest.fixture
def ctx() -> AsyncMock:
    return AsyncMock(spec=SessionContext)


def _extractor_input(payload: dict) -> dict:
    return {"Extractor": {"response": json.dumps(payload)}}


async def test_known_particles_found(ctx):
    payload = {"particles_involved": ["muon", "electron"]}
    result = await ReferenceDataLookupTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "consistent"
    assert set(result["found"].keys()) == {"muon", "electron"}
    assert result["unknown"] == []


async def test_unknown_particle_reported(ctx):
    payload = {"particles_involved": ["muon", "gravitino"]}
    result = await ReferenceDataLookupTransform(_extractor_input(payload), {}, ctx)
    assert "gravitino" in result["unknown"]
    assert "muon" in result["found"]
    assert result["verdict"] == "consistent"  # at least one particle was found


async def test_all_unknown_particles_is_unknown_particle_verdict(ctx):
    payload = {"particles_involved": ["gravitino", "axion"]}
    result = await ReferenceDataLookupTransform(_extractor_input(payload), {}, ctx)
    assert result["found"] == {}
    assert result["verdict"] == "unknown_particle"


async def test_missing_particles_involved_is_not_applicable(ctx):
    payload = {"hypothesis_type": "property_claim"}
    result = await ReferenceDataLookupTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_antiparticle_flips_signed_charge_and_lepton_number(ctx):
    payload = {
        "particles_involved": ["electron_neutrino"],
        "final_state": [{"particle": "electron_neutrino", "antiparticle": True, "count": 1}],
    }
    result = await ReferenceDataLookupTransform(_extractor_input(payload), {}, ctx)
    signed = result["signed"]
    assert len(signed) == 1
    assert signed[0]["particle"] == "electron_neutrino"
    assert signed[0]["antiparticle"] is True
    assert signed[0]["effective_charge"] == "0"
    assert signed[0]["effective_electron_number"] == -1


async def test_non_antiparticle_signed_entry_keeps_sign(ctx):
    payload = {
        "particles_involved": ["muon"],
        "initial_state": [{"particle": "muon", "antiparticle": False, "count": 1}],
    }
    result = await ReferenceDataLookupTransform(_extractor_input(payload), {}, ctx)
    signed = result["signed"]
    assert signed[0]["effective_charge"] == "-1"
    assert signed[0]["effective_muon_number"] == 1


async def test_non_list_particles_involved_raises_nonretryable(ctx):
    payload = {"particles_involved": "muon"}
    with pytest.raises(NonRetryableTransformError):
        await ReferenceDataLookupTransform(_extractor_input(payload), {}, ctx)


async def test_int_particles_involved_raises_nonretryable(ctx):
    payload = {"particles_involved": 5}
    with pytest.raises(NonRetryableTransformError):
        await ReferenceDataLookupTransform(_extractor_input(payload), {}, ctx)


async def test_non_list_initial_state_raises_nonretryable(ctx):
    payload = {
        "particles_involved": ["muon"],
        "initial_state": "not-a-list",
    }
    with pytest.raises(NonRetryableTransformError):
        await ReferenceDataLookupTransform(_extractor_input(payload), {}, ctx)


async def test_non_list_final_state_raises_nonretryable(ctx):
    payload = {
        "particles_involved": ["muon"],
        "final_state": {"particle": "muon"},
    }
    with pytest.raises(NonRetryableTransformError):
        await ReferenceDataLookupTransform(_extractor_input(payload), {}, ctx)


async def test_non_dict_entry_in_state_is_skipped(ctx):
    payload = {
        "particles_involved": ["muon"],
        "initial_state": ["muon", {"particle": "muon", "antiparticle": False, "count": 1}],
    }
    result = await ReferenceDataLookupTransform(_extractor_input(payload), {}, ctx)
    signed = result["signed"]
    assert len(signed) == 1
    assert signed[0]["particle"] == "muon"


async def test_non_string_entry_in_particles_involved_not_counted(ctx):
    payload = {"particles_involved": ["muon", 5, None]}
    result = await ReferenceDataLookupTransform(_extractor_input(payload), {}, ctx)
    assert result["found"] == {"muon": result["found"]["muon"]}
    assert result["unknown"] == []
    assert result["verdict"] == "consistent"
