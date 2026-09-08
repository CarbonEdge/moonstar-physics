"""One-shot CLI: submit a physics hypothesis to the physics_hypothesis pipeline
and print the synthesizer's verdict.

Usage:
    MOONSTAR_AUTH_TOKEN=<token> python scripts/test_hypothesis.py "could a muon decay into an electron and a photon?"

Env vars:
    MOONSTAR_GATEWAY_URL   default http://localhost:8000
    MOONSTAR_AUTH_TOKEN    required — get one via `bash scripts/harness.sh token` in moonstar-rs

physics_hypothesis.yaml mixes LlmTransform steps (dispatched to the
gateway) with deterministic physics-check steps moonstar-rs has no way to
run (see moonstar_physics/local_pipeline.py's module docstring) — this
script runs the DAG locally via that module rather than submitting the
whole YAML as one gateway session.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from moonstar_physics.local_pipeline import run_physics_hypothesis  # noqa: E402

# Windows consoles default stdout/stderr to the system codepage (e.g. cp1252),
# which raises UnicodeEncodeError on ordinary LLM output (em/en dashes, smart
# quotes, non-breaking hyphens). Force UTF-8 with lossy fallback rather than
# crashing after a real, already-completed pipeline run.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

_ROOT_DIR = Path(__file__).parent.parent
_PIPELINE_DIR = _ROOT_DIR / "pipelines"
_RUNS_DIR = _ROOT_DIR / "runs"


def _save_session_artifacts(session_id: str, status_data: dict) -> Path:
    """Persist the full session response (all step artifacts) to disk.

    Printed output only ever shows the synthesizer's writeup — when an
    earlier step degrades silently (truncated response, empty output), the
    only way to diagnose it is to have the raw artifacts on hand.
    """
    _RUNS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _RUNS_DIR / f"{session_id}.json"
    out_path.write_text(json.dumps(status_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


async def _run(hypothesis: str) -> int:
    gateway_url = os.environ.get("MOONSTAR_GATEWAY_URL", "http://localhost:8000")
    token = os.environ.get("MOONSTAR_AUTH_TOKEN")
    if not token:
        print("ERROR: MOONSTAR_AUTH_TOKEN is not set", file=sys.stderr)
        return 1

    print(f"Submitting hypothesis to {gateway_url} (LLM steps only — physics checks run locally) ...")
    status_data = await run_physics_hypothesis(
        hypothesis, gateway_url, token,
        _PIPELINE_DIR / "physics_hypothesis.yaml", _PIPELINE_DIR / "models.json",
    )
    session_id = status_data.get("session_id", "unknown")
    status = status_data.get("status")

    artifacts_path = _save_session_artifacts(session_id, status_data)
    print(f"Full run artifacts saved to: {artifacts_path}")

    if status == "completed":
        for artifact in status_data.get("artifacts", []):
            if artifact.get("transform_name") == "synthesizer":
                writeup = (artifact.get("data") or {}).get("response", "")
                print("\n" + writeup.strip())
                return 0
        print("ERROR: run completed but no synthesizer artifact found", file=sys.stderr)
        return 1

    print(f"ERROR: run {status}: see {artifacts_path} for details", file=sys.stderr)
    return 1


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_hypothesis.py \"<hypothesis>\"", file=sys.stderr)
        sys.exit(1)
    hypothesis = " ".join(sys.argv[1:])
    sys.exit(asyncio.run(_run(hypothesis)))


if __name__ == "__main__":
    main()
