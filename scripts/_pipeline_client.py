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
    """Pull the one-line verdict off a synthesizer writeup.

    The synthesizer is prompted to lead with a "VERDICT: <word>" line so the
    verdict survives even if the explanation that follows gets truncated by
    a token-budget cutoff. Falls back to the last non-empty line (stripped
    of markdown emphasis markers, e.g. "**INCONCLUSIVE**" -> "INCONCLUSIVE")
    for older-style writeups without that prefix. Returns "UNKNOWN" if the
    writeup has no non-empty lines.
    """
    lines = [line.strip() for line in writeup.strip().splitlines() if line.strip()]
    if not lines:
        return "UNKNOWN"
    for line in lines:
        stripped = line.strip("*_ ")
        if stripped.upper().startswith("VERDICT:"):
            return stripped.split(":", 1)[1].strip().strip("*_ ")
    return lines[-1].strip("*_ ")


def strip_leading_verdict_line(writeup: str) -> str:
    """Drop a leading "VERDICT: <word>" line (and the blank line after it)
    from a synthesizer writeup before display — extract_verdict() already
    pulled the verdict out for the "**Verdict:** X" heading, so repeating
    the raw prefix line in the writeup body is redundant. Leaves writeups
    without that prefix (e.g. the old last-line style) unchanged.
    """
    lines = writeup.strip("\n").splitlines()
    if lines and lines[0].strip("*_ ").upper().startswith("VERDICT:"):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines = lines[1:]
    return "\n".join(lines)


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
