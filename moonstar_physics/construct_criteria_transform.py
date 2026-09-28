"""ConstructCriteriaTransform — pure-code merge of checker results into a
per-criterion checklist and a verdict. No LLM: the verdict must come from
deterministic checks only.

Verdict:
  NOT_FOUND    a hard *gate* criterion (divergence_zero / identity_zero) is
               not met — nothing passed the symbolic gate
  CONSTRUCTED  every hard criterion is met
  PARTIAL      gates met, but >=1 hard criterion unmet or unverified

CONSTRUCTED means "satisfies the stated criteria as checked here" — never
"novel", never "proven".
"""
from __future__ import annotations

from typing import Any

from ._compat import NonRetryableTransformError, SessionContext
from .construct_spec import GATE_CHECKS, load_construct_spec

_STATUS_MAP = {"pass": "met", "fail": "unmet", "error": "unverified"}


async def ConstructCriteriaTransform(
    input: dict[str, Any], config: dict[str, Any], ctx: SessionContext
) -> dict[str, Any]:
    spec = load_construct_spec(config["spec_path"])
    source = config.get("source", "checks")
    block = input.get(source)
    if not isinstance(block, dict) or not isinstance(block.get("results"), list):
        raise NonRetryableTransformError(
            f"Expected {source!r} dependency with a 'results' list — is this "
            "transform's `input:` wired to the checker step?"
        )
    by_id = {r["id"]: r for r in block["results"] if isinstance(r, dict) and "id" in r}

    checklist = []
    for c in spec.criteria:
        result = by_id.get(c.id)
        status = "unverified" if result is None else _STATUS_MAP.get(result.get("status"), "unverified")
        checklist.append({
            "id": c.id, "hard": c.hard, "check": c.check,
            "status": status, "note": c.note, "evidence": result,
        })

    hard = [(c, row) for c, row in zip(spec.criteria, checklist) if c.hard]
    unmet = [c.id for c, row in hard if row["status"] == "unmet"]
    unverified = [c.id for c, row in hard if row["status"] == "unverified"]
    gate_ok = all(row["status"] == "met" for c, row in hard if c.check in GATE_CHECKS)

    if not gate_ok:
        verdict = "NOT_FOUND"
    elif not unmet and not unverified:
        verdict = "CONSTRUCTED"
    else:
        verdict = "PARTIAL"

    return {
        "verdict": verdict,
        "checklist": checklist,
        "unmet_hard": unmet,
        "unverified_hard": unverified,
        "_model": "none", "_provider": "none", "_input_tokens": 0, "_output_tokens": 0,
    }