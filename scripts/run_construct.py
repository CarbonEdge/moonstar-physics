"""Run one round of the construct pipeline against a ConstructSpec.

Usage:
    MOONSTAR_AUTH_TOKEN=<token> python scripts/run_construct.py constructs/analytic-3d-mhd-equilibrium.yaml

Env vars:
    MOONSTAR_GATEWAY_URL   default http://localhost:8000
    MOONSTAR_AUTH_TOKEN    required — `bash scripts/harness.sh token` in moonstar-rs

Real LLM spend happens here (Planner + 2 Generators + up to 3 review steps).
Every run is saved to constructs/<slug>/runs/<session_id>.json with all
artifacts (candidates, filled iota scripts, sandbox stdout, checklists).
Exit code 0 iff the run completed with verdict CONSTRUCTED.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))
from check_construct_candidate import _format  # noqa: E402
from moonstar_physics.construct_pipeline import run_construct  # noqa: E402
from moonstar_physics.construct_spec import load_construct_spec  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

_ROOT_DIR = Path(__file__).parent.parent
_CONSTRUCTS_DIR = _ROOT_DIR / "constructs"
_PIPELINE_PATH = _ROOT_DIR / "pipelines" / "construct.yaml"
_MODELS_PATH = _ROOT_DIR / "pipelines" / "models.json"


def _save_run(slug: str, session_id: str, result: dict[str, Any]) -> Path:
    out_dir = _CONSTRUCTS_DIR / slug / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{session_id}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def _usage_totals(result: dict[str, Any]) -> dict[str, dict[str, int]]:
    totals: dict[str, dict[str, int]] = {}
    for art in result.get("artifacts", []):
        data = art.get("data") or {}
        if not ("_input_tokens" in data or "_output_tokens" in data):
            continue
        model = data.get("_model", "unknown")
        if model == "none":
            continue
        row = totals.setdefault(model, {"input_tokens": 0, "output_tokens": 0})
        row["input_tokens"] += int(data.get("_input_tokens") or 0)
        row["output_tokens"] += int(data.get("_output_tokens") or 0)
    return totals


def _format_summary(result: dict[str, Any]) -> str:
    if result.get("status") != "completed":
        return f"RUN FAILED: {result.get('error', 'unknown error')}"
    by_name = {a["transform_name"]: a["data"] for a in result["artifacts"]}
    best = result.get("best_candidate", "A").lower()
    parts = [_format(by_name[f"criteria_{best}"])]
    if "synthesizer" in by_name:
        parts += ["", "--- synthesizer ---", by_name["synthesizer"].get("response", "")]
    parts += ["", f"elapsed: {result.get('elapsed_seconds')}s", "token usage (measure cost/round from this):"]
    usage = _usage_totals(result)
    parts += [f"  {m}: in={u['input_tokens']} out={u['output_tokens']}" for m, u in usage.items()] or ["  (none reported)"]
    return "\n".join(parts)


async def _run(spec_path: str) -> int:
    gateway_url = os.environ.get("MOONSTAR_GATEWAY_URL", "http://localhost:8000")
    token = os.environ.get("MOONSTAR_AUTH_TOKEN")
    if not token:
        print("ERROR: MOONSTAR_AUTH_TOKEN is not set", file=sys.stderr)
        return 1
    spec = load_construct_spec(spec_path)
    result = await run_construct(spec_path, gateway_url, token, _PIPELINE_PATH, _MODELS_PATH)
    saved = _save_run(spec.slug, result["session_id"], result)
    print(_format_summary(result))
    print(f"\nsaved: {saved}")
    return 0 if result.get("verdict") == "CONSTRUCTED" else 1


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: run_construct.py <spec.yaml>", file=sys.stderr)
        return 2
    if not os.environ.get("MOONSTAR_AUTH_TOKEN"):
        print("ERROR: MOONSTAR_AUTH_TOKEN is not set", file=sys.stderr)
        return 1
    return asyncio.run(_run(argv[1]))


if __name__ == "__main__":
    sys.exit(main(sys.argv))