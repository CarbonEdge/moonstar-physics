"""Tests for ConservationLawCheckTransform."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from moonstar_core import SessionContext
from moonstar_core.exceptions import NonRetryableTransformError

from moonstar_physics.conservation_transform import ConservationLawCheckTransform


@pytest.fixture
def ctx() -> AsyncMock:
    return AsyncMock(spec=SessionContext)


def _extractor_input(payload: dict) -> dict:
    return {"Extractor": {"response": json.dumps(payload)}}


async def test_muon_decay_is_consistent(ctx):
    """mu- -> e- + anti-nu_e + nu_mu: the real, allowed muon decay."""
    payload = {
        "initial_state": [{"particle": "muon", "antiparticle": False, "count": 1}],
        "final_state": [
            {"particle": "electron", "antiparticle": False, "count": 1},
            {"particle": "electron_neutrino", "antiparticle": True, "count": 1},
            {"particle": "muon_neutrino", "antiparticle": False, "count": 1},
        ],
    }
    result = await ConservationLawCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "consistent"
    assert result["violations"] == []


async def test_muon_to_electron_photon_violates_lepton_flavor(ctx):
    """mu- -> e- + gamma: conserves charge and total lepton number, but not
    muon-number or electron-number individually. A real forbidden decay
    (lepton flavor violation) that a single pooled lepton-number check would miss."""
    payload = {
        "initial_state": [{"particle": "muon", "antiparticle": False, "count": 1}],
        "final_state": [
            {"particle": "electron", "antiparticle": False, "count": 1},
            {"particle": "photon", "antiparticle": False, "count": 1},
        ],
    }
    result = await ConservationLawCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "violated"
    assert "muon_number" in result["violations"]
    assert "electron_number" in result["violations"]
    assert "charge" not in result["violations"]


async def test_charge_violation_detected(ctx):
    """proton -> neutron (charge +1 -> 0): not a real process, charge imbalance."""
    payload = {
        "initial_state": [{"particle": "proton", "antiparticle": False, "count": 1}],
        "final_state": [{"particle": "neutron", "antiparticle": False, "count": 1}],
    }
    result = await ConservationLawCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "violated"
    assert "charge" in result["violations"]


async def test_energetically_forbidden_when_final_mass_exceeds_initial(ctx):
    """electron -> muon + photon: final rest mass (105.66 + 0 MeV) exceeds
    initial rest mass (0.51 MeV) — impossible regardless of any other law."""
    payload = {
        "initial_state": [{"particle": "electron", "antiparticle": False, "count": 1}],
        "final_state": [
            {"particle": "muon", "antiparticle": False, "count": 1},
            {"particle": "photon", "antiparticle": False, "count": 1},
        ],
    }
    result = await ConservationLawCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "energetically_forbidden"


async def test_missing_state_data_is_not_applicable(ctx):
    payload = {"hypothesis_type": "property_claim"}
    result = await ConservationLawCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_unknown_particle_is_not_applicable(ctx):
    payload = {
        "initial_state": [{"particle": "gravitino", "antiparticle": False, "count": 1}],
        "final_state": [{"particle": "electron", "antiparticle": False, "count": 1}],
    }
    result = await ConservationLawCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_non_list_initial_state_raises_nonretryable(ctx):
    payload = {
        "initial_state": "muon",
        "final_state": [{"particle": "electron", "antiparticle": False, "count": 1}],
    }
    with pytest.raises(NonRetryableTransformError):
        await ConservationLawCheckTransform(_extractor_input(payload), {}, ctx)


async def test_non_list_final_state_raises_nonretryable(ctx):
    payload = {
        "initial_state": [{"particle": "muon", "antiparticle": False, "count": 1}],
        "final_state": 42,
    }
    with pytest.raises(NonRetryableTransformError):
        await ConservationLawCheckTransform(_extractor_input(payload), {}, ctx)


async def test_non_dict_entry_in_state_list_is_not_applicable(ctx):
    payload = {
        "initial_state": ["muon"],
        "final_state": [{"particle": "electron", "antiparticle": False, "count": 1}],
    }
    result = await ConservationLawCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"


async def test_non_numeric_count_is_not_applicable(ctx):
    payload = {
        "initial_state": [{"particle": "muon", "antiparticle": False, "count": "two"}],
        "final_state": [{"particle": "electron", "antiparticle": False, "count": 1}],
    }
    result = await ConservationLawCheckTransform(_extractor_input(payload), {}, ctx)
    assert result["verdict"] == "not_applicable"
