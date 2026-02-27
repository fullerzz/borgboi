from collections.abc import Generator, Iterable
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter, ValidationError


class ArchiveProgress(BaseModel):
    type: Literal["archive_progress"] = "archive_progress"
    original_size: int | None = None
    compressed_size: int | None = None
    deduplicated_size: int | None = None
    nfiles: int | None = None
    path: str | None = None
    time: datetime
    finished: bool


class ProgressMessage(BaseModel):
    type: Literal["progress_message"] = "progress_message"
    operation: int
    msgid: str | None
    finished: bool
    message: str | None = None
    time: datetime


class ProgressPercent(BaseModel):
    type: Literal["progress_percent"] = "progress_percent"
    operation: int
    msgid: str | None
    finished: bool
    message: str | None = None
    current: int | None = None
    info: list[str] | None = None
    total: int | None = None
    time: datetime


class FileStatus(BaseModel):
    type: Literal["file_status"] = "file_status"
    status: str
    path: str


class LogMessage(BaseModel):
    type: Literal["log_message"] = "log_message"
    time: datetime
    levelname: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    name: str
    message: str
    msgid: str | None = None


BorgLogEvent = Annotated[
    ArchiveProgress | ProgressMessage | ProgressPercent | LogMessage | FileStatus,
    Field(discriminator="type"),
]

_JSON_OBJECT_ADAPTER = TypeAdapter(dict[str, Any])
_TYPED_EVENT_ADAPTER: TypeAdapter[ArchiveProgress | ProgressMessage | ProgressPercent | LogMessage | FileStatus] = (
    TypeAdapter(BorgLogEvent)
)


def _is_unknown_union_tag_error(exc: ValidationError) -> bool:
    return any(error.get("type") == "union_tag_invalid" for error in exc.errors())


def _normalize_payload_type(payload: dict[str, Any]) -> None:
    """Borg sends type=progress_message for payloads that are semantically ProgressPercent."""
    if payload.get("type") == "progress_message" and ("current" in payload or "total" in payload):
        payload["type"] = "progress_percent"


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
    if "type" in payload:
        _normalize_payload_type(payload)
        try:
            return _TYPED_EVENT_ADAPTER.validate_python(payload)
        except ValidationError as exc:
            if _is_unknown_union_tag_error(exc):
                payload_without_type = {key: value for key, value in payload.items() if key != "type"}
                return _parse_by_shape(payload_without_type)
            raise
    return _parse_by_shape(payload)


def parse_borg_log_stream(log_stream: Iterable[str]) -> Generator[BorgLogEvent]:
    """Parse a stream of Borg JSON log lines into strongly typed events."""
    for log_line in log_stream:
        yield parse_borg_log_line(log_line)
