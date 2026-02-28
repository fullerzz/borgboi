import socket
from collections.abc import Generator, Iterable
from typing import Protocol

from borgboi.clients.utils.borg_logs import (
    ArchiveProgress,
    FileStatus,
    LogMessage,
    ProgressMessage,
    ProgressPercent,
    parse_borg_log_line,
    parse_borg_log_stream,
)
from borgboi.config import config
from borgboi.models import BorgBoiRepo


class HasHostname(Protocol):
    """Protocol for objects with a hostname attribute."""

    hostname: str


def metadata_is_present(repo: BorgBoiRepo) -> bool:
    return repo.metadata is not None


def repo_is_local(repo: HasHostname) -> bool:
    return repo.hostname == socket.gethostname()


def exclude_list_created(repo_name: str) -> bool:
    exclude_file = config.borgboi_dir / f"{repo_name}_{config.excludes_filename}"
    return exclude_file.exists()


def parse_log(log: str) -> ArchiveProgress | ProgressMessage | ProgressPercent | LogMessage | FileStatus:
    """
    Parse the log message from the borg client

    Args:
        log (str): single line output from the borg client

    Returns:
        ArchiveProgress | ProgressMessage | ProgressPercent | LogMessage | FileStatus: validated log message
    """
    return parse_borg_log_line(log)


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
    yield from parse_borg_log_stream(log_stream)


def valid_line(lines: list[str], line_num: int) -> bool:
    """
    Check if the line number is valid for the given lines.

    Args:
        lines (list[str]): List of lines.
        line_num (int): Line number to check.

    Returns:
        bool: True if the line number is valid, False otherwise.
    """
    # line numbers start from 1 so 0 is invalid
    return 0 < line_num <= len(lines)
