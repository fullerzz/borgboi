"""Shared helpers for formatting and summarising archive diff results."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from borgboi.clients.borg import DiffChange, DiffEntry, DiffResult
from borgboi.lib.utils import format_size_bytes

DiffChangeKind = Literal["added", "removed", "modified", "mode"]
ALL_DIFF_KINDS: frozenset[DiffChangeKind] = frozenset({"added", "removed", "modified", "mode"})


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
            added_bytes = change.added if change.added is not None else 0
            removed_bytes = change.removed if change.removed is not None else 0
            if change.type == "added":
                summary["bytes_added"] += added_bytes if change.added is not None else (change.size or 0)
            elif change.type == "removed":
                summary["bytes_removed"] += removed_bytes if change.removed is not None else (change.size or 0)
            elif change.type == "modified":
                summary["bytes_added"] += added_bytes
                summary["bytes_removed"] += removed_bytes

    return summary


def format_diff_change(change: DiffChange) -> str:
    """Render a single diff change into compact human-readable text."""
    match change.type:
        case "added":
            size = change.added if change.added is not None else (change.size or 0)
            return f"added ({format_size_bytes(size)})"
        case "removed":
            size = change.removed if change.removed is not None else (change.size or 0)
            return f"removed ({format_size_bytes(size)})"
        case "modified":
            added = format_size_bytes(change.added if change.added is not None else 0)
            removed = format_size_bytes(change.removed if change.removed is not None else 0)
            return f"modified (+{added}, -{removed})"
        case "mode":
            return f"mode {change.old_mode or '?'} -> {change.new_mode or '?'}"
        case _ if change.old is not None or change.new is not None:
            return f"{change.type} {change.old if change.old is not None else '?'} -> {change.new if change.new is not None else '?'}"
        case _:
            return change.type


def resolve_entry_kind(entry: DiffEntry) -> DiffChangeKind:
    """Classify a diff entry as added, removed, modified, or mode-only."""
    types = {change.type for change in entry.changes}
    if types == {"added"}:
        return "added"
    if types == {"removed"}:
        return "removed"
    if types == {"mode"}:
        return "mode"
    return "modified"


def filter_diff_result(
    result: DiffResult,
    *,
    kinds: Iterable[DiffChangeKind] | None = None,
    substring: str = "",
) -> DiffResult:
    """Return a DiffResult filtered by change kind and path substring.

    - `kinds`: iterable of kinds to retain (empty iterable → no matches).
      `None` means retain all kinds.
    - `substring`: case-insensitive match against the entry path's POSIX form.
      Empty string matches everything.
    """
    allowed: frozenset[DiffChangeKind] | None = frozenset(kinds) if kinds is not None else None
    needle = substring.strip().lower()

    filtered: list[DiffEntry] = []
    for entry in result.entries:
        if allowed is not None and resolve_entry_kind(entry) not in allowed:
            continue
        if needle and needle not in entry.path.as_posix().lower():
            continue
        filtered.append(entry)

    return DiffResult(archive1=result.archive1, archive2=result.archive2, entries=filtered)
