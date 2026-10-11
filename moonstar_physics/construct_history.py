"""History, scoring and repair feedback for the construct pipeline's multi-round loop.

Pure functions over the per-round summaries: the deterministic evidence of each candidate,
the score that picks the repair anchor (verdict rank, hard criteria met, fewest unmet, latest
round), the regression guard (criteria the anchor met that a later candidate lost), and the
size-capped feedback / planner views. No I/O; construct_pipeline.py owns the orchestration.
"""
from __future__ import annotations

import json
from typing import Any

_RANK = {"NOT_FOUND": 0, "PARTIAL": 1, "CONSTRUCTED": 2}
_HISTORY_ROUNDS = 2
_DIAG_MAX_CHARS = 6000  # cap on the residual diagnostics fed back to Derive (token cost)


def _loads_lenient(raw: Any) -> Any:
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


def _cap_diagnostics(diag: dict[str, Any] | None) -> dict[str, Any] | None:
    """Keep the feedback prompt bounded: drop the bulkiest parts until it fits."""
    if not diag:
        return None
    for drop in ((), ("components",), ("components", "lorentz_vs_grad_p")):
        trimmed = {cid: {k: v for k, v in e.items() if k not in drop} for cid, e in diag.items()}
        if len(json.dumps(trimmed, default=str)) <= _DIAG_MAX_CHARS:
            return trimmed
    return {cid: {"residual_at_points": e.get("residual_at_points")} for cid, e in diag.items()}


def _evidence(criteria: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in criteria.get("checklist", []):
        ev = row.get("evidence") or {}
        entry: dict[str, Any] = {"status": row.get("status"), "hard": row.get("hard")}
        for key in ("max_residual", "value", "iota", "detail"):
            if ev.get(key) is not None:
                entry[key] = ev[key]
        out[row["id"]] = entry
    return out


def _hard_met(evidence: dict[str, dict[str, Any]]) -> list[str]:
    """Hard criteria a candidate's evidence shows as passing, in a stable order."""
    return sorted(cid for cid, e in evidence.items() if e.get("hard") and e.get("status") == "met")


def _candidate_summary(
    label: str, artifacts: dict[str, dict[str, Any]], anchor_met: list[str] | None = None
) -> dict[str, Any]:
    crit = artifacts.get(f"criteria_{label.lower()}", {})
    parsed = _loads_lenient(artifacts.get(f"Generator_{label}", {}).get("response"))
    parsed = parsed if isinstance(parsed, dict) else {}
    evidence = _evidence(crit)
    met = _hard_met(evidence)
    return {
        "verdict": crit.get("verdict", "NOT_FOUND"),
        "unmet_hard": list(crit.get("unmet_hard", [])),
        "unverified_hard": list(crit.get("unverified_hard", [])),
        "evidence": evidence,
        "hard_met": met,
        # Deterministic regression guard: criteria the repair anchor met that this candidate lost.
        "regressed_from": sorted(set(anchor_met or []) - set(met)),
        "diagnostics": artifacts.get(f"diag_{label.lower()}", {}).get("diagnostics"),
        "candidate": {k: parsed[k] for k in ("defs", "objects", "params") if k in parsed},
        "derivation_notes": parsed.get("derivation_notes", ""),
        "error": crit.get("error"),
    }


def _round_summary(
    round_no: int, verdict: str, best: str, artifacts: dict[str, dict[str, Any]],
    anchor_met: list[str] | None = None, labels: tuple[str, ...] = ("A", "B"),
) -> dict[str, Any]:
    return {
        "round": round_no, "verdict": verdict, "best_candidate": best,
        "candidates": {l: _candidate_summary(l, artifacts, anchor_met) for l in labels},
    }


def _cand_score(verdict: str, c: dict[str, Any], round_no: int) -> tuple[int, int, int, int]:
    """Verdict rank, then most hard criteria met, then fewest unmet, then latest round."""
    return (_RANK[verdict], len(c.get("hard_met", [])), -len(c["unmet_hard"]), round_no)


def _round_score(h: dict[str, Any]) -> tuple[int, int, int, int]:
    return _cand_score(h["verdict"], h["candidates"][h["best_candidate"]], h["round"])


def _feedback(history: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The best candidate seen across ALL rounds (see _cand_score) with its
    evidence, as the repair anchor. `must_still_pass` / `must_fix` make the
    carry-over explicit; `regressions` names what last round's candidates broke."""
    best: tuple[tuple[int, int, int, int], int, str, dict[str, Any]] | None = None
    for h in history:
        for label, c in h["candidates"].items():
            if not c["candidate"]:
                continue
            score = _cand_score(c["verdict"], c, h["round"])
            if best is None or score > best[0]:
                best = (score, h["round"], label, c)
    if best is None:
        return None
    _, rnd, label, c = best
    last = history[-1]["candidates"]
    return {
        "from_round": rnd, "from_candidate": label, "previous_best": c["candidate"],
        "evidence": c["evidence"], "unmet_hard": c["unmet_hard"],
        "unverified_hard": c["unverified_hard"], "derivation_notes": c["derivation_notes"],
        "residual_diagnostics": _cap_diagnostics(c.get("diagnostics")),
        "must_still_pass": list(c.get("hard_met", [])),
        "must_fix": [*c["unmet_hard"], *c["unverified_hard"]],
        "regressions": {l: v["regressed_from"] for l, v in last.items() if v.get("regressed_from")},
    }


def _planner_view(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "round": h["round"], "verdict": h["verdict"], "best_candidate": h["best_candidate"],
            "candidates": {
                l: {k: v for k, v in c.items() if k not in ("candidate", "diagnostics")}
                for l, c in h["candidates"].items()
            },
        }
        for h in history[-_HISTORY_ROUNDS:]
    ]
