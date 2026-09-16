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


async def test_timeout_force_removes_the_named_container(ctx):
    # Finding 1: subprocess.run's timeout kills the `docker` CLI client,
    # not the container — --rm only fires on container exit. The timeout
    # handler must best-effort `docker rm -f` the container it named.
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[0:2] == ["docker", "run"]:
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=60, output="partial output")
        return _FakeCompletedProcess(0, "")

    with patch(
        "moonstar_physics.numerical_experiment_transform.subprocess.run", side_effect=fake_run
    ):
        result = await NumericalExperimentTransform(_codegen_input("..."), {}, ctx)

    assert result["ran"] is False
    run_cmd = calls[0]
    name_idx = run_cmd.index("--name")
    container_name = run_cmd[name_idx + 1]
    assert container_name.startswith("moonstar-exp-")

    assert len(calls) == 2
    cleanup_cmd = calls[1]
    assert cleanup_cmd == ["docker", "rm", "-f", container_name]


async def test_timeout_cleanup_failure_does_not_mask_original_timeout_report(ctx):
    # The cleanup call's own failure must never escape or replace the
    # original timeout detail returned to the caller.
    def fake_run(cmd, **kwargs):
        if cmd[0:2] == ["docker", "run"]:
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=60, output="partial output")
        raise OSError("docker daemon unreachable")

    with patch(
        "moonstar_physics.numerical_experiment_transform.subprocess.run", side_effect=fake_run
    ):
        result = await NumericalExperimentTransform(_codegen_input("..."), {}, ctx)

    assert result["ran"] is False
    assert "timeout" in result["detail"].lower()


async def test_timeout_stdout_is_truncated(ctx):
    huge_output = "x" * 100_000

    def fake_run(cmd, **kwargs):
        if cmd[0:2] == ["docker", "run"]:
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=60, output=huge_output)
        return _FakeCompletedProcess(0, "")

    with patch(
        "moonstar_physics.numerical_experiment_transform.subprocess.run", side_effect=fake_run
    ):
        result = await NumericalExperimentTransform(_codegen_input("..."), {}, ctx)

    assert len(result["stdout"]) < 100_000
    assert "truncated" in result["stdout"]


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
    # Finding 1: an explicit unique container name so a timed-out run can
    # be force-removed via `docker rm -f <name>`.
    assert "--name" in called_cmd
    name_idx = called_cmd.index("--name")
    assert called_cmd[name_idx + 1].startswith("moonstar-exp-")


async def test_docker_command_uses_utf8_replace_encoding(ctx):
    # Finding 3: text=True with no explicit encoding decodes with the OS
    # ANSI codepage on Windows and can raise UnicodeDecodeError from
    # inside subprocess.run itself. Must match _extract_pdf_text's
    # established convention: encoding="utf-8", errors="replace".
    fake = _FakeCompletedProcess(0, "RESULT: {}\n")
    with patch("moonstar_physics.numerical_experiment_transform.subprocess.run", return_value=fake) as mock_run:
        await NumericalExperimentTransform(_codegen_input("print(1)"), {}, ctx)
    assert mock_run.call_args.kwargs["encoding"] == "utf-8"
    assert mock_run.call_args.kwargs["errors"] == "replace"
    assert mock_run.call_args.kwargs["text"] is True


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


async def test_success_stdout_is_truncated_and_reports_original_length(ctx):
    # Finding 2: unbounded stdout capture bloats gateway payloads and
    # audit files. The success path must cap the stored stdout.
    huge_prefix = "x" * 100_000
    fake = _FakeCompletedProcess(0, f"{huge_prefix}\nRESULT: {{\"ok\": true}}\n")
    with patch("moonstar_physics.numerical_experiment_transform.subprocess.run", return_value=fake):
        result = await NumericalExperimentTransform(_codegen_input("..."), {}, ctx)
    assert result["ran"] is True
    assert result["result"] == {"ok": True}
    assert len(result["stdout"]) < 100_000
    assert "truncated" in result["stdout"]
    assert "original length" in result["stdout"]


async def test_result_line_past_64kb_is_still_found_before_truncation(ctx):
    # RESULT: is searched on the FULL untruncated stdout — truncating
    # before searching would silently break a correct script that just
    # printed a lot of earlier diagnostic output.
    huge_prefix = "diagnostic line\n" * 10_000  # well over 64KB
    fake = _FakeCompletedProcess(0, f"{huge_prefix}RESULT: {{\"late\": true}}\n")
    with patch("moonstar_physics.numerical_experiment_transform.subprocess.run", return_value=fake):
        result = await NumericalExperimentTransform(_codegen_input("..."), {}, ctx)
    assert result["ran"] is True
    assert result["result"] == {"late": True}
    # the returned stdout is still capped even though the RESULT line was found
    assert len(result["stdout"]) < len(huge_prefix)


async def test_non_zero_exit_stdout_is_truncated(ctx):
    huge_output = "Traceback...\n" + "x" * 100_000
    fake = _FakeCompletedProcess(1, huge_output)
    with patch("moonstar_physics.numerical_experiment_transform.subprocess.run", return_value=fake):
        result = await NumericalExperimentTransform(_codegen_input("..."), {}, ctx)
    assert result["ran"] is False
    assert len(result["stdout"]) < len(huge_output)


async def test_missing_result_line_stdout_is_truncated(ctx):
    huge_output = "x" * 100_000
    fake = _FakeCompletedProcess(0, huge_output)
    with patch("moonstar_physics.numerical_experiment_transform.subprocess.run", return_value=fake):
        result = await NumericalExperimentTransform(_codegen_input("..."), {}, ctx)
    assert result["ran"] is False
    assert len(result["stdout"]) < len(huge_output)


async def test_small_stdout_is_not_truncated(ctx):
    fake = _FakeCompletedProcess(0, "RESULT: {\"ok\": true}\n")
    with patch("moonstar_physics.numerical_experiment_transform.subprocess.run", return_value=fake):
        result = await NumericalExperimentTransform(_codegen_input("..."), {}, ctx)
    assert result["stdout"] == "RESULT: {\"ok\": true}\n"
    assert "truncated" not in result["stdout"]
