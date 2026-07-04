"""Tests for the bundled particle reference dataset loader."""
from __future__ import annotations

import pytest
import sympy

from moonstar_physics._particle_data import load_particle_data


def test_electron_properties():
    data = load_particle_data()
    electron = data["electron"]
    assert electron["mass_mev"] == pytest.approx(0.511, rel=1e-2)
    assert sympy.Rational(electron["charge"]) == -1
    assert electron["electron_number"] == 1
    assert electron["muon_number"] == 0
    assert electron["tau_number"] == 0


def test_muon_properties():
    data = load_particle_data()
    muon = data["muon"]
    assert sympy.Rational(muon["charge"]) == -1
    assert muon["muon_number"] == 1
    assert muon["electron_number"] == 0
    assert muon["mean_lifetime_s"] == pytest.approx(2.197e-6, rel=1e-2)


def test_photon_is_neutral_and_stable():
    data = load_particle_data()
    photon = data["photon"]
    assert sympy.Rational(photon["charge"]) == 0
    assert photon["mean_lifetime_s"] == "stable"


def test_quark_charges_are_fractional():
    data = load_particle_data()
    up = data["up_quark"]
    down = data["down_quark"]
    assert sympy.Rational(up["charge"]) == sympy.Rational(2, 3)
    assert sympy.Rational(down["charge"]) == sympy.Rational(-1, 3)
    assert sympy.Rational(up["baryon_number"]) == sympy.Rational(1, 3)


def test_load_is_cached_same_object():
    a = load_particle_data()
    b = load_particle_data()
    assert a is b
