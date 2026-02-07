"""Tests for SQLiteConfigBackend."""

from pathlib import Path

import pytest

from borgboi.config import Config
from borgboi.storage.db import init_db
from borgboi.storage.sqlite_config import SQLiteConfigBackend


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_config.db"


@pytest.fixture
def backend(db_path: Path) -> SQLiteConfigBackend:
    engine = init_db(db_path)
    return SQLiteConfigBackend(db_path, engine=engine)


class TestSQLiteConfigBackend:
    def test_load_empty_db_returns_defaults(
        self, backend: SQLiteConfigBackend, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Clear env vars set by autouse fixture so we get true defaults
        monkeypatch.delenv("BORGBOI_AWS__S3_BUCKET", raising=False)
        monkeypatch.delenv("BORGBOI_AWS__DYNAMODB_REPOS_TABLE", raising=False)
        monkeypatch.delenv("BORGBOI_AWS__DYNAMODB_ARCHIVES_TABLE", raising=False)

        cfg = backend.load_config(validate=False)
        assert cfg.offline is False
        assert cfg.debug is False
        assert cfg.aws.s3_bucket == "bb-backups"
        assert cfg.borg.compression == "zstd,6"
        assert cfg.ui.theme == "catppuccin"

    def test_save_and_load_roundtrip(self, backend: SQLiteConfigBackend, monkeypatch: pytest.MonkeyPatch) -> None:
        # Clear env vars set by autouse fixture so saved values aren't overridden
        monkeypatch.delenv("BORGBOI_AWS__S3_BUCKET", raising=False)
        monkeypatch.delenv("BORGBOI_AWS__DYNAMODB_REPOS_TABLE", raising=False)
        monkeypatch.delenv("BORGBOI_AWS__DYNAMODB_ARCHIVES_TABLE", raising=False)

        cfg = Config(offline=True, debug=True)
        cfg.aws.s3_bucket = "custom-bucket"
        cfg.borg.compression = "lz4"
        cfg.borg.retention.keep_daily = 14
        cfg.ui.theme = "monokai"

        backend.save_config(cfg)
        loaded = backend.load_config(validate=False)

        assert loaded.offline is True
        assert loaded.debug is True
        assert loaded.aws.s3_bucket == "custom-bucket"
        assert loaded.borg.compression == "lz4"
        assert loaded.borg.retention.keep_daily == 14
        assert loaded.ui.theme == "monokai"

    def test_save_overwrites_previous(self, backend: SQLiteConfigBackend) -> None:
        cfg1 = Config(offline=True)
        backend.save_config(cfg1)

        cfg2 = Config(offline=False, debug=True)
        backend.save_config(cfg2)

        loaded = backend.load_config(validate=False)
        assert loaded.offline is False
        assert loaded.debug is True

    def test_env_override(self, backend: SQLiteConfigBackend, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BORGBOI_OFFLINE", "true")
        monkeypatch.setenv("BORGBOI_AWS__S3_BUCKET", "env-bucket")
        monkeypatch.setenv("BORGBOI_BORG__RETENTION__KEEP_DAILY", "30")

        cfg = backend.load_config(validate=False)
        assert cfg.offline is True
        assert cfg.aws.s3_bucket == "env-bucket"
        assert cfg.borg.retention.keep_daily == 30

    def test_env_override_takes_precedence_over_db(
        self, backend: SQLiteConfigBackend, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cfg = Config()
        cfg.aws.s3_bucket = "db-bucket"
        backend.save_config(cfg)

        monkeypatch.setenv("BORGBOI_AWS__S3_BUCKET", "env-bucket")
        loaded = backend.load_config(validate=False)
        assert loaded.aws.s3_bucket == "env-bucket"
