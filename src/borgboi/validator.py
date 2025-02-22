import socket
from pathlib import Path

from pydantic import ValidationError

from borgboi.backups import BORGBOI_DIR_NAME, EXCLUDE_FILENAME, BorgRepo
from borgboi.clients.utils.borg_logs import (
    ArchiveProgress,
    FileStatus,
    LogMessage,
    ProgressMessage,
    ProgressPercent,
)


def repo_is_local(repo: BorgRepo) -> bool:
    return repo.hostname == socket.gethostname()


def exclude_list_created(repo_name: str) -> bool:
    exclude_file = Path.home() / BORGBOI_DIR_NAME / f"{repo_name}_{EXCLUDE_FILENAME}"
    return exclude_file.exists()


def parse_log(log: str) -> ArchiveProgress | ProgressMessage | ProgressPercent | LogMessage | FileStatus:
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
