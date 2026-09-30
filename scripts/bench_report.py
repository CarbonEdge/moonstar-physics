"""Rebuild a bench summary from saved raw runs (no LLM, no gateway).

Usage: python scripts/bench_report.py constructs/_bench/<date>-<tag>

Reads <dir>/meta.json (optional) and <dir>/run-<i>.json, writes <dir>/summary.md and prints it.
Raw run JSON stays untracked (.gitignore); summary.md is what gets committed.
Every cost in the report is labelled provisional until P6.1 (real cost reporting) lands.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))
from moonstar_physics.construct_bench import aggregate, render_report, summarise_run  # noqa: E402


def _run_index(p: Path) -> int:
    m = re.search(r"run-(\d+)", p.name)
    return int(m.group(1)) if m else 0


def load_runs(out_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    meta_path = out_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {"tag": out_dir.name}
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(out_dir.glob("run-*.json"), key=_run_index)]
    return meta, runs


def build_report(out_dir: Path) -> str:
    meta, runs = load_runs(Path(out_dir))
    summaries = [summarise_run(r) for r in runs]
    return render_report(meta, aggregate(summaries), summaries)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: bench_report.py <bench-dir>", file=sys.stderr)
        return 2
    out_dir = Path(argv[1])
    if not list(out_dir.glob("run-*.json")):
        print(f"no run-*.json in {out_dir}", file=sys.stderr)
        return 1
    text = build_report(out_dir)
    (out_dir / "summary.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
