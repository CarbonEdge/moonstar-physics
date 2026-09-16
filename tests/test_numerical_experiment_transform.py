"""Tests for NumericalExperimentTransform. Runs against a mocked
subprocess.run — never spins up a real Docker daemon here. See
moonstar-physics/README.md for the separate manual/local-only end-to-end
test that actually builds the image and runs a trivial script."""
from __future__ import annotations

import json
import subprocess
from unittest.mock import AsyncMock, patch

import pytest

from moonstar_physics._compat import SessionContext
from moonstar_physics.numerical_experiment_transform import NumericalExperimentTransform


@pytest.fixture
def ctx() -> AsyncMock:
    return AsyncMock(spec=SessionContext)


def _codegen_input(code: str) -> dict:
    return {"experiment_codegen_a": {"response": json.dumps({"code": code})}}


class _FakeCompletedProcess:
    def __init__(self, returncode: int, stdout: str):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = ""


async def test_valid_result_line_is_parsed(ctx):
    fake = _FakeCompletedProcess(0, "some diagnostic output\nRESULT: {\"diverged\": true, \"linf\": 99.0}\n")
    with patch("moonstar_physics.numerical_experiment_transform.subprocess.run", return_value=fake):
        result = await NumericalExperimentTransform(_codegen_input("print('RESULT: {}')"), {}, ctx)
    assert result["ran"] is True
    assert result["result"] == {"diverged": True, "linf": 99.0}
    assert result["exit_code"] == 0


async def test_last_result_line_wins_when_multiple_present(ctx):
    fake = _FakeCompletedProcess(0, 'RESULT: {"a": 1}\nRESULT: {"a": 2}\n')
    with patch("moonstar_physics.numerical_experiment_transform.subprocess.run", return_value=fake):
        result = await NumericalExperimentTransform(_codegen_input("..."), {}, ctx)
    assert result["result"] == {"a": 2}


async def test_timeout_yields_not_ran(ctx):
    with patch(
        "moonstar_physics.numerical_experiment_transform.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["docker"], timeout=60, output="partial output"),
    ):
        result = await NumericalExperimentTransform(_codegen_input("..."), {}, ctx)
    assert result["ran"] is False
    assert "timeout" in result["detail"].lower()


async def test_non_zero_exit_yields_not_ran(ctx):
    fake = _FakeCompletedProcess(1, "Traceback (most recent call last): ...")
    with patch("moonstar_physics.numerical_experiment_transform.subprocess.run", return_value=fake):
        result = await NumericalExperimentTransform(_codegen_input("..."), {}, ctx)
    assert result["ran"] is False
    assert result["exit_code"] == 1


async def test_missing_result_line_yields_not_ran(ctx):
    fake = _FakeCompletedProcess(0, "no result line printed here\n")
    with patch("moonstar_physics.numerical_experiment_transform.subprocess.run", return_value=fake):
        result = await NumericalExperimentTransform(_codegen_input("..."), {}, ctx)
    assert result["ran"] is False
    assert "RESULT" in result["detail"]


async def test_malformed_result_json_yields_not_ran(ctx):
    fake = _FakeCompletedProcess(0, "RESULT: {not valid json\n")
    with patch("moonstar_physics.numerical_experiment_transform.subprocess.run", return_value=fake):
        result = await NumericalExperimentTransform(_codegen_input("..."), {}, ctx)
    assert result["ran"] is False


async def test_missing_code_field_never_invokes_subprocess(ctx):
    bad_input = {"experiment_codegen_a": {"response": json.dumps({"not_code": "x"})}}
    with patch("moonstar_physics.numerical_experiment_transform.subprocess.run") as mock_run:
        result = await NumericalExperimentTransform(bad_input, {}, ctx)
    mock_run.assert_not_called()
    assert result["ran"] is False


async def test_docker_command_uses_expected_isolation_flags(ctx):
    fake = _FakeCompletedProcess(0, "RESULT: {}\n")
    with patch("moonstar_physics.numerical_experiment_transform.subprocess.run", return_value=fake) as mock_run:
        await NumericalExperimentTransform(_codegen_input("print(1)"), {}, ctx)
    called_cmd = mock_run.call_args.args[0]
    assert called_cmd[0:3] == ["docker", "run", "--rm"]
    assert "--network" in called_cmd and "none" in called_cmd
    assert "--read-only" in called_cmd
    assert "--pids-limit" in called_cmd and "64" in called_cmd
    assert "moonstar-physics-experiment-runner" in called_cmd


async def test_custom_timeout_from_config_is_passed_through(ctx):
    fake = _FakeCompletedProcess(0, "RESULT: {}\n")
    with patch("moonstar_physics.numerical_experiment_transform.subprocess.run", return_value=fake) as mock_run:
        await NumericalExperimentTransform(_codegen_input("print(1)"), {"timeout_seconds": 15}, ctx)
    assert mock_run.call_args.kwargs["timeout"] == 15


async def test_response_wrapped_in_markdown_fence_is_still_parsed(ctx):
    fenced = "```json\n" + json.dumps({"code": "print('hi')"}) + "\n```"
    input_ = {"experiment_codegen_a": {"response": fenced}}
    fake = _FakeCompletedProcess(0, "RESULT: {}\n")
    with patch("moonstar_physics.numerical_experiment_transform.subprocess.run", return_value=fake) as mock_run:
        result = await NumericalExperimentTransform(input_, {}, ctx)
    mock_run.assert_called_once()
    assert result["ran"] is True
