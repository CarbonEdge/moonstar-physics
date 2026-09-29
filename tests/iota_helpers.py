"""Run a generated iota-trace script with the host interpreter (no Docker)."""
from __future__ import annotations

import json
import subprocess
import sys
from typing import Any


def run_script_locally(script: str, timeout_seconds: int = 120) -> dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=timeout_seconds,
    )
    lines = [ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT: ")]
    assert lines, f"no RESULT line; stderr:\n{proc.stderr}"
    return json.loads(lines[-1][len("RESULT: "):])


async def fake_sandbox(script: str, timeout_seconds: int) -> dict[str, Any]:
    result = run_script_locally(script, timeout_seconds)
    return {
        "ran": True, "result": result, "detail": None,
        "stdout": "RESULT: " + json.dumps(result), "exit_code": 0,
    }