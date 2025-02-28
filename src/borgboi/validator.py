import socket
from collections.abc import Generator, Iterable
from pathlib import Path

from pydantic import ValidationError

from borgboi.clients.dynamodb import BorgRepoTableItem
from borgboi.clients.utils.borg_logs import (
    ArchiveProgress,
    FileStatus,
    LogMessage,
    ProgressMessage,
    ProgressPercent,
)
from borgboi.models import BORGBOI_DIR_NAME, EXCLUDE_FILENAME, BorgBoiRepo


def metadata_is_present(repo: BorgBoiRepo) -> bool:
    return repo.metadata is not None


def repo_is_local(repo: BorgBoiRepo | BorgRepoTableItem) -> bool:
    return repo.hostname == socket.gethostname()


def exclude_list_created(repo_name: str) -> bool:
    exclude_file = Path.home() / BORGBOI_DIR_NAME / f"{repo_name}_{EXCLUDE_FILENAME}"
    return exclude_file.exists()


def parse_log(log: str) -> ArchiveProgress | ProgressMessage | ProgressPercent | LogMessage | FileStatus:
    """
    Parse the log message from the borg client

    Args:
        log (str): single line output from the borg client

    Returns:
        ArchiveProgress | ProgressMessage | ProgressPercent | LogMessage | FileStatus: validated log message
    """
    log_msg: ArchiveProgress | ProgressMessage | ProgressPercent | LogMessage | FileStatus
    try:
        log_msg = ArchiveProgress.model_validate_json(log)
    except ValidationError:
        try:
            log_msg = ProgressPercent.model_validate_json(log)
        except ValidationError:
            try:
                log_msg = ProgressMessage.model_validate_json(log)
            except ValidationError:
                log_msg = LogMessage.model_validate_json(log)
    return log_msg


def parse_logs(
    log_stream: Iterable[str],
) -> Generator[ArchiveProgress | ProgressMessage | ProgressPercent | LogMessage | FileStatus]:
    """
    Parse the logs from the borg client

    Args:
        log_stream (Iterable[str]): logs from the borg client

    Yields:
        Generator[ArchiveProgress | ProgressMessage | ProgressPercent | LogMessage | FileStatus]: validated log message
    """
    log_msg: ArchiveProgress | ProgressMessage | ProgressPercent | LogMessage | FileStatus
    for log in log_stream:
        try:
            log_msg = ArchiveProgress.model_validate_json(log)
        except ValidationError:
            try:
                log_msg = ProgressPercent.model_validate_json(log)
            except ValidationError:
                try:
                    log_msg = ProgressMessage.model_validate_json(log)
                except ValidationError:
                    log_msg = LogMessage.model_validate_json(log)
        yield log_msg
