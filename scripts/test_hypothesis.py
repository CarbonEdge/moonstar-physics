"""One-shot CLI: submit a physics hypothesis to the physics_hypothesis pipeline
and print the synthesizer's verdict.

Usage:
    MOONSTAR_AUTH_TOKEN=<token> python scripts/test_hypothesis.py "could a muon decay into an electron and a photon?"

Env vars:
    MOONSTAR_GATEWAY_URL   default http://localhost:8000
    MOONSTAR_AUTH_TOKEN    required — get one via `python -m moonstar_gateway.cli seed-user`
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx

_PIPELINE_DIR = Path(__file__).parent.parent / "pipelines"
_POLL_INTERVAL_SECONDS = 2
_MAX_POLLS = 90


def _load_pipeline_yaml() -> str:
    models = json.loads((_PIPELINE_DIR / "models.json").read_text(encoding="utf-8"))
    text = (_PIPELINE_DIR / "physics_hypothesis.yaml").read_text(encoding="utf-8")
    for key, model in models.items():
        text = text.replace("{{" + key + "}}", model)
    return text


async def _run(hypothesis: str) -> int:
    gateway_url = os.environ.get("MOONSTAR_GATEWAY_URL", "http://localhost:8000")
    token = os.environ.get("MOONSTAR_AUTH_TOKEN")
    if not token:
        print("ERROR: MOONSTAR_AUTH_TOKEN is not set", file=sys.stderr)
        return 1

    yaml_spec = _load_pipeline_yaml()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        print(f"Submitting hypothesis to {gateway_url} ...")
        submit_resp = await client.post(
            f"{gateway_url}/pipelines/run",
            json={"yaml_spec": yaml_spec, "initial_input": {"hypothesis": hypothesis}},
            headers=headers,
        )
        submit_resp.raise_for_status()
        session_id = submit_resp.json()["session_id"]
        print(f"Session: {session_id}")

        for _ in range(_MAX_POLLS):
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)
            status_resp = await client.get(f"{gateway_url}/sessions/{session_id}", headers=headers)
            status_resp.raise_for_status()
            status_data = status_resp.json()
            status = status_data.get("status")

            if status == "completed":
                for artifact in status_data.get("artifacts", []):
                    if artifact.get("transform_name") == "synthesizer":
                        writeup = (artifact.get("data") or {}).get("response", "")
                        print("\n" + writeup.strip())
                        return 0
                print("ERROR: session completed but no synthesizer artifact found", file=sys.stderr)
                return 1

            if status in ("failed", "rejected"):
                print(f"ERROR: session {status}: {status_data}", file=sys.stderr)
                return 1

        print("ERROR: timed out waiting for session to complete", file=sys.stderr)
        return 1


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_hypothesis.py \"<hypothesis>\"", file=sys.stderr)
        sys.exit(1)
    hypothesis = " ".join(sys.argv[1:])
    sys.exit(asyncio.run(_run(hypothesis)))


if __name__ == "__main__":
    main()
