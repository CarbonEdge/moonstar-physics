"""Tests that the four custom transforms' `moonstar.transforms` entrypoint
declarations in pyproject.toml resolve to real, awaitable callables.

Previously loaded through the Python `moonstar` gateway's
`moonstar_core.registry.ProviderRegistry` (`importlib.metadata`
entry_points()) — that gateway no longer exists in this workspace, and
these transforms now run locally rather than through any gateway registry
(see moonstar_physics/local_pipeline.py). This test keeps checking the one
thing that still matters: pyproject.toml's declared entry points actually
point at real, importable, awaitable functions, so the declaration doesn't
silently rot.
"""
import asyncio
from importlib.metadata import entry_points

_TRANSFORM_NAMES = (
    "ConservationLawCheckTransform",
    "QMCalculationTransform",
    "ReferenceDataLookupTransform",
    "DimensionConsistencyTransform",
    "IdentityCheckTransform",
    "ConjectureCheckTransform",
)


def _entry_points_for_group() -> dict[str, str]:
    eps = entry_points(group="moonstar.transforms")
    return {ep.name: ep.value for ep in eps}


def test_all_four_transforms_are_declared():
    declared = _entry_points_for_group()
    for name in _TRANSFORM_NAMES:
        assert name in declared, f"{name} missing from moonstar.transforms entry points"


def test_all_four_entrypoints_resolve_to_awaitable_callables():
    eps = entry_points(group="moonstar.transforms")
    for name in _TRANSFORM_NAMES:
        matches = [ep for ep in eps if ep.name == name]
        assert matches, f"{name} missing from moonstar.transforms entry points"
        fn = matches[0].load()
        assert asyncio.iscoroutinefunction(fn)
