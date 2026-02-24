from collections.abc import Generator, Iterable
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, TypeAdapter, ValidationError


class ArchiveProgress(BaseModel):
    original_size: int | None = None
    compressed_size: int | None = None
    deduplicated_size: int | None = None
    nfiles: int | None = None
    path: str | None = None
    time: datetime
    finished: bool


class ProgressMessage(BaseModel):
    operation: int
    msgid: str | None
    finished: bool
    message: str | None = None
    time: datetime


class ProgressPercent(BaseModel):
    operation: int
    msgid: str | None
    finished: bool
    message: str | None = None
    current: int | None = None
    info: list[str] | None = None
    total: int | None = None
    time: datetime


class FileStatus(BaseModel):
    status: str
    path: str


class LogMessage(BaseModel):
    time: datetime
    levelname: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    name: str
    message: str
    msgid: str | None = None


type BorgLogEvent = ArchiveProgress | ProgressMessage | ProgressPercent | LogMessage | FileStatus

_JSON_OBJECT_ADAPTER = TypeAdapter(dict[str, Any])


def _parse_by_type(payload: dict[str, Any]) -> BorgLogEvent | None:
    event_type = payload.get("type")
    if event_type == "archive_progress":
        return ArchiveProgress.model_validate(payload)
    if event_type == "progress_message":
        if "current" in payload or "total" in payload:
            return ProgressPercent.model_validate(payload)
        return ProgressMessage.model_validate(payload)
    if event_type == "progress_percent":
        return ProgressPercent.model_validate(payload)
    if event_type == "file_status":
        return FileStatus.model_validate(payload)
    if event_type == "log_message":
        return LogMessage.model_validate(payload)
    return None


def _parse_by_shape(payload: dict[str, Any]) -> BorgLogEvent:
    try:
        return ArchiveProgress.model_validate(payload)
    except ValidationError:
        try:
            return ProgressPercent.model_validate(payload)
        except ValidationError:
            try:
                return ProgressMessage.model_validate(payload)
            except ValidationError:
                try:
                    return FileStatus.model_validate(payload)
                except ValidationError:
                    return LogMessage.model_validate(payload)


def parse_borg_log_line(log_line: str) -> BorgLogEvent:
    """Parse a Borg JSON log line into a strongly typed event model."""
    payload = _JSON_OBJECT_ADAPTER.validate_json(log_line)
    parsed_by_type = _parse_by_type(payload)
    if parsed_by_type is not None:
        return parsed_by_type
    return _parse_by_shape(payload)


def parse_borg_log_stream(log_stream: Iterable[str]) -> Generator[BorgLogEvent]:
    """Parse a stream of Borg JSON log lines into strongly typed events."""
    for log_line in log_stream:
        yield parse_borg_log_line(log_line)
