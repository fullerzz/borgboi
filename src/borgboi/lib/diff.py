"""Shared helpers for formatting and summarising archive diff results."""

from __future__ import annotations

from borgboi.clients.borg import DiffChange, DiffResult
from borgboi.lib.utils import format_size_bytes


def summarize_diff_changes(result: DiffResult) -> dict[str, int]:
    """Summarize archive diff changes into category counts and byte totals."""
    summary = {
        "added": 0,
        "removed": 0,
        "modified": 0,
        "mode": 0,
        "bytes_added": 0,
        "bytes_removed": 0,
    }

    for entry in result.entries:
        entry_categories = {change.type for change in entry.changes}
        if "added" in entry_categories:
            summary["added"] += 1
        if "removed" in entry_categories:
            summary["removed"] += 1
        if "modified" in entry_categories:
            summary["modified"] += 1
        if "mode" in entry_categories:
            summary["mode"] += 1

        for change in entry.changes:
            added_bytes = change.added or 0
            removed_bytes = change.removed or 0
            if change.type == "added":
                summary["bytes_added"] += added_bytes or change.size or 0
            elif change.type == "removed":
                summary["bytes_removed"] += removed_bytes or change.size or 0
            elif change.type == "modified":
                summary["bytes_added"] += added_bytes
                summary["bytes_removed"] += removed_bytes

    return summary


def format_diff_change(change: DiffChange) -> str:
    """Render a single diff change into compact human-readable text."""
    match change.type:
        case "added":
            return f"added ({format_size_bytes(change.added or change.size or 0)})"
        case "removed":
            return f"removed ({format_size_bytes(change.removed or change.size or 0)})"
        case "modified":
            added = format_size_bytes(change.added or 0)
            removed = format_size_bytes(change.removed or 0)
            return f"modified (+{added}, -{removed})"
        case "mode":
            return f"mode {change.old_mode or '?'} -> {change.new_mode or '?'}"
        case _ if change.old is not None or change.new is not None:
            return f"{change.type} {change.old if change.old is not None else '?'} -> {change.new if change.new is not None else '?'}"
        case _:
            return change.type
