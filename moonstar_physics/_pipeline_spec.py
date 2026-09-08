"""Minimal local stand-in for the (now-removed) Python `moonstar_executor`
package's `PipelineSpec`/`TransformSpec` — just enough YAML-shape parsing
(name/type/input->deps/config) for moonstar-physics's own use: validating
`pipelines/*.yaml`'s dependency graph in tests, and driving the local DAG
walk in `local_pipeline.py`. Not a general pipeline executor — moonstar-rs
owns that now; this only needs to read the shape of a YAML file.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass
class TransformSpec:
    name: str
    type: str
    input: str | list[str] | None = None
    config: dict[str, Any] = field(default_factory=dict)

    @property
    def deps(self) -> list[str]:
        if self.input is None:
            return []
        if isinstance(self.input, str):
            return [self.input]
        return list(self.input)


@dataclass
class PipelineSpec:
    name: str
    version: str = "1.0"
    description: str = ""
    transforms: list[TransformSpec] = field(default_factory=list)

    def by_name(self) -> dict[str, TransformSpec]:
        return {t.name: t for t in self.transforms}

    @classmethod
    def from_yaml_text(cls, text: str) -> PipelineSpec:
        data = yaml.safe_load(text) or {}
        pipeline = data.get("pipeline") or {}
        transforms = [
            TransformSpec(
                name=t["name"],
                type=t["type"],
                input=t.get("input"),
                config=t.get("config") or {},
            )
            for t in (data.get("transforms") or [])
        ]
        return cls(
            name=pipeline.get("name", ""),
            version=pipeline.get("version", "1.0"),
            description=pipeline.get("description", ""),
            transforms=transforms,
        )


def render_pipeline_yaml(pipeline_path: Any, models_path: Any) -> str:
    """Substitutes `{{MODEL_X}}` placeholders from models.json into a
    pipeline YAML's raw text. Shared by scripts and tests so there's one
    place that knows the placeholder convention."""
    import json
    from pathlib import Path

    models = json.loads(Path(models_path).read_text(encoding="utf-8"))
    text = Path(pipeline_path).read_text(encoding="utf-8")
    for key, model in models.items():
        text = text.replace("{{" + key + "}}", model)
    return text
