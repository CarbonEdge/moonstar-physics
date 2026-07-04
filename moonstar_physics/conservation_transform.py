"""ConservationLawCheckTransform — checks charge, baryon number, per-flavor
lepton number, and a rest-mass-energy threshold across initial vs final state.

Rest-mass-energy is deliberately NOT an equality check: decays and reactions
routinely convert rest mass into kinetic energy (e.g. muon -> electron +
neutrinos is a completely normal decay even though final rest mass is far
below initial rest mass). The only hard constraint derivable from rest
masses alone is a threshold: final rest mass can't exceed initial rest mass,
since kinetic energy can't be negative.
"""
from __future__ import annotations

from typing import Any

import sympy
from moonstar_core import SessionContext
from moonstar_core.exceptions import NonRetryableTransformError

from ._parsing import parse_extractor_output
from ._particle_data import ParticleNotFound, load_particle_data

_LEPTON_FLAVORS = ("electron_number", "muon_number", "tau_number")


class _MalformedStateEntry(Exception):
    """Raised internally when a state list entry isn't a well-formed dict
    (not a dict at all, or has a non-numeric 'count'). Caught alongside
    ParticleNotFound to fall through to the not_applicable verdict."""


def _state_totals(state: list[Any], data: dict[str, Any]) -> dict[str, Any]:
    charge_total = sympy.Integer(0)
    baryon_total = sympy.Integer(0)
    lepton_totals = {flavor: 0 for flavor in _LEPTON_FLAVORS}
    mass_total = 0.0

    for entry in state:
        if not isinstance(entry, dict):
            raise _MalformedStateEntry(f"state entry is not an object: {entry!r}")

        name = entry.get("particle")
        antiparticle = bool(entry.get("antiparticle", False))
        try:
            count = int(entry.get("count", 1))
        except (TypeError, ValueError):
            raise _MalformedStateEntry(
                f"non-numeric count: {entry.get('count')!r}"
            ) from None

        if name not in data:
            raise ParticleNotFound(name)

        p = data[name]
        sign = -1 if antiparticle else 1

        charge_total += sign * sympy.Rational(p["charge"]) * count
        baryon_total += sign * sympy.Rational(p["baryon_number"]) * count
        for flavor in _LEPTON_FLAVORS:
            lepton_totals[flavor] += sign * p[flavor] * count
        mass_total += p["mass_mev"] * count  # rest mass is never negative

    return {
        "charge": charge_total,
        "baryon_number": baryon_total,
        **lepton_totals,
        "mass_mev": mass_total,
    }


async def ConservationLawCheckTransform(
    input: dict[str, Any], config: dict[str, Any], ctx: SessionContext
) -> dict[str, Any]:
    parsed = parse_extractor_output(input)

    initial_state = parsed.get("initial_state")
    final_state = parsed.get("final_state")

    def _not_applicable(detail: str) -> dict[str, Any]:
        return {
            "checked": [],
            "violations": [],
            "verdict": "not_applicable",
            "detail": detail,
            "_model": "none",
            "_provider": "none",
            "_input_tokens": 0,
            "_output_tokens": 0,
        }

    if not initial_state or not final_state:
        return _not_applicable(
            "initial_state and final_state are both required for a conservation check"
        )

    if not isinstance(initial_state, list):
        raise NonRetryableTransformError(
            f"'initial_state' must be a list, got {type(initial_state).__name__}"
        )
    if not isinstance(final_state, list):
        raise NonRetryableTransformError(
            f"'final_state' must be a list, got {type(final_state).__name__}"
        )

    data = load_particle_data()

    try:
        initial = _state_totals(initial_state, data)
        final = _state_totals(final_state, data)
    except ParticleNotFound as e:
        return _not_applicable(f"unknown particle: {e.args[0]}")
    except _MalformedStateEntry as e:
        return _not_applicable(f"malformed state entry: {e}")

    checked = ["charge", "baryon_number", *_LEPTON_FLAVORS, "mass_energy_threshold"]
    violations = [
        law
        for law in ("charge", "baryon_number", *_LEPTON_FLAVORS)
        if initial[law] != final[law]
    ]

    energetically_forbidden = final["mass_mev"] > initial["mass_mev"]

    # Fundamental conservation laws (charge, baryon number) take precedence
    fundamental_violations = [v for v in violations if v in ("charge", "baryon_number")]

    if fundamental_violations:
        verdict = "violated"
    elif energetically_forbidden:
        verdict = "energetically_forbidden"
    elif violations:
        verdict = "violated"
    else:
        verdict = "consistent"

    return {
        "checked": checked,
        "violations": violations,
        "verdict": verdict,
        "initial_totals": {k: str(v) for k, v in initial.items()},
        "final_totals": {k: str(v) for k, v in final.items()},
        "_model": "none",
        "_provider": "none",
        "_input_tokens": 0,
        "_output_tokens": 0,
    }
