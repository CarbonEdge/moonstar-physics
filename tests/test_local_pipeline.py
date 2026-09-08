"""Tests for moonstar_physics.local_pipeline — the DAG walker that replaced
submitting the whole physics_hypothesis.yaml to the gateway as one session
(moonstar-rs has no way to run its deterministic-check transform types; see
the module's docstring for why). No real gateway is used: LLM steps are
served by an httpx.MockTransport standing in for moonstar-rs.
"""
from __future__ import annotations

import json

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
