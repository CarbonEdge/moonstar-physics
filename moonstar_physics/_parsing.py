"""Shared parsing contract for the Extractor step's LLM output.

LlmTransform always returns {"response": "<raw text>"} — never pre-parsed
JSON (see moonstar-ai/moonstar_ai/transform.py). Every custom transform in
the physics_hypothesis pipeline receives {"Extractor": {"response": "..."}}
as its `input` and must go through this parser first.
"""
from __future__ import annotations

import json
from typing import Any

from moonstar_core.exceptions import NonRetryableTransformError


def parse_extractor_output(input: dict[str, Any]) -> dict[str, Any]:
    extractor = input.get("Extractor")
    if not isinstance(extractor, dict):
        raise NonRetryableTransformError(
            "Expected an 'Extractor' dependency in input — is this transform's "
            "`input:` field wired to the Extractor step in the pipeline YAML?"
        )

    raw = extractor.get("response")
    if not isinstance(raw, str):
        raise NonRetryableTransformError(
            "Extractor artifact has no string 'response' field"
        )

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
    except json.JSONDecodeError as e:
        raise NonRetryableTransformError(
            f"Extractor response is not valid JSON: {e}"
        ) from e

    if not isinstance(parsed, dict):
        raise NonRetryableTransformError(
            "Extractor response must decode to a JSON object"
        )

    return parsed
