"""Helpers for estimating and persisting daily backup stage progress."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Protocol

from sqlalchemy import Engine

from borgboi.storage.db import BackupStageTimingRow, get_db_path, get_session_factory, init_db

logger = logging.getLogger(__name__)

DEFAULT_STAGE_DURATION_MS: dict[str, float] = {
    "create": 360_000.0,
    "prune": 60_000.0,
    "compact": 90_000.0,
    "sync": 180_000.0,
}
DEFAULT_UNKNOWN_STAGE_DURATION_MS = 60_000.0
REPO_STAGE_SAMPLE_LIMIT = 10
GLOBAL_STAGE_SAMPLE_LIMIT = 20


class DailyBackupProgressHistory(Protocol):
    """Interface for loading and storing stage timing history."""

    def get_stage_durations(self, repo_name: str, stage_ids: Iterable[str]) -> dict[str, float]:
        """Return predicted durations in milliseconds for the given stages."""

    def record_stage_timing(
        self,
        repo_name: str,
        stage_id: str,
        duration_ms: float,
        *,
        sync_enabled: bool,
        succeeded: bool,
    ) -> None:
        """Persist an observed stage duration."""


class SQLiteDailyBackupProgressHistory:
    """SQLite-backed stage timing history for TUI daily backup progress."""

    def __init__(self, db_path: Path | None = None, engine: Engine | None = None) -> None:
        self._owns_engine = engine is None
        self._engine = engine or init_db(db_path or get_db_path())
        self._session_factory = get_session_factory(self._engine)

    def close(self) -> None:
        """Dispose the owned engine when the history store is no longer needed."""
        if self._owns_engine:
            self._engine.dispose()

    def get_stage_durations(self, repo_name: str, stage_ids: Iterable[str]) -> dict[str, float]:
        """Return predicted stage durations for a repository."""
        stage_list = list(stage_ids)
        if not stage_list:
            return {}

        predictions: dict[str, float] = {}
        for stage_id in stage_list:
            predictions[stage_id] = self._predict_stage_duration(repo_name, stage_id)
        return predictions

    def record_stage_timing(
        self,
        repo_name: str,
        stage_id: str,
        duration_ms: float,
        *,
        sync_enabled: bool,
        succeeded: bool,
    ) -> None:
        """Persist a stage timing sample.

        Storage errors are intentionally downgraded to warnings so backup runs
        do not fail if local progress history cannot be updated.
        """
        if duration_ms <= 0:
            return

        with self._session_factory() as session:
            try:
                session.add(
                    BackupStageTimingRow(
                        repo_name=repo_name,
                        stage_id=stage_id,
                        sync_enabled=sync_enabled,
                        duration_ms=int(duration_ms),
                        succeeded=succeeded,
                        completed_at=datetime.now(UTC),
                    )
                )
                session.commit()
            except Exception:
                session.rollback()
                logger.warning("Failed to persist daily backup timing for %s/%s", repo_name, stage_id, exc_info=True)

    def _predict_stage_duration(self, repo_name: str, stage_id: str) -> float:
        repo_samples = self._load_recent_durations(
            stage_id=stage_id, repo_name=repo_name, limit=REPO_STAGE_SAMPLE_LIMIT
        )
        if repo_samples:
            return float(median(repo_samples))

        global_samples = self._load_recent_durations(stage_id=stage_id, repo_name=None, limit=GLOBAL_STAGE_SAMPLE_LIMIT)
        if global_samples:
            return float(median(global_samples))

        return DEFAULT_STAGE_DURATION_MS.get(stage_id, DEFAULT_UNKNOWN_STAGE_DURATION_MS)

    def _load_recent_durations(self, *, stage_id: str, repo_name: str | None, limit: int) -> list[int]:
        with self._session_factory() as session:
            query = session.query(BackupStageTimingRow.duration_ms).filter_by(stage_id=stage_id, succeeded=True)
            if repo_name is not None:
                query = query.filter_by(repo_name=repo_name)

            rows = query.order_by(BackupStageTimingRow.completed_at.desc()).limit(limit).all()

        durations = [row[0] for row in rows if row[0] is not None and row[0] > 0]
        return durations
