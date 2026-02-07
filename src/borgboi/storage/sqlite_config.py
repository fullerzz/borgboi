"""SQLite-backed configuration backend for BorgBoi, replacing Dynaconf."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import Engine

from borgboi.storage.db import ConfigRow, get_session_factory, init_db

if TYPE_CHECKING:
    from borgboi.config import Config

logger = logging.getLogger(__name__)


class SQLiteConfigBackend:
    """Load and save BorgBoi configuration from/to a SQLite database."""

    def __init__(self, db_path: Path, engine: Engine | None = None) -> None:
        self._db_path = db_path
        self._engine = engine or init_db(db_path)
        self._session_factory = get_session_factory(self._engine)

    def load_config(self, validate: bool = True, print_warnings: bool = True) -> Config:
        """Load config from DB, apply env overrides, validate, return Config."""
        from borgboi.config import Config, validate_config

        raw = self._load_from_db()
        raw = self._apply_env_overrides(raw)
        cfg = Config.model_validate(raw)

        if validate:
            config_warnings = validate_config(cfg)
            if print_warnings and config_warnings:
                import sys

                for warning in config_warnings:
                    print(f"[CONFIG WARNING] {warning}", file=sys.stderr)  # noqa: T201

        return cfg

    def save_config(self, cfg: Config) -> None:
        """Persist a Config instance to the database."""
        config_dict = cfg.model_dump(exclude_none=True, mode="json")
        # Convert Path objects to strings for serialization
        if "borg" in config_dict and "default_repo_path" in config_dict["borg"]:
            config_dict["borg"]["default_repo_path"] = str(config_dict["borg"]["default_repo_path"])
        self._save_to_db(config_dict)

    def _load_from_db(self) -> dict[str, Any]:
        """Read all config rows and reconstruct as nested dict."""
        result: dict[str, Any] = {}
        with self._session_factory() as session:
            rows = session.query(ConfigRow).all()
            for row in rows:
                value = json.loads(row.value)
                if row.section == "top":
                    result[row.key] = value
                else:
                    # Handle nested sections like "aws", "borg", "borg.retention", "ui"
                    parts = row.section.split(".")
                    target: dict[str, Any] = result
                    for part in parts:
                        if part not in target:
                            target[part] = {}
                        target = target[part]
                    target[row.key] = value
        return result

    def _save_to_db(self, config_dict: dict[str, Any]) -> None:
        """Flatten nested config dict to rows and upsert into config table."""
        rows_to_upsert = self._flatten_config(config_dict)

        with self._session_factory() as session:
            try:
                # Delete all existing config rows and replace
                session.query(ConfigRow).delete()
                for section, key, value in rows_to_upsert:
                    session.add(ConfigRow(section=section, key=key, value=json.dumps(value)))
                session.commit()
            except Exception as e:
                session.rollback()
                raise RuntimeError(f"Failed to save config to database: {e}") from e

    def _flatten_config(self, data: dict[str, Any], section: str = "top") -> list[tuple[str, str, Any]]:
        """Flatten a nested dict into (section, key, value) tuples."""
        rows: list[tuple[str, str, Any]] = []
        for key, value in data.items():
            if isinstance(value, dict):
                child_section = key if section == "top" else f"{section}.{key}"
                rows.extend(self._flatten_config(value, child_section))
            else:
                rows.append((section, key, value))
        return rows

    def _apply_env_overrides(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Apply BORGBOI_* environment variable overrides to the raw config dict."""
        from borgboi.config import CONFIG_ENV_VAR_MAP

        for config_path, env_var in CONFIG_ENV_VAR_MAP.items():
            env_value = os.getenv(env_var)
            if env_value is None:
                continue

            # Coerce types
            coerced: object = self._coerce_env_value(env_value, config_path)

            # Set nested value
            parts = config_path.split(".")
            target: dict[str, Any] = raw
            for part in parts[:-1]:
                if part not in target:
                    target[part] = {}
                target = target[part]
            target[parts[-1]] = coerced

        return raw

    def _coerce_env_value(self, value: str, config_path: str) -> object:
        """Coerce a string env var value to the appropriate Python type."""
        lower = value.lower()

        # Bool coercion
        if lower in ("true", "1", "yes"):
            return True
        if lower in ("false", "0", "no"):
            return False

        # Int coercion for known int fields
        int_fields = {
            "borg.checkpoint_interval",
            "borg.retention.keep_daily",
            "borg.retention.keep_weekly",
            "borg.retention.keep_monthly",
            "borg.retention.keep_yearly",
        }
        if config_path in int_fields:
            try:
                return int(value)
            except ValueError:
                pass

        return value
