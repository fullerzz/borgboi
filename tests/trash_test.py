from pathlib import Path

import pytest

from borgboi.clients.utils import trash


@pytest.fixture
def tmp_trash(tmp_path: Path) -> Path:
    """
    Fixture to create a temporary trash directory for testing.
    """
    trash_path = tmp_path / "trash"
    trash_path.mkdir(parents=True, exist_ok=False)
    return trash_path


def test_get_trash_creates_directories(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Patch TRASH_PATH to a temp dir
    tmp_trash = tmp_path / "trash"
    monkeypatch.setattr(trash, "TRASH_PATH", tmp_trash)
    # Clear cache so get_trash uses new path
    trash.get_trash.cache_clear()
    t = trash.get_trash()
    assert t.path.exists()
    assert t.files.exists()
    assert t.info.exists()


def test_trash_file_moves_and_creates_info(tmp_trash: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(trash, "TRASH_PATH", tmp_trash)
    trash.get_trash.cache_clear()
    # Create a temp file
    file = tmp_trash / "testfile.txt"
    _ = file.write_text("hello")
    trash.trash_file(file)
    # File should be gone from original location
    assert not file.exists()
    # File should be in trash/files
    trashed = tmp_trash / "files" / "testfile.txt"
    assert trashed.exists()
    # Info file should exist
    info = tmp_trash / "info" / "testfile.txt.trashinfo"
    assert info.exists()
    # Info file should contain [Trash Info]
    assert "[Trash Info]" in info.read_text()


def test_trash_file_nonexistent(tmp_trash: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(trash, "TRASH_PATH", tmp_trash)
    trash.get_trash.cache_clear()
    file = tmp_trash / "doesnotexist.txt"
    with pytest.raises(FileNotFoundError):
        trash.trash_file(file)


def test_trash_file_already_in_trash(tmp_trash: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(trash, "TRASH_PATH", tmp_trash)
    trash.get_trash.cache_clear()
    file = tmp_trash / "dupe.txt"
    _ = file.write_text("hi")
    trash.trash_file(file)
    # Try to trash again (file no longer at original location)
    with pytest.raises((trash.TrashError, FileNotFoundError)):
        trash.trash_file(file)
    # Try to trash a file with same name
    file2 = tmp_trash / "dupe.txt"
    _ = file2.write_text("bye")
    with pytest.raises(trash.TrashError):
        trash.trash_file(file2)
