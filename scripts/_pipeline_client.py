"""Shared gateway submit/poll helpers for paper-review publishing scripts.

Pure/testable pieces (render_pipeline_yaml, find_artifact, extract_verdict)
are separated from the one network function (submit_and_wait) so tests
don't need a real gateway.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

_POLL_INTERVAL_SECONDS = 2
_MAX_POLLS = 90


class PipelineRunError(RuntimeError):
    """Raised when a submitted pipeline session times out waiting to complete."""


def render_pipeline_yaml(pipeline_path: Path, models_path: Path) -> str:
    models = json.loads(models_path.read_text(encoding="utf-8"))
    text = pipeline_path.read_text(encoding="utf-8")
    for key, model in models.items():
        text = text.replace("{{" + key + "}}", model)
    return text


def find_artifact(status_data: dict[str, Any], transform_name: str) -> dict[str, Any] | None:
    for artifact in status_data.get("artifacts", []):
        if artifact.get("transform_name") == transform_name:
            return artifact.get("data") or {}
    return None


def extract_verdict(writeup: str) -> str:
    """Pull the trailing one-line verdict off a synthesizer writeup.

    Takes the last non-empty line and strips markdown emphasis markers,
    e.g. "**INCONCLUSIVE**" -> "INCONCLUSIVE". Returns "UNKNOWN" if the
    writeup has no non-empty lines.
    """
    lines = [line.strip() for line in writeup.strip().splitlines() if line.strip()]
    if not lines:
        return "UNKNOWN"
    return lines[-1].strip("*_ ")


async def submit_and_wait(
    client: httpx.AsyncClient,
    gateway_url: str,
    token: str,
    yaml_spec: str,
    initial_input: dict[str, Any],
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    submit_resp = await client.post(
        f"{gateway_url}/pipelines/run",
        json={"yaml_spec": yaml_spec, "initial_input": initial_input},
        headers=headers,
    )
    submit_resp.raise_for_status()
    session_id = submit_resp.json()["session_id"]

    for _ in range(_MAX_POLLS):
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
        status_resp = await client.get(f"{gateway_url}/sessions/{session_id}", headers=headers)
        status_resp.raise_for_status()
        status_data = status_resp.json()
        if status_data.get("status") in ("completed", "failed", "rejected"):
            return status_data

    raise PipelineRunError(f"session {session_id} timed out waiting for completion")
