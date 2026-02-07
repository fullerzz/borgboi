"""Configuration management for borgboi using YAML and Pydantic."""

import os
import shutil
from functools import lru_cache
from pathlib import Path
from platform import system
from typing import Any

import yaml
from pydantic import BaseModel, Field

DEFAULT_DYNAMODB_REPOS_TABLE = "bb-repos"
DEFAULT_DYNAMODB_ARCHIVES_TABLE = "bb-archives"
DEFAULT_S3_BUCKET = "bb-backups"
DEFAULT_AWS_REGION = "us-west-1"
DEFAULT_REPO_STORAGE_QUOTA = "100G"
DEFAULT_REPO_COMPRESSION = "zstd,6"


class RetentionConfig(BaseModel):
    """Borg backup retention policy configuration."""

    keep_daily: int = 7
    keep_weekly: int = 4
    keep_monthly: int = 6
    keep_yearly: int = 0


class AWSConfig(BaseModel):
    """AWS service configuration."""

    dynamodb_repos_table: str = DEFAULT_DYNAMODB_REPOS_TABLE
    dynamodb_archives_table: str = DEFAULT_DYNAMODB_ARCHIVES_TABLE
    s3_bucket: str = DEFAULT_S3_BUCKET
    region: str = DEFAULT_AWS_REGION
    profile: str | None = None


class BorgConfig(BaseModel):
    """Borg-specific configuration."""

    executable_path: str = "borg"
    default_repo_path: Path = Field(default_factory=lambda: resolve_home_dir() / ".borgboi" / "repositories")
    compression: str = DEFAULT_REPO_COMPRESSION
    checkpoint_interval: int = 900  # seconds
    storage_quota: str = DEFAULT_REPO_STORAGE_QUOTA
    additional_free_space: str = "2G"
    retention: RetentionConfig = Field(default_factory=RetentionConfig)
    borg_passphrase: str | None = None
    borg_new_passphrase: str | None = None


class UIConfig(BaseModel):
    """UI/Display configuration."""

    theme: str = "catppuccin"
    show_progress: bool = True
    color_output: bool = True
    table_style: str = "rounded"


