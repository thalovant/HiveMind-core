"""The legacy in-process harness must expose real link credentials."""

from importlib.metadata import metadata, version
from types import SimpleNamespace

import pytest
from hivescope.node import InProcessHiveShim
from packaging.requirements import Requirement


def test_shim_password_forwards_identity_without_caching():
    identity = SimpleNamespace(password=object())
    shim = InProcessHiveShim(identity, satellite_ref=None)
    assert shim.password is identity.password
    identity.password = object()
    assert shim.password is identity.password
    assert not shim.handshake_event.is_set()


def test_shim_missing_credential_is_not_replaced():
    shim = InProcessHiveShim(SimpleNamespace(), satellite_ref=None)
    with pytest.raises(AttributeError):
        _ = shim.password
    assert not shim.handshake_event.is_set()


def test_test_extras_keep_the_legacy_harness_contract():
    requirements = [
        Requirement(value)
        for value in metadata("hivemind-core").get_all("Requires-Dist", [])
    ]
    harness = [item for item in requirements if item.name == "hivescope"]
    assert len(harness) == 2
    for requirement in harness:
        assert requirement.specifier.contains("0.6.6a1", prereleases=True)
        assert not requirement.specifier.contains("0.7.0a1", prereleases=True)
        assert not requirement.specifier.contains("0.8.8a1", prereleases=True)
        assert requirement.specifier.contains(version("hivescope"), prereleases=True)
    assert {str(item.marker) for item in harness} == {
        'extra == "test"', 'extra == "integration"',
    }
