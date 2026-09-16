"""NumericalExperimentTransform — runs one LLM-generated numpy/scipy
script in an isolated, ephemeral Docker container and parses its printed
RESULT line. Not an LLM step: this is the one place in the
numerical-evidence stage that actually executes generated code, so its
safety contract is load-bearing — see docs/superpowers/specs/
2026-09-16-moonstar-physics-proof-verification-design.md's "Sandbox
isolation" safeguard.

Scoped narrowly to this one fixed contract (run a single numpy/scipy
script, no other imports, print exactly one JSON summary line) — not a
general-purpose code-execution tool for the rest of the workspace.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ._compat import SessionContext

_IMAGE_NAME = "moonstar-physics-experiment-runner"
_DEFAULT_TIMEOUT_SECONDS = 60


def _not_ran(detail: str, stdout: str = "", exit_code: int | None = None) -> dict[str, Any]:
    return {
        "ran": False,
        "result": None,
        "detail": detail,
        "stdout": stdout,
        "exit_code": exit_code,
        "_model": "none",
        "_provider": "none",
        "_input_tokens": 0,
        "_output_tokens": 0,
    }


def _extract_code(input: dict[str, Any]) -> str | None:
    """Pulls the generated script out of whatever single upstream
    dependency this node was wired to (experiment_codegen_a or _b) —
    reads that artifact's "response" field generically rather than via
    parse_extractor_output, since this node's dependency isn't named
    "Extractor"."""
    if len(input) != 1:
        return None
    artifact = next(iter(input.values()))
    if not isinstance(artifact, dict):
        return None
    raw = artifact.get("response")
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:]
    text = text.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    code = parsed.get("code")
    return code if isinstance(code, str) else None


def _parse_result_line(stdout: str) -> dict[str, Any] | None:
    result_lines = [line for line in stdout.splitlines() if line.startswith("RESULT: ")]
    if not result_lines:
        return None
    payload = result_lines[-1][len("RESULT: "):]
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


async def NumericalExperimentTransform(
    input: dict[str, Any], config: dict[str, Any], ctx: SessionContext
) -> dict[str, Any]:
    code = _extract_code(input)
    if code is None:
        return _not_ran("upstream experiment_codegen artifact had no usable 'code' field")

    timeout_seconds = config.get("timeout_seconds", _DEFAULT_TIMEOUT_SECONDS)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        script_path = f.name

    try:
        docker_cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", "512m",
            "--cpus", "1",
            "--pids-limit", "64",
            "--read-only",
            "--tmpfs", "/tmp",
            "-v", f"{script_path}:/experiment/run.py:ro",
            _IMAGE_NAME,
            "python", "/experiment/run.py",
        ]
        try:
            proc = subprocess.run(
                docker_cmd, capture_output=True, text=True, timeout=timeout_seconds
            )
        except subprocess.TimeoutExpired as e:
            stdout = e.stdout if isinstance(e.stdout, str) else ""
            return _not_ran(f"sandbox run exceeded {timeout_seconds}s timeout", stdout=stdout)
        except OSError as e:
            return _not_ran(f"failed to invoke docker: {e}")
    finally:
        Path(script_path).unlink(missing_ok=True)

    if proc.returncode != 0:
        return _not_ran(
            f"sandbox exited with code {proc.returncode}", stdout=proc.stdout, exit_code=proc.returncode
        )

    result = _parse_result_line(proc.stdout)
    if result is None:
        return _not_ran(
            "no valid RESULT: line in sandbox stdout", stdout=proc.stdout, exit_code=proc.returncode
        )

    return {
        "ran": True,
        "result": result,
        "detail": None,
        "stdout": proc.stdout,
        "exit_code": proc.returncode,
        "_model": "none",
        "_provider": "none",
        "_input_tokens": 0,
        "_output_tokens": 0,
    }
