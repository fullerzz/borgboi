"""Shared repository workspace state helpers for the TUI."""

from __future__ import annotations

import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class RepoWorkspaceRecord(Protocol):
    """Repository fields needed to resolve local workspace availability."""

    path: str
    hostname: str


@dataclass(frozen=True, slots=True)
class RepoWorkspaceState:
    """Workspace browsing state for a repository."""

    path: Path
    status: str
    detail: str
    can_browse: bool


def load_repo_workspace_state(repo: RepoWorkspaceRecord) -> RepoWorkspaceState:
    """Resolve whether the selected repository workspace can be browsed locally."""
    repo_path = Path(repo.path)
    current_hostname = socket.gethostname()

    if repo.hostname != current_hostname:
        return RepoWorkspaceState(
            path=repo_path,
            status="Workspace tree unavailable.",
            detail=(
                "Workspace tree is only available for repositories on this machine. "
                f"Selected host: {repo.hostname}. Current host: {current_hostname}."
            ),
            can_browse=False,
        )

    if not repo_path.exists():
        return RepoWorkspaceState(
            path=repo_path,
            status="Workspace tree unavailable.",
            detail="Repository path is not available on this machine.",
            can_browse=False,
        )

    if not repo_path.is_dir():
        return RepoWorkspaceState(
            path=repo_path,
            status="Workspace tree unavailable.",
            detail="Repository path exists on this machine but is not a directory.",
            can_browse=False,
        )

    return RepoWorkspaceState(
        path=repo_path,
        status="Browsing local repository workspace.",
        detail="Browsing local repository workspace.",
        can_browse=True,
    )
