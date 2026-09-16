"""Tests for moonstar_physics.local_pipeline — the DAG walker that replaced
submitting the whole physics_hypothesis.yaml to the gateway as one session
(moonstar-rs has no way to run its deterministic-check transform types; see
the module's docstring for why). No real gateway is used: LLM steps are
served by an httpx.MockTransport standing in for moonstar-rs.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import yaml

from moonstar_physics import local_pipeline


def _paths():
    from pathlib import Path

    root = Path(__file__).parent.parent
    return root / "pipelines" / "physics_hypothesis.yaml", root / "pipelines" / "models.json"


_EXTRACTOR_RESPONSE = json.dumps(
    {
        "hypothesis_type": "decay",
        "particles_involved": ["muon", "electron", "muon_neutrino", "electron_neutrino"],
        "initial_state": [{"particle": "muon", "count": 1}],
        "final_state": [
            {"particle": "electron", "count": 1},
            {"particle": "muon_neutrino", "count": 1},
            {"particle": "electron_neutrino", "antiparticle": True, "count": 1},
        ],
        "claimed_values": {},
        "system_description": "",
        "system_params": {"type": None},
        "dimension_claims": [],
    }
)

_LLM_RESPONSES = {
    "Extractor": _EXTRACTOR_RESPONSE,
    "theory_critic": json.dumps(
        {"well_posed": True, "theoretical_concerns": [], "assessment": "looks fine"}
    ),
    "devils_advocate": json.dumps(
        {
            "agreement": "wave-1 checks agree",
            "contradiction": "none",
            "coverage_gaps": [],
            "strongest_objection": "none",
        }
    ),
    "synthesizer": "VERDICT: PLAUSIBLE\n\nThis is a real, allowed muon decay.",
}


def _mock_transport(seen_requests: list[dict]):
    sessions: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/pipelines/run":
            body = json.loads(request.content)
            spec = yaml.safe_load(body["yaml_spec"])
            node_name = spec["transforms"][0]["name"]
            seen_requests.append({"node": node_name, "initial_input": body["initial_input"]})
            session_id = f"sess-{node_name}"
            sessions[session_id] = node_name
            return httpx.Response(200, json={"session_id": session_id})

        if request.url.path.startswith("/sessions/"):
            session_id = request.url.path.rsplit("/", 1)[-1]
            node_name = sessions[session_id]
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "session_id": session_id,
                    "artifacts": [
                        {
                            "transform_name": node_name,
                            "data": {"response": _LLM_RESPONSES[node_name]},
                        }
                    ],
                },
            )

        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    return httpx.MockTransport(handler)


async def test_full_dag_wires_llm_steps_to_gateway_and_checks_locally():
    seen: list[dict] = []
    pipeline_path, models_path = _paths()

    result = await local_pipeline.run_physics_hypothesis(
        "could a muon decay into an electron, a muon-neutrino, and an anti-electron-neutrino?",
        "http://gateway.test",
        "tok",
        pipeline_path,
        models_path,
        transport=_mock_transport(seen),
    )

    assert result["status"] == "completed"
    by_name = {a["transform_name"]: a["data"] for a in result["artifacts"]}

    # All 4 LLM steps went to the gateway (mock transport), in DAG order.
    assert [r["node"] for r in seen] == [
        "Extractor",
        "theory_critic",
        "devils_advocate",
        "synthesizer",
    ]

    # The 4 deterministic checks ran locally — never touched the mock transport.
    assert by_name["conservation_check"]["verdict"] == "consistent"
    assert by_name["qm_calculation"]["verdict"] == "not_applicable"
    assert by_name["reference_lookup"]["verdict"] == "consistent"
    assert by_name["dimension_check"]["verdict"] == "not_applicable"

    # theory_critic received exactly the Extractor artifact as its input.
    assert seen[1]["initial_input"] == {"Extractor": {"response": _EXTRACTOR_RESPONSE}}

    # devils_advocate received all 5 wave-1 outputs.
    assert set(seen[2]["initial_input"].keys()) == {
        "conservation_check",
        "qm_calculation",
        "reference_lookup",
        "dimension_check",
        "theory_critic",
    }

    # synthesizer received all 6 prior outputs.
    assert set(seen[3]["initial_input"].keys()) == {
        "conservation_check",
        "qm_calculation",
        "reference_lookup",
        "dimension_check",
        "theory_critic",
        "devils_advocate",
    }

    assert by_name["synthesizer"]["response"].startswith("VERDICT: PLAUSIBLE")


async def test_malformed_extractor_output_fails_locally_without_calling_gateway_again():
    seen: list[dict] = []
    pipeline_path, models_path = _paths()

    responses = dict(_LLM_RESPONSES)
    responses["Extractor"] = json.dumps(
        {
            "initial_state": "not-a-list",  # triggers NonRetryableTransformError locally
            "final_state": [{"particle": "electron"}],
            "particles_involved": [],
            "system_params": {"type": None},
            "dimension_claims": [],
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/pipelines/run":
            body = json.loads(request.content)
            spec = yaml.safe_load(body["yaml_spec"])
            node_name = spec["transforms"][0]["name"]
            seen.append(node_name)
            return httpx.Response(200, json={"session_id": f"sess-{node_name}"})
        if request.url.path.startswith("/sessions/"):
            node_name = request.url.path.rsplit("/", 1)[-1].removeprefix("sess-")
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "artifacts": [
                        {"transform_name": node_name, "data": {"response": responses[node_name]}}
                    ],
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    result = await local_pipeline.run_physics_hypothesis(
        "malformed hypothesis",
        "http://gateway.test",
        "tok",
        pipeline_path,
        models_path,
        transport=httpx.MockTransport(handler),
    )

    assert result["status"] == "failed"
    assert "initial_state" in result["error"]
    # Only Extractor was submitted — the DAG stopped before theory_critic/
    # devils_advocate/synthesizer ever reached the gateway.
    assert seen == ["Extractor"]


_PROOF_EXTRACTOR_RESPONSE = json.dumps(
    {
        "proof_context": "Testing whether the paper's own definitions A = 1/2+h and D = 1/2-h sum to 1.",
        "algebraic_claims": [
            {
                "description": "A + D sums to 1",
                "lhs": "(Rational(1,2)+h)+(Rational(1,2)-h)",
                "rhs": "1",
                "variables": ["h"],
            }
        ],
    }
)

_PROOF_LLM_RESPONSES = {
    "Extractor": _PROOF_EXTRACTOR_RESPONSE,
    "proof_critic": json.dumps(
        {"algebra_sufficient_if_verified": True, "logical_gap": "none", "assessment": "the claim is a direct algebraic consequence"}
    ),
    "devils_advocate": json.dumps(
        {
            "agreement": "identity_checks and proof_critic agree",
            "contradiction": "none",
            "coverage_gaps": [],
            "strongest_objection": "none",
        }
    ),
    "synthesizer": "VERDICT: PLAUSIBLE\n\nThe transcribed algebra checks out.",
}


def _proof_pipeline_path():
    from pathlib import Path

    root = Path(__file__).parent.parent
    return root / "pipelines" / "proof_hypothesis.yaml", root / "pipelines" / "models.json"


def _proof_mock_transport(seen_requests: list[dict]):
    sessions: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/pipelines/run":
            body = json.loads(request.content)
            spec = yaml.safe_load(body["yaml_spec"])
            node_name = spec["transforms"][0]["name"]
            seen_requests.append({"node": node_name, "initial_input": body["initial_input"]})
            session_id = f"sess-{node_name}"
            sessions[session_id] = node_name
            return httpx.Response(200, json={"session_id": session_id})

        if request.url.path.startswith("/sessions/"):
            session_id = request.url.path.rsplit("/", 1)[-1]
            node_name = sessions[session_id]
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "session_id": session_id,
                    "artifacts": [
                        {
                            "transform_name": node_name,
                            "data": {"response": _PROOF_LLM_RESPONSES[node_name]},
                        }
                    ],
                },
            )

        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    return httpx.MockTransport(handler)


async def test_proof_dag_wires_llm_steps_to_gateway_and_checks_locally():
    seen: list[dict] = []
    pipeline_path, models_path = _proof_pipeline_path()

    result = await local_pipeline.run_proof_hypothesis(
        "the paper defines A = 1/2+h and D = 1/2-h; do they sum to 1?",
        "http://gateway.test",
        "tok",
        pipeline_path,
        models_path,
        transport=_proof_mock_transport(seen),
    )

    assert result["status"] == "completed"
    by_name = {a["transform_name"]: a["data"] for a in result["artifacts"]}

    assert [r["node"] for r in seen] == ["Extractor", "proof_critic", "devils_advocate", "synthesizer"]

    # identity_checks ran locally — never touched the mock transport.
    assert by_name["identity_checks"]["verdict"] == "consistent"

    # proof_critic received exactly the Extractor artifact as its input.
    assert seen[1]["initial_input"] == {"Extractor": {"response": _PROOF_EXTRACTOR_RESPONSE}}

    # devils_advocate received both wave-1 outputs.
    assert set(seen[2]["initial_input"].keys()) == {"identity_checks", "proof_critic"}

    # synthesizer received all 3 prior outputs.
    assert set(seen[3]["initial_input"].keys()) == {"identity_checks", "proof_critic", "devils_advocate"}

    assert by_name["synthesizer"]["response"].startswith("VERDICT: PLAUSIBLE")


async def test_proof_pipeline_with_no_stated_equations_is_not_applicable_but_completes():
    seen: list[dict] = []
    pipeline_path, models_path = _proof_pipeline_path()

    responses = dict(_PROOF_LLM_RESPONSES)
    responses["Extractor"] = json.dumps({"proof_context": "pure prose, no equations", "algebraic_claims": []})

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/pipelines/run":
            body = json.loads(request.content)
            spec = yaml.safe_load(body["yaml_spec"])
            node_name = spec["transforms"][0]["name"]
            seen.append(node_name)
            return httpx.Response(200, json={"session_id": f"sess-{node_name}"})
        if request.url.path.startswith("/sessions/"):
            node_name = request.url.path.rsplit("/", 1)[-1].removeprefix("sess-")
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "artifacts": [{"transform_name": node_name, "data": {"response": responses[node_name]}}],
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    result = await local_pipeline.run_proof_hypothesis(
        "pure prose hypothesis with no equations",
        "http://gateway.test",
        "tok",
        pipeline_path,
        models_path,
        transport=httpx.MockTransport(handler),
    )

    assert result["status"] == "completed"
    by_name = {a["transform_name"]: a["data"] for a in result["artifacts"]}
    assert by_name["identity_checks"]["verdict"] == "not_applicable"
    # the DAG still ran to completion — a not_applicable check isn't a failure.
    assert seen == ["Extractor", "proof_critic", "devils_advocate", "synthesizer"]


_NUMERICAL_EXTRACTOR_RESPONSE = json.dumps(
    {
        "proof_context": "Testing a viscosity-rescaling L2-norm scaling relation.",
        "algebraic_claims": [
            {"description": "trivial arithmetic", "lhs": "2 + 2", "rhs": "4", "variables": []},
        ],
    }
)

_REDUCTION_RESPONSE = json.dumps(
    {
        "reduction_description": "A 1D self-similar ODE capturing the scaling.",
        "equations": "dy/dt = -y, y(0) = 1",
        "claimed_signature": "y(t) decays to near zero by t=5",
    }
)

_CODEGEN_RESPONSE = json.dumps({"code": "print('RESULT: {\"decayed\": true}')"})

_EVIDENCE_CRITIC_RESPONSE = json.dumps(
    {
        "derivations_agree": True,
        "both_ran_successfully": True,
        "results_agree_with_each_other": True,
        "results_match_claimed_signature": True,
        "verdict": "corroborates",
        "assessment": "Both runs show decay as claimed.",
    }
)

_NUMERICAL_LLM_RESPONSES = {
    "Extractor": _NUMERICAL_EXTRACTOR_RESPONSE,
    "proof_critic": json.dumps(
        {"algebra_sufficient_if_verified": True, "logical_gap": "none", "assessment": "fine"}
    ),
    "reduction_a": _REDUCTION_RESPONSE,
    "reduction_b": _REDUCTION_RESPONSE,
    "experiment_codegen_a": _CODEGEN_RESPONSE,
    "experiment_codegen_b": _CODEGEN_RESPONSE,
    "evidence_critic": _EVIDENCE_CRITIC_RESPONSE,
    "devils_advocate": json.dumps(
        {
            "agreement": "all checks agree",
            "contradiction": "none",
            "coverage_gaps": [],
            "numerical_evidence_weight": "corroborating, not decisive",
            "strongest_objection": "none",
        }
    ),
    "synthesizer": "VERDICT: PLAUSIBLE\n\nThe algebra checks out and the numerical evidence corroborates.",
}


def _numerical_pipeline_path():
    from pathlib import Path

    root = Path(__file__).parent.parent
    return root / "pipelines" / "proof_hypothesis_numerical.yaml", root / "pipelines" / "models.json"


def _numerical_mock_transport(seen_requests: list[dict]):
    sessions: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/pipelines/run":
            body = json.loads(request.content)
            spec = yaml.safe_load(body["yaml_spec"])
            node_name = spec["transforms"][0]["name"]
            seen_requests.append({"node": node_name, "initial_input": body["initial_input"]})
            session_id = f"sess-{node_name}"
            sessions[session_id] = node_name
            return httpx.Response(200, json={"session_id": session_id})

        if request.url.path.startswith("/sessions/"):
            session_id = request.url.path.rsplit("/", 1)[-1]
            node_name = sessions[session_id]
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "session_id": session_id,
                    "artifacts": [
                        {
                            "transform_name": node_name,
                            "data": {"response": _NUMERICAL_LLM_RESPONSES[node_name]},
                        }
                    ],
                },
            )

        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    return httpx.MockTransport(handler)


async def test_numerical_dag_wires_llm_steps_to_gateway_and_sandbox_locally():
    seen: list[dict] = []
    pipeline_path, models_path = _numerical_pipeline_path()

    fake_sandbox_result = {
        "ran": True,
        "result": {"decayed": True},
        "detail": None,
        "stdout": "RESULT: {\"decayed\": true}\n",
        "exit_code": 0,
        "_model": "none",
        "_provider": "none",
        "_input_tokens": 0,
        "_output_tokens": 0,
    }

    with patch(
        "moonstar_physics.local_pipeline.NumericalExperimentTransform",
        new=AsyncMock(return_value=fake_sandbox_result),
    ) as mock_sandbox:
        result = await local_pipeline.run_proof_hypothesis_numerical(
            "does y(t) decay as claimed by the viscosity-rescaling reduction?",
            "paper summary text",
            "http://gateway.test",
            "tok",
            pipeline_path,
            models_path,
            transport=_numerical_mock_transport(seen),
        )

    assert result["status"] == "completed"
    by_name = {a["transform_name"]: a["data"] for a in result["artifacts"]}

    assert [r["node"] for r in seen] == [
        "Extractor",
        "proof_critic",
        "reduction_a",
        "reduction_b",
        "experiment_codegen_a",
        "experiment_codegen_b",
        "evidence_critic",
        "devils_advocate",
        "synthesizer",
    ]

    # identity_checks and both sandbox runs went local, never through the mock transport.
    assert by_name["identity_checks"]["verdict"] == "consistent"
    assert mock_sandbox.await_count == 2
    assert by_name["sandbox_runner_a"] == fake_sandbox_result
    assert by_name["sandbox_runner_b"] == fake_sandbox_result

    # reduction_a/b both received the same {hypothesis, paper_summary} initial_input.
    reduction_a_req = next(r for r in seen if r["node"] == "reduction_a")
    reduction_b_req = next(r for r in seen if r["node"] == "reduction_b")
    assert reduction_a_req["initial_input"] == {
        "hypothesis": "does y(t) decay as claimed by the viscosity-rescaling reduction?",
        "paper_summary": "paper summary text",
    }
    assert reduction_b_req["initial_input"] == reduction_a_req["initial_input"]

    # experiment_codegen_a received exactly reduction_a's artifact.
    codegen_a_req = next(r for r in seen if r["node"] == "experiment_codegen_a")
    assert codegen_a_req["initial_input"] == {"reduction_a": {"response": _REDUCTION_RESPONSE}}

    # evidence_critic received both reductions and both sandbox results.
    evidence_req = next(r for r in seen if r["node"] == "evidence_critic")
    assert set(evidence_req["initial_input"].keys()) == {
        "reduction_a", "reduction_b", "sandbox_runner_a", "sandbox_runner_b",
    }

    # devils_advocate received identity_checks, proof_critic, and evidence_critic.
    devils_req = next(r for r in seen if r["node"] == "devils_advocate")
    assert set(devils_req["initial_input"].keys()) == {"identity_checks", "proof_critic", "evidence_critic"}

    # synthesizer received all four prior wave outputs.
    synth_req = next(r for r in seen if r["node"] == "synthesizer")
    assert set(synth_req["initial_input"].keys()) == {
        "identity_checks", "proof_critic", "evidence_critic", "devils_advocate",
    }

    assert by_name["synthesizer"]["response"].startswith("VERDICT: PLAUSIBLE")


async def test_numerical_pipeline_propagates_not_ran_sandbox_results_without_crashing():
    seen: list[dict] = []
    pipeline_path, models_path = _numerical_pipeline_path()

    not_ran_result = {
        "ran": False,
        "result": None,
        "detail": "sandbox exited with code 1",
        "stdout": "Traceback...",
        "exit_code": 1,
        "_model": "none",
        "_provider": "none",
        "_input_tokens": 0,
        "_output_tokens": 0,
    }

    with patch(
        "moonstar_physics.local_pipeline.NumericalExperimentTransform",
        new=AsyncMock(return_value=not_ran_result),
    ):
        result = await local_pipeline.run_proof_hypothesis_numerical(
            "hypothesis text",
            "paper summary text",
            "http://gateway.test",
            "tok",
            pipeline_path,
            models_path,
            transport=_numerical_mock_transport(seen),
        )

    assert result["status"] == "completed"
    by_name = {a["transform_name"]: a["data"] for a in result["artifacts"]}
    assert by_name["sandbox_runner_a"]["ran"] is False
    assert by_name["sandbox_runner_b"]["ran"] is False
    # the DAG still ran to completion — evidence_critic decides what a
    # failed sandbox run means, local_pipeline doesn't short-circuit.
    assert [r["node"] for r in seen][-1] == "synthesizer"