class Config(BaseModel):
    """Main configuration container."""

    aws: AWSConfig = Field(default_factory=AWSConfig)
    borg: BorgConfig = Field(default_factory=BorgConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    offline: bool = False
    debug: bool = False

    @property
    def borgboi_dir(self) -> Path:
        """Get the borgboi directory path."""
        return resolve_home_dir() / ".borgboi"

    @property
    def passphrases_dir(self) -> Path:
        """Get the passphrases directory path."""
        return self.borgboi_dir / "passphrases"

    @property
    def excludes_filename(self) -> str:
        """Get the excludes filename."""
        return "excludes.txt"


def resolve_home_dir() -> Path:
    """
    Resolve home directory with priority:
    1. BORGBOI_HOME environment variable
    2. SUDO_USER home directory (if running as sudo)
    3. Current user's home directory

    Returns:
        Path: Resolved home directory path
    """
    # Check BORGBOI_HOME first
    if borgboi_home := os.getenv("BORGBOI_HOME"):
        return Path(borgboi_home)

    # Check if running as sudo
    if sudo_user := os.getenv("SUDO_USER"):
        sudo_home = Path(f"/Users/{sudo_user}") if system() == "Darwin" else Path(f"/home/{sudo_user}")
        if sudo_home.exists():
            return sudo_home

    # Fall back to current user
    return Path.home()


def _create_settings_dir() -> Path:
    """Create and return the settings directory path."""
    settings_dir = resolve_home_dir() / ".borgboi"
    settings_dir.mkdir(parents=True, exist_ok=True)
    return settings_dir


def get_default_config_path() -> Path:
    """Return the default borgboi config file path."""
    return resolve_home_dir() / ".borgboi" / "config.yaml"


def _apply_env_overrides(raw: dict[str, Any]) -> dict[str, Any]:
    """Apply BORGBOI_* environment variable overrides to the raw config dict."""
    for config_path, env_var in CONFIG_ENV_VAR_MAP.items():
        env_value = os.getenv(env_var)
        if env_value is None:
            continue

        coerced: object = _coerce_env_value(env_value, config_path)

        parts = config_path.split(".")
        target: dict[str, Any] = raw
        for part in parts[:-1]:
            existing = target.get(part)
            if not isinstance(existing, dict):
                target[part] = {}
            target = target[part]
        target[parts[-1]] = coerced

    return raw


def _coerce_env_value(value: str, config_path: str) -> object:
    """Coerce a string env var value to the appropriate Python type."""
    lower = value.lower()

    if lower in ("true", "1", "yes"):
        return True
    if lower in ("false", "0", "no"):
        return False

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


def _write_default_config(config_path: Path) -> None:
    """Write a default config.yaml file."""
    cfg = Config()
    config_dict = cfg.model_dump(exclude_none=True, mode="json")
    if "borg" in config_dict and "default_repo_path" in config_dict["borg"]:
        config_dict["borg"]["default_repo_path"] = str(config_dict["borg"]["default_repo_path"])
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w") as f:
        yaml.safe_dump(config_dict, f, default_flow_style=False, sort_keys=False)


@lru_cache(maxsize=1)
def get_config(validate: bool = True, print_warnings: bool = True) -> Config:
    """Load and return validated configuration from YAML file.

    On first call, loads config from config.yaml with env var overrides.

    Note: This function uses lru_cache with maxsize=1, so the first call's
    validate and print_warnings parameters determine the cached behavior.

    Args:
        validate: Whether to run validation checks (default True)
        print_warnings: Whether to print validation warnings to stderr (default True)

    Returns:
        Config: Validated configuration instance
    """
    _create_settings_dir()
    config_path = get_default_config_path()

    if not config_path.exists():
        _write_default_config(config_path)

    with config_path.open() as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        data = {}

    data = _apply_env_overrides(data)
    cfg = Config.model_validate(data)

    if validate:
        config_warnings = validate_config(cfg)
        if print_warnings and config_warnings:
            import sys

            for warning in config_warnings:
                print(f"[CONFIG WARNING] {warning}", file=sys.stderr)  # noqa: T201

    return cfg


def load_config_from_path(config_path: Path, validate: bool = True, print_warnings: bool = True) -> Config:
    """Load configuration from an explicit YAML file path.

    Args:
        config_path: Path to the configuration file to load.
        validate: Whether to run validation checks (default True).
        print_warnings: Whether to print validation warnings to stderr (default True).

    Returns:
        Config: Validated configuration instance.

    Raises:
        FileNotFoundError: If the config file doesn't exist or is a directory.
    """
    resolved_path = config_path.expanduser()
    if not resolved_path.exists():
        raise FileNotFoundError(f"Config file not found at {resolved_path}")
    if not resolved_path.is_file():
        raise FileNotFoundError(f"Config path is not a file: {resolved_path}")

    with resolved_path.open() as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        data = {}

    data = _apply_env_overrides(data)
    cfg = Config.model_validate(data)

    if validate:
        config_warnings = validate_config(cfg)
        if print_warnings and config_warnings:
            import sys

            for warning in config_warnings:
                print(f"[CONFIG WARNING] {warning}", file=sys.stderr)  # noqa: T201

    return cfg


def validate_config(cfg: Config) -> list[str]:  # noqa: C901
    """Validate configuration and return a list of warnings.

    This function checks for potential issues in the configuration:
    - Borg executable exists and is accessible
    - AWS configuration is complete (if not in offline mode)
    - Compression format is valid
    - Retention values are sensible

    Args:
        cfg: The configuration to validate

    Returns:
        List of warning messages (empty if no issues found)
    """
    warnings: list[str] = []

    # Check Borg executable
    borg_path = shutil.which(cfg.borg.executable_path)
    if not borg_path:
        warnings.append(f"Borg executable '{cfg.borg.executable_path}' not found in PATH. Backup operations will fail.")

    # Check AWS configuration if not offline
    if not cfg.offline:
        if not cfg.aws.s3_bucket:
            warnings.append("AWS S3 bucket not configured. S3 sync operations will fail.")
        if not cfg.aws.dynamodb_repos_table:
            warnings.append("AWS DynamoDB repos table not configured. Repository tracking will fail.")

    # Validate compression format
    valid_compression_prefixes = ("none", "lz4", "zstd", "zlib", "lzma")
    compression_base = cfg.borg.compression.split(",")[0].lower()
    if compression_base not in valid_compression_prefixes:
        warnings.append(
            f"Invalid compression format '{cfg.borg.compression}'. "
            f"Valid formats: {', '.join(valid_compression_prefixes)}"
        )

    # Validate retention policy
    retention = cfg.borg.retention
    if retention.keep_daily < 0:
        warnings.append(f"Invalid retention.keep_daily: {retention.keep_daily} (must be >= 0)")
    if retention.keep_weekly < 0:
        warnings.append(f"Invalid retention.keep_weekly: {retention.keep_weekly} (must be >= 0)")
    if retention.keep_monthly < 0:
        warnings.append(f"Invalid retention.keep_monthly: {retention.keep_monthly} (must be >= 0)")
    if retention.keep_yearly < 0:
        warnings.append(f"Invalid retention.keep_yearly: {retention.keep_yearly} (must be >= 0)")

    # Warn if no retention policy is set
    total_kept = retention.keep_daily + retention.keep_weekly + retention.keep_monthly + retention.keep_yearly
    if total_kept == 0:
        warnings.append(
            "No retention policy configured. All archives will be kept which may consume excessive storage."
        )

    # Check checkpoint interval
    if cfg.borg.checkpoint_interval < 0:
        warnings.append(f"Invalid checkpoint_interval: {cfg.borg.checkpoint_interval} (must be >= 0)")

    return warnings


# Mapping of config paths to their corresponding environment variable names
CONFIG_ENV_VAR_MAP: dict[str, str] = {
    # Top-level
    "offline": "BORGBOI_OFFLINE",
    "debug": "BORGBOI_DEBUG",
    # AWS
    "aws.dynamodb_repos_table": "BORGBOI_AWS__DYNAMODB_REPOS_TABLE",
    "aws.dynamodb_archives_table": "BORGBOI_AWS__DYNAMODB_ARCHIVES_TABLE",
    "aws.s3_bucket": "BORGBOI_AWS__S3_BUCKET",
    "aws.region": "BORGBOI_AWS__REGION",
    "aws.profile": "BORGBOI_AWS__PROFILE",
    # Borg
    "borg.executable_path": "BORGBOI_BORG__EXECUTABLE_PATH",
    "borg.default_repo_path": "BORGBOI_BORG__DEFAULT_REPO_PATH",
    "borg.compression": "BORGBOI_BORG__COMPRESSION",
    "borg.checkpoint_interval": "BORGBOI_BORG__CHECKPOINT_INTERVAL",
    "borg.storage_quota": "BORGBOI_BORG__STORAGE_QUOTA",
    "borg.additional_free_space": "BORGBOI_BORG__ADDITIONAL_FREE_SPACE",
    "borg.borg_passphrase": "BORGBOI_BORG__BORG_PASSPHRASE",
    "borg.borg_new_passphrase": "BORGBOI_BORG__BORG_NEW_PASSPHRASE",
    # Borg retention
    "borg.retention.keep_daily": "BORGBOI_BORG__RETENTION__KEEP_DAILY",
    "borg.retention.keep_weekly": "BORGBOI_BORG__RETENTION__KEEP_WEEKLY",
    "borg.retention.keep_monthly": "BORGBOI_BORG__RETENTION__KEEP_MONTHLY",
    "borg.retention.keep_yearly": "BORGBOI_BORG__RETENTION__KEEP_YEARLY",
    # UI
    "ui.theme": "BORGBOI_UI__THEME",
    "ui.show_progress": "BORGBOI_UI__SHOW_PROGRESS",
    "ui.color_output": "BORGBOI_UI__COLOR_OUTPUT",
    "ui.table_style": "BORGBOI_UI__TABLE_STYLE",
}


def get_env_overrides() -> dict[str, str]:
    """Return a mapping of config paths to env var names for all currently set env overrides.

    This checks which BORGBOI_* environment variables are set and returns a dict
    mapping the corresponding config path (e.g., 'aws.s3_bucket') to the env var
    name (e.g., 'BORGBOI_AWS__S3_BUCKET').

    Returns:
        dict[str, str]: Config paths that are overridden by environment variables,
                       mapped to their env var names.
    """
    return {
        config_path: env_var for config_path, env_var in CONFIG_ENV_VAR_MAP.items() if os.getenv(env_var) is not None
    }


def save_config(cfg: Config, config_path: Path | None = None) -> None:
    """Save configuration to a YAML file.

    Args:
        cfg: Config instance to save
        config_path: Optional custom path. Defaults to ~/.borgboi/config.yaml.
    """
    resolved_path = config_path if config_path is not None else get_default_config_path()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    config_dict = cfg.model_dump(exclude_none=True, mode="json")
    if "borg" in config_dict and "default_repo_path" in config_dict["borg"]:
        config_dict["borg"]["default_repo_path"] = str(config_dict["borg"]["default_repo_path"])
    with resolved_path.open("w") as f:
        yaml.safe_dump(config_dict, f, default_flow_style=False, sort_keys=False)


# Global config instance (singleton)
config = get_config()
