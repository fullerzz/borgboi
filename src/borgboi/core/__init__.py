"""Core domain layer for BorgBoi.

This module contains the core models, error types, and orchestration logic
for the BorgBoi backup system.
"""

from typing import TYPE_CHECKING

from borgboi.core.errors import (
    BorgBoiError,
    BorgError,
    BorgExitCode,
    ConfigurationError,
    RepositoryNotFoundError,
    StorageError,
    ValidationError,
)
from borgboi.core.models import (
    BackupOptions,
    Repository,
    RestoreOptions,
    RetentionPolicy,
)
from borgboi.core.output import (
    CollectingOutputHandler,
    DefaultOutputHandler,
    OutputHandler,
    SilentOutputHandler,
)

if TYPE_CHECKING:
    from borgboi.core.orchestrator import Orchestrator
    from borgboi.core.validator import Validator


def __getattr__(name: str) -> object:
    """Lazy import for classes that may cause circular imports."""
    if name == "Orchestrator":
        from borgboi.core.orchestrator import Orchestrator

        return Orchestrator
    if name == "Validator":
        from borgboi.core.validator import Validator

        return Validator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BackupOptions",
    "BorgBoiError",
    "BorgError",
    "BorgExitCode",
    "CollectingOutputHandler",
    "ConfigurationError",
    "DefaultOutputHandler",
    "Orchestrator",
    "OutputHandler",
    "Repository",
    "RepositoryNotFoundError",
    "RestoreOptions",
    "RetentionPolicy",
    "SilentOutputHandler",
    "StorageError",
    "ValidationError",
    "Validator",
]
