"""Shared repository quota display helpers for TUI screens."""

from __future__ import annotations


def effective_quota_display(
    *,
    quota_load_failed: bool,
    is_local_repo: bool,
    live_quota: str | None,
    config_default_quota: str | None,
) -> tuple[str, str]:
    """Return (quota_text, source_label) for the current repository quota state."""
    if quota_load_failed and is_local_repo and live_quota is None:
        return "Unknown", "Unavailable"
    if live_quota is not None:
        return live_quota, "Repository"
    if not is_local_repo:
        return "Unknown", "Unavailable"
    if config_default_quota is not None:
        return config_default_quota, "Default"
    return "Unknown", "Unknown"
