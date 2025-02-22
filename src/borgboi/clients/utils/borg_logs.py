from datetime import datetime
from typing import Literal

from pydantic import BaseModel


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
