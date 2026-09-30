"""Run one round of the construct pipeline against a ConstructSpec.

Usage:
    MOONSTAR_AUTH_TOKEN=<token> python scripts/run_construct.py constructs/analytic-3d-mhd-equilibrium.yaml [--max-rounds N]

Env vars:
    MOONSTAR_GATEWAY_URL   default http://localhost:8000
    MOONSTAR_AUTH_TOKEN    required — `bash scripts/harness.sh token` in moonstar-rs

Runs up to spec.budget.max_rounds repair rounds (override with --max-rounds);
stops early on CONSTRUCTED.

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


def _format_summary(result: dict[str, Any]) -> str:
    if result.get("status") != "completed":
        return f"RUN FAILED: {result.get('error', 'unknown error')}"
    by_name = {a["transform_name"]: a["data"] for a in result["artifacts"]}
    best = result.get("best_candidate", "A").lower()
    parts = [_format(by_name[f"criteria_{best}"])]
    if "synthesizer" in by_name:
        parts += ["", "--- synthesizer ---", by_name["synthesizer"].get("response", "")]
    rounds = result.get("rounds") or []
    if rounds:
        parts += ["", f"rounds: {len(rounds)} (stop: {result.get('stop_reason')}, "
                      f"best: round {result.get('best_round')})"]
        parts += [
            f"  round {r['round']}: {r['verdict']} (best candidate {r['best_candidate']}, "
            f"${r['cost_usd']:.4f})"
            for r in rounds
        ]
    parts += [
        "", f"elapsed: {result.get('elapsed_seconds')}s",
        (f"cost: ${result.get('cost_usd', 0.0):.4f} reported by OpenRouter per call "
         f"(incl. ${result.get('cost_truncated_usd', 0.0):.4f} wasted on truncated retries; "
         "calls that failed or timed out entirely are not counted)")
        if result.get("cost_is_exact") else
        f"cost: ${result.get('cost_usd', 0.0):.4f} ESTIMATED (token x price table"
        + (f"; ${result.get('cost_reported_usd', 0.0):.4f} of it reported" if result.get("cost_reported_usd") else "")
        + "; failed/retried calls are not counted)",
    ]
    if result.get("unpriced_models"):
        parts.append(f"UNPRICED models (cost undercounted): {', '.join(result['unpriced_models'])}")
    parts.append("token usage:")
    usage = result.get("token_usage") or {}
    parts += [f"  {m}: in={u['input_tokens']} out={u['output_tokens']}" for m, u in usage.items()] or ["  (none reported)"]
    return "\n".join(parts)


def _parse_args(argv: list[str]) -> tuple[str, int | None, str | None] | None:
    """`<spec> [--max-rounds N] [--models PATH]` -> (spec, max_rounds, models_path)."""
    if len(argv) < 2:
        return None
    spec, max_rounds, models = argv[1], None, None
    rest = argv[2:]
    while rest:
        if len(rest) < 2:
            return None
        flag, value = rest[0], rest[1]
        if flag == "--max-rounds":
            try:
                max_rounds = int(value)
            except ValueError:
                return None
        elif flag == "--models":
            models = value
        else:
            return None
        rest = rest[2:]
    return spec, max_rounds, models


async def _run(spec_path: str, max_rounds: int | None, models_path: str | None = None) -> int:
    gateway_url = os.environ.get("MOONSTAR_GATEWAY_URL", "http://localhost:8000")
    token = os.environ.get("MOONSTAR_AUTH_TOKEN")
    if not token:
        print("ERROR: MOONSTAR_AUTH_TOKEN is not set", file=sys.stderr)
        return 1
    spec = load_construct_spec(spec_path)
    result = await run_construct(
        spec_path, gateway_url, token, _PIPELINE_PATH, models_path or _MODELS_PATH,
        max_rounds=max_rounds,
    )
    saved = _save_run(spec.slug, result["session_id"], result)
    print(_format_summary(result))
    print(f"\nsaved: {saved}")
    return 0 if result.get("verdict") == "CONSTRUCTED" else 1


def main(argv: list[str]) -> int:
    parsed = _parse_args(argv)
    if parsed is None:
        print("usage: run_construct.py <spec.yaml> [--max-rounds N] [--models PATH]", file=sys.stderr)
        return 2
    if not os.environ.get("MOONSTAR_AUTH_TOKEN"):
        print("ERROR: MOONSTAR_AUTH_TOKEN is not set", file=sys.stderr)
        return 1
    return asyncio.run(_run(*parsed))


if __name__ == "__main__":
    sys.exit(main(sys.argv))