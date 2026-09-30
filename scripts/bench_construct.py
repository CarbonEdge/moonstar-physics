"""Run one construct config N times, sequentially, and write a bench summary.

Usage:
    MOONSTAR_AUTH_TOKEN=<token> python scripts/bench_construct.py <spec.yaml> --n 5 --tag baseline-v4pro \
        [--max-rounds 5] [--models pipelines/models.derive-flash41.json] [--note "text"]

Output: constructs/_bench/<date>-<tag>/run-<i>.json (raw, untracked), meta.json (untracked),
summary.md (commit this). One live run at a time: the gateway runs ~2 LLM transforms at once, so
concurrent benches queue each other and distort timings. Each raw run is saved as soon as it
finishes, so an interrupted bench keeps its finished runs (rebuild with scripts/bench_report.py).
Cost figures are PROVISIONAL (token x price table) until P6.1.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from bench_report import build_report  # noqa: E402
from moonstar_physics.construct_pipeline import run_construct  # noqa: E402
from moonstar_physics.construct_spec import load_construct_spec  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).parent.parent
_BENCH_DIR = _ROOT / "constructs" / "_bench"
_PIPELINE = _ROOT / "pipelines" / "construct.yaml"
_DEFAULT_MODELS = _ROOT / "pipelines" / "models.json"


def parse_args(argv: list[str]) -> dict | None:
    if len(argv) < 2:
        return None
    opts: dict = {"spec": argv[1], "n": 5, "tag": None, "max_rounds": None, "models": None, "note": None}
    flags = {"--n": ("n", int), "--tag": ("tag", str), "--max-rounds": ("max_rounds", int),
             "--models": ("models", str), "--note": ("note", str)}
    rest = argv[2:]
    while rest:
        if len(rest) < 2 or rest[0] not in flags:
            return None
        key, cast = flags[rest[0]]
        try:
            opts[key] = cast(rest[1])
        except ValueError:
            return None
        rest = rest[2:]
    if not opts["tag"] or opts["n"] < 1:
        return None
    return opts


async def _bench(opts: dict) -> int:
    gateway_url = os.environ.get("MOONSTAR_GATEWAY_URL", "http://localhost:8000")
    token = os.environ.get("MOONSTAR_AUTH_TOKEN")
    if not token:
        print("ERROR: MOONSTAR_AUTH_TOKEN is not set", file=sys.stderr)
        return 1
    spec = load_construct_spec(opts["spec"])
    models_path = Path(opts["models"]) if opts["models"] else _DEFAULT_MODELS
    out_dir = _BENCH_DIR / f"{datetime.date.today().isoformat()}-{opts['tag']}"
    if list(out_dir.glob("run-*.json")):
        print(f"ERROR: {out_dir} already has runs; pick another --tag", file=sys.stderr)
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "tag": opts["tag"], "date": datetime.date.today().isoformat(), "spec": spec.slug,
        "models": models_path.name, "models_content": json.loads(models_path.read_text(encoding="utf-8")),
        "max_rounds": opts["max_rounds"] if opts["max_rounds"] is not None else spec.budget.get("max_rounds"),
        "n_requested": opts["n"], "note": opts["note"],
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    for i in range(1, opts["n"] + 1):
        result = await run_construct(
            opts["spec"], gateway_url, token, _PIPELINE, models_path, max_rounds=opts["max_rounds"]
        )
        (out_dir / f"run-{i}.json").write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"run {i}/{opts['n']}: {result.get('status')} {result.get('verdict')} "
              f"rounds={len(result.get('rounds', []))} elapsed={result.get('elapsed_seconds')}s", flush=True)
    text = build_report(out_dir)
    (out_dir / "summary.md").write_text(text, encoding="utf-8")
    print(text)
    print(f"summary: {out_dir / 'summary.md'}")
    return 0


def main(argv: list[str]) -> int:
    opts = parse_args(argv)
    if opts is None:
        print("usage: bench_construct.py <spec.yaml> --tag TAG [--n N] [--max-rounds R] [--models PATH] [--note TEXT]",
              file=sys.stderr)
        return 2
    return asyncio.run(_bench(opts))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
