"""Check a construct candidate against a ConstructSpec — no LLM, no gateway.

Usage: python scripts/check_construct_candidate.py <spec.yaml> <candidate.json>

Prints "VERDICT: ..." first, then the per-criterion checklist. Exit code 0
iff CONSTRUCTED, 1 otherwise, 2 on usage error.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from moonstar_physics._compat import SessionContext
from moonstar_physics.construct_criteria_transform import ConstructCriteriaTransform
from moonstar_physics.vector_calculus_check_transform import VectorCalculusCheckTransform

_CTX = SessionContext()


async def check_candidate(spec_path: str, candidate: dict) -> dict:
    checks = await VectorCalculusCheckTransform(
        {"Generator_A": {"response": json.dumps(candidate)}},
        {"spec_path": spec_path, "source": "Generator_A"},
        _CTX,
    )
    return await ConstructCriteriaTransform(
        {"checks": checks}, {"spec_path": spec_path, "source": "checks"}, _CTX
    )


def _format(out: dict) -> str:
    lines = [f"VERDICT: {out['verdict']}", ""]
    lines.append(f"{'criterion':<18}{'level':<6}{'status':<11}evidence")
    for row in out["checklist"]:
        ev = row["evidence"] or {}
        detail = ev.get("detail") or ", ".join(
            f"{k}={ev[k]:.3g}" for k in ("max_residual", "value") if isinstance(ev.get(k), float)
        )
        level = "hard" if row["hard"] else "soft"
        lines.append(f"{row['id']:<18}{level:<6}{row['status']:<11}{detail or row['note']}")
    lines.append("")
    lines.append(
        "CONSTRUCTED means: satisfies the stated criteria as checked here "
        "(numeric residuals). Not novelty, not proof."
    )
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: check_construct_candidate.py <spec.yaml> <candidate.json>", file=sys.stderr)
        return 2
    candidate = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
    out = asyncio.run(check_candidate(argv[1], candidate))
    print(_format(out))
    return 0 if out["verdict"] == "CONSTRUCTED" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))