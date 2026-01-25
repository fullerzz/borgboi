"""Custom error types for BorgBoi.

This module defines a hierarchy of exceptions used throughout BorgBoi
to provide clear, actionable error information.
"""

from enum import IntEnum
from typing import override


class BorgExitCode(IntEnum):
    """Borg backup exit codes.

    Borg uses specific exit codes to indicate the result of an operation:
    - 0: Success - Operation completed without any issues
    - 1: Warning - Operation completed but with warnings (e.g., permission denied for some files)
    - 2: Error - Operation failed

    References:
        https://borgbackup.readthedocs.io/en/stable/usage/general.html#return-codes
    """

    SUCCESS = 0
    WARNING = 1
    ERROR = 2


class BorgBoiError(Exception):
    """Base exception for all BorgBoi errors."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class BorgError(BorgBoiError):
    """Exception raised when a Borg command fails.

    Attributes:
        exit_code: The exit code returned by Borg
        command: The command that was executed
        stdout: Standard output from the command
        stderr: Standard error output from the command
    """

    def __init__(
        self,
        message: str,
        exit_code: int,
        command: list[str] | None = None,
        stdout: str | None = None,
        stderr: str | None = None,
    ) -> None:
        super().__init__(message)
        self._exit_code = BorgExitCode(exit_code) if exit_code in BorgExitCode.__members__.values() else exit_code
        self.command = command or []
        self.stdout = stdout or ""
        self.stderr = stderr or ""

    @property
    def exit_code(self) -> int:
        """Get the exit code as an integer."""
        return int(self._exit_code) if isinstance(self._exit_code, BorgExitCode) else self._exit_code

    @property
    def exit_code_enum(self) -> BorgExitCode | None:
        """Get the exit code as a BorgExitCode enum, if valid."""
        return self._exit_code if isinstance(self._exit_code, BorgExitCode) else None

    @property
    def is_warning(self) -> bool:
        """Check if the exit code indicates a warning (non-fatal)."""
        return self._exit_code == BorgExitCode.WARNING

    @property
    def is_fatal(self) -> bool:
        """Check if the exit code indicates a fatal error."""
        return self._exit_code == BorgExitCode.ERROR or (
            isinstance(self._exit_code, int) and self._exit_code not in (0, 1)
        )

    @property
    def is_success(self) -> bool:
        """Check if the exit code indicates success."""
        return self._exit_code == BorgExitCode.SUCCESS

    @override
    def __str__(self) -> str:
        parts = [self.message]
        if self.command:
            parts.append(f"Command: {' '.join(self.command)}")
        if self.stderr:
            parts.append(f"Stderr: {self.stderr}")
        return "\n".join(parts)


class StorageError(BorgBoiError):
    """Exception raised when storage operations fail.

    This includes errors from DynamoDB, offline storage, and file I/O operations.
    """

    def __init__(self, message: str, operation: str | None = None, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.operation = operation
        self.cause = cause

    @override
    def __str__(self) -> str:
        parts = [self.message]
        if self.operation:
            parts.append(f"Operation: {self.operation}")
        if self.cause:
            parts.append(f"Caused by: {self.cause}")
        return "\n".join(parts)


class ValidationError(BorgBoiError):
    """Exception raised when validation fails.

    Attributes:
        field: The field that failed validation (if applicable)
        value: The invalid value (if applicable)
    """

    def __init__(self, message: str, field: str | None = None, value: str | None = None) -> None:
        super().__init__(message)
        self.field = field
        self.value = value

    @override
    def __str__(self) -> str:
        parts = [self.message]
        if self.field:
            parts.append(f"Field: {self.field}")
        if self.value:
            parts.append(f"Value: {self.value}")
        return "\n".join(parts)


class ConfigurationError(BorgBoiError):
    """Exception raised when configuration is invalid or missing."""

    def __init__(self, message: str, config_key: str | None = None) -> None:
        super().__init__(message)
        self.config_key = config_key


class RepositoryNotFoundError(BorgBoiError):
    """Exception raised when a repository cannot be found.

    Attributes:
        name: The repository name that was searched for
        path: The repository path that was searched for
    """

    def __init__(self, message: str, name: str | None = None, path: str | None = None) -> None:
        super().__init__(message)
        self.name = name
        self.path = path

    @override
    def __str__(self) -> str:
        parts = [self.message]
        if self.name:
            parts.append(f"Name: {self.name}")
        if self.path:
            parts.append(f"Path: {self.path}")
        return "\n".join(parts)
