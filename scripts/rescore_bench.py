"""Re-score every saved candidate of a bench campaign with the CURRENT deterministic checker.

No LLM, no gateway. Why: a checker fix (e.g. the translation-invariant axisymmetry test) changes
which candidates deserve CONSTRUCTED; campaigns run on older code must be re-scored before they
are compared. For each run it replays every candidate of every round (seed = round, same as the
live run) and reports the best verdict, so the number is directly comparable between campaigns.

Usage: python scripts/rescore_bench.py <bench-dir> [--spec constructs/x.yaml] [--out rescored.json]
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from moonstar_physics import iota_trace_transform  # noqa: E402
from moonstar_physics.construct_replay import replay_candidate  # noqa: E402

_RANK = {"NOT_FOUND": 0, "PARTIAL": 1, "CONSTRUCTED": 2}
_ROOT = Path(__file__).parent.parent
_DEFAULT_SPEC = _ROOT / "constructs" / "analytic-3d-mhd-equilibrium.yaml"


async def _host_sandbox(script: str, timeout_seconds: int):
    """Runs the (fixed, sympy-printed) trace script with the host interpreter instead of Docker."""
    import subprocess
    proc = await asyncio.to_thread(
        subprocess.run, [sys.executable, "-c", script], capture_output=True, text=True, timeout=timeout_seconds
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT: ")]
    if not lines:
        return {"ran": False, "detail": proc.stderr[-300:], "stdout": proc.stdout}
    return {"ran": True, "result": json.loads(lines[-1][len("RESULT: "):]), "detail": None,
            "stdout": lines[-1], "exit_code": proc.returncode}


async def rescore_run(spec: Path, run: dict) -> dict:
    best = None
    rounds_out = []
    for r in run.get("rounds", []):
        arts = {a["transform_name"]: a["data"] for a in r.get("artifacts", [])}
        for name, data in arts.items():
            if not name.startswith("Generator_"):
                continue
            try:
                cand = json.loads(data["response"])
                out = await replay_candidate(spec, cand, seed=r["round"])
            except Exception as e:  # noqa: BLE001 - an unreadable candidate is NOT_FOUND
                out = {"verdict": "NOT_FOUND", "unmet_hard": [], "unverified_hard": [str(e)[:60]]}
            row = {"round": r["round"], "label": name[-1], "verdict": out["verdict"],
                   "unmet": out.get("unmet_hard", []), "unverified": out.get("unverified_hard", [])}
            rounds_out.append(row)
            key = (_RANK[row["verdict"]], -len(row["unmet"]) - len(row["unverified"]))
            if best is None or key > best[0]:
                best = (key, row)
    return {"best": best[1] if best else None, "candidates": rounds_out}


async def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    bench = Path(argv[1])
    spec = Path(argv[argv.index("--spec") + 1]) if "--spec" in argv else _DEFAULT_SPEC
    out_path = Path(argv[argv.index("--out") + 1]) if "--out" in argv else bench / "rescored.json"
    iota_trace_transform._run_sandbox = _host_sandbox
    results = {}
    for f in sorted(bench.glob("run-*.json"), key=lambda p: int(p.stem.split("-")[1])):
        run = json.loads(f.read_text(encoding="utf-8"))
        results[f.stem] = {"original": run.get("verdict"), **await rescore_run(spec, run)}
        b = results[f.stem]["best"]
        print(f"{f.stem}: original={run.get('verdict')} rescored={b['verdict'] if b else None} "
              f"(round {b['round'] if b else '-'} cand {b['label'] if b else '-'}, unmet={b['unmet'] if b else ''})", flush=True)
    counts = {v: sum(1 for r in results.values() if r["best"] and r["best"]["verdict"] == v) for v in _RANK}
    print("rescored best-verdict counts:", counts)
    out_path.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print("saved:", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv)))
