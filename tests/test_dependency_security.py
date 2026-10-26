"""Keep the real install metadata and classic lock behavior security-pinned."""

from importlib.metadata import metadata, version
from pathlib import Path

from combo_lock import ComboLock
from packaging.requirements import Requirement


def test_wheel_metadata_keeps_exact_filelock_pin() -> None:
    """Installed distribution metadata must constrain the actual runtime graph."""
    requirements = [
        Requirement(value)
        for value in metadata("hivemind-core").get_all("Requires-Dist", [])
    ]
    selected = [item for item in requirements if item.name == "filelock"]
    assert len(selected) == 1
    assert str(selected[0].specifier) == "==3.20.3"
    assert selected[0].marker is None
    assert all(item.url is None for item in requirements)
    assert version("filelock") == "3.20.3"


def test_combo_lock_excludes_other_instances_and_releases(tmp_path: Path) -> None:
    """The selected filelock must preserve the API used by transitive consumers."""
    held = ComboLock(tmp_path / "dependency.lock")
    contender = ComboLock(tmp_path / "dependency.lock")
    with held:
        assert contender.acquire(blocking=False) is False
    assert contender.acquire(blocking=False) is True
    contender.release()


def test_legacy_client_api_support_is_explicit() -> None:
    """The legacy fork must reject the manager that removed its Client API."""
    requirements = [
        Requirement(value)
        for value in metadata("hivemind-core").get_all("Requires-Dist", [])
    ]
    selected = next(item for item in requirements if item.name == "hivemind-plugin-manager")
    assert selected.specifier.contains("0.8.0a1", prereleases=True)
    assert selected.specifier.contains("0.8.0a3", prereleases=True)
    assert not selected.specifier.contains("0.9.0a1", prereleases=True)
    assert not selected.specifier.contains("0.10.0a1", prereleases=True)

