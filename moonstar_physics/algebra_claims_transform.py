"""AlgebraicClaimsCheckTransform — verifies each of a proof paper's
hand-transcribed algebraic sub-claims (scaling relations, ansatz
substitutions, exponent arithmetic — see proof_hypothesis.yaml's Extractor
schema) via sympy, then aggregates the per-claim verdicts into one verdict
for the whole hypothesis.

Reuses IdentityCheckTransform's own Extractor-shaped input contract rather
than reimplementing its sympy-checking logic: each {lhs, rhs, variables}
claim is wrapped as a synthetic single-claim Extractor response and passed
through the existing, already-tested function. One sympy-checking
implementation, never two.
"""
from __future__ import annotations

import json
from typing import Any

from ._compat import SessionContext
from ._parsing import parse_extractor_output
from .maths.identity_transform import IdentityCheckTransform


def _not_applicable(detail: str) -> dict[str, Any]:
    return {
        "checked_claims": [],
        "verdict": "not_applicable",
        "detail": detail,
        "_model": "none",
        "_provider": "none",
        "_input_tokens": 0,
        "_output_tokens": 0,
    }


async def AlgebraicClaimsCheckTransform(
    input: dict[str, Any], config: dict[str, Any], ctx: SessionContext
) -> dict[str, Any]:
    parsed = parse_extractor_output(input)
    claims = parsed.get("algebraic_claims")

    if not claims:
        return _not_applicable("no algebraic_claims provided")
    if not isinstance(claims, list):
        return _not_applicable(f"'algebraic_claims' must be a list, got {type(claims).__name__}")

    checked: list[dict[str, Any]] = []
    for claim in claims:
        if not isinstance(claim, dict):
            checked.append(
                {
                    "description": "<malformed claim entry>",
                    "verdict": "not_applicable",
                    "detail": "claim entry is not an object",
                }
            )
            continue

        description = claim.get("description") or "<no description>"
        synthetic_input = {
            "Extractor": {
                "response": json.dumps(
                    {
                        "claim_type": "identity",
                        "identity_claim": {
                            "lhs": claim.get("lhs"),
                            "rhs": claim.get("rhs"),
                            "variables": claim.get("variables") or [],
                        },
                    }
                )
            }
        }
        result = await IdentityCheckTransform(synthetic_input, {}, ctx)
        checked.append(
            {
                "description": description,
                **{k: v for k, v in result.items() if not k.startswith("_")},
            }
        )

    verdicts = [c["verdict"] for c in checked]
    if "violated" in verdicts:
        verdict = "violated"
    elif "consistent" in verdicts:
        verdict = "consistent"
    else:
        verdict = "not_applicable"

    return {
        "checked_claims": checked,
        "verdict": verdict,
        "_model": "none",
        "_provider": "none",
        "_input_tokens": 0,
        "_output_tokens": 0,
    }
