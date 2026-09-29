"""ConstructSpec — the input contract for the construct pipeline.

A spec states a construction task (definitions, hard + soft acceptance
criteria, mechanism hints, free parameters, sampling box). Loading fails
loudly on anything the pipeline could not actually check: a hard
criterion must map to a supported checker, and at least one hard
criterion must be a "gate" (symbolic/numeric identity) so a verdict can
never be vacuous.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

SUPPORTED_CHECKS = frozenset(
    {"divergence_zero", "identity_zero", "numeric_sample", "sandbox_experiment", "manual"}
)
NUMERIC_KINDS = frozenset({"nonnegative", "nonconstant", "axisymmetry_breaking"})
SANDBOX_KINDS = frozenset({"iota_nonzero", "iota_noninteger"})
GATE_CHECKS = frozenset({"divergence_zero", "identity_zero"})
_AXES = ("x", "y", "z")
_ALLOWED_TOP_LEVEL = frozenset(
    {
        "slug", "title", "statement", "unknowns", "criteria", "mechanism_hints",
        "degrees_of_freedom", "sample_box", "budget",
    }
)


class ConstructSpecError(ValueError):
    """Raised when a construct spec is malformed or unverifiable."""


@dataclass(frozen=True)
class Criterion:
    id: str
    check: str
    hard: bool
    expr: str | None = None
    kind: str | None = None
    target: str | None = None
    note: str = ""


@dataclass(frozen=True)
class DegreeOfFreedom:
    name: str
    low: float
    high: float


@dataclass(frozen=True)
class ConstructSpec:
    slug: str
    title: str
    statement: str
    unknowns: tuple[dict[str, Any], ...]
    criteria: tuple[Criterion, ...]
    mechanism_hints: tuple[str, ...]
    degrees_of_freedom: tuple[DegreeOfFreedom, ...]
    sample_box: dict[str, tuple[float, float]]
    budget: dict[str, Any]

    def hard_criteria(self) -> list[Criterion]:
        return [c for c in self.criteria if c.hard]

    def soft_criteria(self) -> list[Criterion]:
        return [c for c in self.criteria if not c.hard]


def _parse_criterion(raw: Any, hard: bool) -> Criterion:
    if not isinstance(raw, dict) or not raw.get("id"):
        raise ConstructSpecError(f"criterion must be a mapping with an id: {raw!r}")
    cid = str(raw["id"])
    check = raw.get("check")
    if check not in SUPPORTED_CHECKS:
        raise ConstructSpecError(f"criterion {cid!r}: unsupported check {check!r}")
    if hard and check == "manual":
        raise ConstructSpecError(
            f"criterion {cid!r}: a hard criterion cannot use check 'manual' (unverifiable)"
        )
    expr = raw.get("expr")
    kind = raw.get("kind")
    target = raw.get("target")
    if check in GATE_CHECKS and not (isinstance(expr, str) and expr.strip()):
        raise ConstructSpecError(f"criterion {cid!r}: check {check!r} requires an expr")
    if check == "numeric_sample":
        if kind not in NUMERIC_KINDS:
            raise ConstructSpecError(f"criterion {cid!r}: unknown numeric_sample kind {kind!r}")
        if not (isinstance(target, str) and target):
            raise ConstructSpecError(f"criterion {cid!r}: numeric_sample requires a target")
    if check == "sandbox_experiment" and kind not in SANDBOX_KINDS:
        raise ConstructSpecError(
            f"criterion {cid!r}: unknown sandbox_experiment kind {kind!r}"
        )
    return Criterion(
        id=cid, check=check, hard=hard, expr=expr, kind=kind, target=target,
        note=str(raw.get("note", "")),
    )


def parse_construct_spec(data: dict[str, Any]) -> ConstructSpec:
    if not isinstance(data, dict):
        raise ConstructSpecError("spec must be a mapping")
    unknown_keys = set(data) - _ALLOWED_TOP_LEVEL
    if unknown_keys:
        raise ConstructSpecError(
            f"unsupported top-level key(s) in v1 spec: {sorted(unknown_keys)} "
            "(external_validator is v2+)"
        )
    for key in ("slug", "title", "statement", "criteria", "sample_box"):
        if key not in data:
            raise ConstructSpecError(f"missing required key {key!r}")

    crit_block = data["criteria"]
    if not isinstance(crit_block, dict):
        raise ConstructSpecError("criteria must be a mapping with 'hard' and optional 'soft'")
    criteria = [_parse_criterion(r, True) for r in crit_block.get("hard") or []]
    criteria += [_parse_criterion(r, False) for r in crit_block.get("soft") or []]

    seen: set[str] = set()
    for c in criteria:
        if c.id in seen:
            raise ConstructSpecError(f"duplicate criterion id {c.id!r}")
        seen.add(c.id)
    if not any(c.hard and c.check in GATE_CHECKS for c in criteria):
        raise ConstructSpecError(
            "spec needs at least one hard gate criterion (divergence_zero or identity_zero)"
        )

    box_raw = data["sample_box"]
    if not isinstance(box_raw, dict) or any(a not in box_raw for a in _AXES):
        raise ConstructSpecError("sample_box must define x, y and z ranges")
    sample_box: dict[str, tuple[float, float]] = {}
    for axis in _AXES:
        lo, hi = box_raw[axis]
        if not lo < hi:
            raise ConstructSpecError(f"sample_box.{axis} range must satisfy low < high")
        sample_box[axis] = (float(lo), float(hi))

    dofs = []
    for raw in data.get("degrees_of_freedom") or []:
        lo, hi = raw["range"]
        if not lo < hi:
            raise ConstructSpecError(f"degree of freedom {raw['name']!r}: range must satisfy low < high")
        dofs.append(DegreeOfFreedom(name=str(raw["name"]), low=float(lo), high=float(hi)))

    return ConstructSpec(
        slug=str(data["slug"]),
        title=str(data["title"]),
        statement=str(data["statement"]),
        unknowns=tuple(dict(u) for u in data.get("unknowns") or []),
        criteria=tuple(criteria),
        mechanism_hints=tuple(str(h) for h in data.get("mechanism_hints") or []),
        degrees_of_freedom=tuple(dofs),
        sample_box=sample_box,
        budget=dict(data.get("budget") or {}),
    )


def load_construct_spec(path: str | Path) -> ConstructSpec:
    text = Path(path).read_text(encoding="utf-8")
    return parse_construct_spec(yaml.safe_load(text))