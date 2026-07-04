"""ReferenceDataLookupTransform — look up known particle properties from the bundled dataset."""
from __future__ import annotations

from typing import Any

import sympy
from moonstar_core import SessionContext
from moonstar_core.exceptions import NonRetryableTransformError

from ._parsing import parse_extractor_output
from ._particle_data import load_particle_data


def _signed_entry(entry: Any, data: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    name = entry.get("particle")
    if name not in data:
        return None
    p = data[name]
    antiparticle = bool(entry.get("antiparticle", False))
    sign = -1 if antiparticle else 1
    return {
        "particle": name,
        "antiparticle": antiparticle,
        "effective_charge": str(sign * sympy.Rational(p["charge"])),
        "effective_electron_number": sign * p["electron_number"],
        "effective_muon_number": sign * p["muon_number"],
        "effective_tau_number": sign * p["tau_number"],
    }


async def ReferenceDataLookupTransform(
    input: dict[str, Any], config: dict[str, Any], ctx: SessionContext
) -> dict[str, Any]:
    parsed = parse_extractor_output(input)
    names = parsed.get("particles_involved") or []
    if not isinstance(names, list):
        raise NonRetryableTransformError(
            f"'particles_involved' must be a list, got {type(names).__name__}"
        )
    data = load_particle_data()

    found: dict[str, Any] = {}
    unknown: list[str] = []
    for name in names:
        if not isinstance(name, str):
            continue
        if name in data:
            found[name] = data[name]
        else:
            unknown.append(name)

    initial_state = parsed.get("initial_state") or []
    final_state = parsed.get("final_state") or []
    if not isinstance(initial_state, list):
        raise NonRetryableTransformError(
            f"'initial_state' must be a list, got {type(initial_state).__name__}"
        )
    if not isinstance(final_state, list):
        raise NonRetryableTransformError(
            f"'final_state' must be a list, got {type(final_state).__name__}"
        )

    signed: list[dict[str, Any]] = []
    for entry in initial_state + final_state:
        s = _signed_entry(entry, data)
        if s is not None:
            signed.append(s)

    if not names:
        verdict = "not_applicable"
    elif not found:
        verdict = "unknown_particle"
    else:
        verdict = "consistent"

    return {
        "found": found,
        "unknown": unknown,
        "signed": signed,
        "verdict": verdict,
        "_model": "none",
        "_provider": "none",
        "_input_tokens": 0,
        "_output_tokens": 0,
    }
