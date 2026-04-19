from __future__ import annotations

from borgboi.clients.borg import DiffResult
from borgboi.lib.diff import filter_diff_result, resolve_entry_kind


def _sample_result() -> DiffResult:
    return DiffResult.model_validate(
        {
            "archive1": "older",
            "archive2": "newer",
            "entries": [
                {"path": "added.txt", "changes": [{"type": "added", "size": 10}]},
                {"path": "removed.txt", "changes": [{"type": "removed", "size": 5}]},
                {"path": "docs/file.txt", "changes": [{"type": "modified", "added": 3, "removed": 1}]},
                {
                    "path": "docs/Mode.txt",
                    "changes": [{"type": "mode", "old_mode": "-rw-r--r--", "new_mode": "-rwxr-xr-x"}],
                },
            ],
        }
    )


def test_resolve_entry_kind_classifies_each_change_category() -> None:
    result = _sample_result()

    kinds = {entry.path.as_posix(): resolve_entry_kind(entry) for entry in result.entries}

    assert kinds == {
        "added.txt": "added",
        "removed.txt": "removed",
        "docs/file.txt": "modified",
        "docs/Mode.txt": "mode",
    }


def test_filter_diff_result_defaults_preserve_every_entry() -> None:
    result = _sample_result()

    filtered = filter_diff_result(result)

    assert [entry.path.as_posix() for entry in filtered.entries] == [entry.path.as_posix() for entry in result.entries]
    assert filtered.archive1 == result.archive1
    assert filtered.archive2 == result.archive2


def test_filter_diff_result_kinds_drop_excluded_entries() -> None:
    result = _sample_result()

    filtered = filter_diff_result(result, kinds={"added", "modified"})

    assert [entry.path.as_posix() for entry in filtered.entries] == ["added.txt", "docs/file.txt"]


def test_filter_diff_result_empty_kinds_yields_no_entries() -> None:
    result = _sample_result()

    filtered = filter_diff_result(result, kinds=set())

    assert filtered.entries == []


def test_filter_diff_result_substring_matches_case_insensitively_on_posix_path() -> None:
    result = _sample_result()

    filtered = filter_diff_result(result, substring="DOCS")

    assert [entry.path.as_posix() for entry in filtered.entries] == ["docs/file.txt", "docs/Mode.txt"]


def test_filter_diff_result_substring_and_kinds_compose() -> None:
    result = _sample_result()

    filtered = filter_diff_result(result, kinds={"mode"}, substring="docs")

    assert [entry.path.as_posix() for entry in filtered.entries] == ["docs/Mode.txt"]


def test_filter_diff_result_blank_substring_is_ignored() -> None:
    result = _sample_result()

    filtered = filter_diff_result(result, substring="   ")

    assert len(filtered.entries) == len(result.entries)
