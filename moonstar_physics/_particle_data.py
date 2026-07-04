"""Loads the bundled particle reference dataset (moonstar_physics/data/particles.json).

No network calls — this is a curated static subset of standard particle
properties, not a live lookup against an external database.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA_PATH = Path(__file__).parent / "data" / "particles.json"


class ParticleNotFound(KeyError):
    """Raised internally when a particle name isn't in the bundled dataset."""


@lru_cache(maxsize=1)
def load_particle_data() -> dict[str, Any]:
    with open(_DATA_PATH, encoding="utf-8") as f:
        return json.load(f)
