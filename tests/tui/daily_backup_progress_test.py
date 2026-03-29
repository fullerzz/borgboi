from __future__ import annotations

from pathlib import Path

from borgboi.tui.daily_backup_progress import DEFAULT_STAGE_DURATION_MS, SQLiteDailyBackupProgressHistory


def _make_history(tmp_path: Path) -> SQLiteDailyBackupProgressHistory:
    return SQLiteDailyBackupProgressHistory(db_path=tmp_path / "borgboi.db")


def test_stage_history_uses_defaults_when_no_samples_exist(tmp_path: Path) -> None:
    history = _make_history(tmp_path)

    try:
        predictions = history.get_stage_durations("alpha", ["create", "prune"])
    finally:
        history.close()

    assert predictions == {
        "create": DEFAULT_STAGE_DURATION_MS["create"],
        "prune": DEFAULT_STAGE_DURATION_MS["prune"],
    }


def test_stage_history_prefers_repo_specific_samples(tmp_path: Path) -> None:
    history = _make_history(tmp_path)

    try:
        history.record_stage_timing("beta", "create", 9_000.0, sync_enabled=False, succeeded=True)
        history.record_stage_timing("alpha", "create", 1_000.0, sync_enabled=False, succeeded=True)
        history.record_stage_timing("alpha", "create", 3_000.0, sync_enabled=True, succeeded=True)

        predictions = history.get_stage_durations("alpha", ["create"])
    finally:
        history.close()

    assert predictions["create"] == 2_000.0


def test_stage_history_falls_back_to_global_successful_samples(tmp_path: Path) -> None:
    history = _make_history(tmp_path)

    try:
        history.record_stage_timing("beta", "sync", 2_000.0, sync_enabled=True, succeeded=True)
        history.record_stage_timing("gamma", "sync", 8_000.0, sync_enabled=True, succeeded=False)
        history.record_stage_timing("delta", "sync", 6_000.0, sync_enabled=False, succeeded=True)

        predictions = history.get_stage_durations("alpha", ["sync"])
    finally:
        history.close()

    assert predictions["sync"] == 4_000.0
