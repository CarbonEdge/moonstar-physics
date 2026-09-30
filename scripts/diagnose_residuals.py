"""Classify every candidate in saved run JSONs (no LLM, no gateway).

Usage: python scripts/diagnose_residuals.py [run.json ...]   (default: constructs/*/runs/*.json)

For each distinct candidate prints the checker verdict's unmet hard criteria and the
construct_diagnose classification (ok / scale / localised / wrong / undefined), then a summary.
Spec is taken from the run's path: constructs/<slug>/runs/<id>.json -> constructs/<slug>.yaml.
"""
from __future__ import annotations

import glob
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from moonstar_physics.construct_diagnose import candidate_health  # noqa: E402

_ROOT = Path(__file__).parent.parent


def iter_candidates(run: dict):
    """Yield (round, label, candidate dict, unmet_hard) for both run formats."""
    blocks = []
    if "rounds" in run:
        blocks = [(r["round"], {a["transform_name"]: a["data"] for a in r["artifacts"]}) for r in run["rounds"]]
    else:
        blocks = [(1, {a["transform_name"]: a["data"] for a in run.get("artifacts", [])})]
    for rnd, by in blocks:
        for label in ("A", "B"):
            gen = by.get(f"Generator_{label}")
            if not gen:
                continue
            try:
                cand = json.loads(gen["response"])
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(cand, dict):
                continue
            crit = by.get(f"criteria_{label.lower()}") or {}
            yield rnd, label, cand, crit.get("unmet_hard")


def main(argv: list[str]) -> int:
    paths = argv[1:] or sorted(glob.glob(str(_ROOT / "constructs" / "*" / "runs" / "*.json")))
    seen: set[str] = set()
    counts: Counter = Counter()
    for path in paths:
        p = Path(path)
        spec = _ROOT / "constructs" / f"{p.parent.parent.name}.yaml"
        run = json.loads(p.read_text(encoding="utf-8"))
        for rnd, label, cand, unmet in iter_candidates(run):
            key = spec.name + json.dumps(cand, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            h = candidate_health(spec, cand)
            counts[h["classification"]] += 1
            gates = h.get("gates", {})
            worst = h.get("worst_gate")
            w = gates.get(worst, {}) if worst else {}
            print(f"{p.name[:18]:<18} r{rnd}{label} {spec.stem[:10]:<10} {h['classification']:<10} "
                  f"worst={worst or '-':<13} abs={w.get('abs', float('nan')):.2e} rel={w.get('rel', float('nan')):.2e} "
                  f"bad={w.get('frac_bad', float('nan')):.2f} range={h.get('b_dynamic_range', float('nan')):.1e} "
                  f"unmet={unmet}")
    print("\nsummary:", dict(counts), "distinct candidates:", sum(counts.values()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
