import os
import tempfile
from functools import cache
from pathlib import Path

from pydantic import BaseModel

from borgboi.core.logging import get_logger

# Trash spec: https://specifications.freedesktop.org/trash-spec/1.0/

TRASH_PATH: Path = Path.home() / ".Trash"
logger = get_logger(__name__)


class TrashError(Exception):
    pass


class Trash(BaseModel):
    path: Path
    files: Path
    info: Path


@cache
def get_trash() -> Trash:
    """Get the path to the trash directory."""
    logger.debug("Ensuring trash directories exist", trash_path=str(TRASH_PATH))
    trash = Trash(path=TRASH_PATH, files=TRASH_PATH / "files", info=TRASH_PATH / "info")
    if not trash.path.exists():
        trash.path.mkdir(parents=True, exist_ok=True)
    if not trash.files.exists():
        trash.files.mkdir(parents=True, exist_ok=True)
    if not trash.info.exists():
        trash.info.mkdir(parents=True, exist_ok=True)
    logger.debug("Trash directories ready", trash_path=str(trash.path))
    return trash


def _create_trashinfo_file(trash_file: Path) -> bool:
    trash: Trash = get_trash()
    info_file = trash.info / f"{trash_file.name}.trashinfo"
    logger.debug("Creating trash info file", file_path=str(trash_file), info_file=str(info_file))
    with tempfile.NamedTemporaryFile(delete=False) as f:
        _ = f.write(b"[Trash Info]\n")
        _ = f.write(f"Path={trash_file.resolve()}\n".encode())
        _ = f.write(f"DeletionDate={trash_file.stat().st_ctime}\n".encode())
        # make sure that all data is on disk
        # see http://stackoverflow.com/questions/7433057/is-rename-without-fsync-safe
        f.flush()
        os.fsync(f.fileno())

        os.replace(f.file.name, info_file.as_posix())  # noqa: PTH105
    created = info_file.exists(follow_symlinks=False)
    logger.debug("Created trash info file", file_path=str(trash_file), info_file=str(info_file), created=created)
    return created


def _move_to_files(trash_file: Path) -> bool:
    """
    Move a file to the $trash/files directory.
    """
    trash: Trash = get_trash()
    trash_path = trash.files / trash_file.name
    if trash_path.exists():
        logger.warning("File already exists in trash", file_path=str(trash_file), trash_path=str(trash_path))
        raise FileExistsError(f"File {trash_path} already exists in trash.")
    logger.debug("Moving file into trash", file_path=str(trash_file), trash_path=str(trash_path))
    trash_file = trash_file.rename(trash_path)
    moved = trash_path.exists(follow_symlinks=False)
    logger.debug("Moved file into trash", file_path=str(trash_file), trash_path=str(trash_path), moved=moved)
    return moved


def trash_file(file_path: Path) -> None:
    """
    Move a file to the trash.
    """
    if not file_path.exists():
        logger.warning("Cannot move missing file to trash", file_path=str(file_path))
        raise FileNotFoundError(f"File {file_path} does not exist.")
    src_file_path = file_path.as_posix()
    logger.info("Moving file to trash", file_path=str(file_path))

    try:
        # Create .trashinfo file first
        trashinfo_created = _create_trashinfo_file(file_path)
        if not trashinfo_created:
            raise RuntimeError(f"Failed to create trash info for {file_path}")

        # Move the file to the trash
        file_moved_to_trash = _move_to_files(file_path)
        if not file_moved_to_trash:
            raise RuntimeError(f"Failed to move {file_path} to trash.")

        # Verify that the file was moved to the trash
        if Path(src_file_path).exists():
            raise RuntimeError(f"Failed to delete {file_path} after moving to trash.")

    except Exception as e:
        logger.error("Failed to move file to trash", file_path=str(file_path), error=str(e))
        raise TrashError(f"An error occurred while moving {file_path} to trash: {e}") from e

    logger.info("File moved to trash", file_path=str(file_path))
    return None
