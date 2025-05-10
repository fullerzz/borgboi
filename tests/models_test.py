from platform import system

import pytest

from borgboi.models import BorgBoiRepo


@pytest.fixture
def borg_repo_linux() -> BorgBoiRepo:
    """Fixture for a Linux based Borg repository."""
    return BorgBoiRepo(
        path="/home/zach/borg-repos/repo",
        backup_target="/home/zach/Documents",
        name="docs-repo",
        hostname="ubuntu-desktop",
        os_platform="Linux",
        metadata=None,
    )


@pytest.fixture
def borg_repo_mac() -> BorgBoiRepo:
    """Fixture for a Mac based Borg repository."""
    return BorgBoiRepo(
        path="/Users/zachfuller/borg-repos/repo",
        backup_target="/Users/zachfuller/Pictures",
        name="pictures-repo",
        hostname="zach-macbook",
        os_platform="Darwin",
        metadata=None,
    )


@pytest.mark.skipif(system() == "Linux", reason="Test only runs on non-Linux systems")
def test_safe_path_convert_linux_repo(borg_repo_linux: BorgBoiRepo) -> None:
    assert borg_repo_linux.safe_path.startswith("/Users/")
    expected_path_parts = ["Users", "$USER", "borg-repos", "repo"]
    safe_path_parts = borg_repo_linux.safe_path.split("/")
    assert len(safe_path_parts) == len(expected_path_parts)
    for part in range(len(expected_path_parts)):
        if expected_path_parts[part] == "$USER":
            continue
        assert safe_path_parts[part] == expected_path_parts[part]


@pytest.mark.skipif(system() == "Darwin", reason="Test only runs on non-Mac systems")
def test_safe_path_convert_mac_repo(borg_repo_mac: BorgBoiRepo) -> None:
    assert borg_repo_mac.safe_path.startswith("/home/")
    expected_path_parts = ["home", "$USER", "borg-repos", "repo"]
    safe_path_parts = borg_repo_mac.safe_path.split("/")
    assert len(safe_path_parts) == len(expected_path_parts)
    for part in range(len(expected_path_parts)):
        if expected_path_parts[part] == "$USER":
            continue
        assert safe_path_parts[part] == expected_path_parts[part]
