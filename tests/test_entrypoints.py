"""Tests that the three custom transforms are discoverable via moonstar.transforms entrypoints."""
import asyncio

from moonstar_core.registry import ProviderRegistry


def test_conservation_law_check_transform_entrypoint():
    reg = ProviderRegistry()
    reg.load_installed()
    fn = reg.get("ConservationLawCheckTransform")
    assert fn is not None


def test_qm_calculation_transform_entrypoint():
    reg = ProviderRegistry()
    reg.load_installed()
    fn = reg.get("QMCalculationTransform")
    assert fn is not None


def test_reference_data_lookup_transform_entrypoint():
    reg = ProviderRegistry()
    reg.load_installed()
    fn = reg.get("ReferenceDataLookupTransform")
    assert fn is not None


def test_all_three_entrypoints_are_awaitable():
    reg = ProviderRegistry()
    reg.load_installed()
    for name in (
        "ConservationLawCheckTransform",
        "QMCalculationTransform",
        "ReferenceDataLookupTransform",
    ):
        assert asyncio.iscoroutinefunction(reg.get(name))
