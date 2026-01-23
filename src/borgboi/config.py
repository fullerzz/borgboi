"""Configuration management for borgboi using dynaconf and Pydantic."""

import os
import shutil
from functools import lru_cache
from pathlib import Path
from platform import system

import yaml
from dynaconf import Dynaconf  # type: ignore[import-untyped]
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
    default_repo_path: Path = Field(default_factory=lambda: Path.home() / ".borgboi" / "repositories")
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


# Initialize dynaconf settings
_settings_dir = _create_settings_dir()
settings = Dynaconf(
    envvar_prefix="BORGBOI",
    settings_files=["config.yaml"],
    settings_dir=str(_settings_dir),
    environments=False,
    load_dotenv=True,
    merge_enabled=True,
)


def _build_config(settings_source: Dynaconf, validate: bool = True, print_warnings: bool = True) -> Config:
    cfg = Config(
        aws=AWSConfig(
            dynamodb_repos_table=str(settings_source.get("aws.dynamodb_repos_table", DEFAULT_DYNAMODB_REPOS_TABLE)),
            dynamodb_archives_table=str(
                settings_source.get("aws.dynamodb_archives_table", DEFAULT_DYNAMODB_ARCHIVES_TABLE)
            ),
            s3_bucket=str(settings_source.get("aws.s3_bucket", DEFAULT_S3_BUCKET)),
            region=str(settings_source.get("aws.region", DEFAULT_AWS_REGION)),
            profile=settings_source.get("aws.profile") if settings_source.get("aws.profile") is not None else None,
        ),
        borg=BorgConfig(
            executable_path=str(settings_source.get("borg.executable_path", "borg")),
            default_repo_path=Path(
                str(
                    settings_source.get(
                        "borg.default_repo_path",
                        str(resolve_home_dir() / ".borgboi" / "repositories"),
                    )
                )
            ),
            compression=str(settings_source.get("borg.compression", DEFAULT_REPO_COMPRESSION)),
            checkpoint_interval=int(settings_source.get("borg.checkpoint_interval", 900)),
            storage_quota=str(settings_source.get("borg.storage_quota", DEFAULT_REPO_STORAGE_QUOTA)),
            additional_free_space=str(settings_source.get("borg.additional_free_space", "2G")),
            retention=RetentionConfig(
                keep_daily=int(settings_source.get("borg.retention.keep_daily", 7)),
                keep_weekly=int(settings_source.get("borg.retention.keep_weekly", 4)),
                keep_monthly=int(settings_source.get("borg.retention.keep_monthly", 6)),
                keep_yearly=int(settings_source.get("borg.retention.keep_yearly", 0)),
            ),
            borg_passphrase=settings_source.get("borg.borg_passphrase"),
            borg_new_passphrase=settings_source.get("borg.borg_new_passphrase"),
        ),
        ui=UIConfig(
            theme=str(settings_source.get("ui.theme", "catppuccin")),
            show_progress=bool(settings_source.get("ui.show_progress", True)),
            color_output=bool(settings_source.get("ui.color_output", True)),
            table_style=str(settings_source.get("ui.table_style", "rounded")),
        ),
        offline=bool(settings_source.get("offline", False)),
        debug=bool(settings_source.get("debug", False)),
    )

    if validate:
        config_warnings = validate_config(cfg)
        if print_warnings and config_warnings:
            import sys

            for warning in config_warnings:
                print(f"[CONFIG WARNING] {warning}", file=sys.stderr)  # noqa: T201

    return cfg


@lru_cache(maxsize=1)
def get_config(validate: bool = True, print_warnings: bool = True) -> Config:
    """Load and return validated configuration from dynaconf settings.

    Args:
        validate: Whether to run validation checks (default True)
        print_warnings: Whether to print validation warnings to stderr (default True)

    Returns:
        Config: Validated configuration instance
    """
    return _build_config(settings, validate=validate, print_warnings=print_warnings)


def load_config_from_path(config_path: Path, validate: bool = True, print_warnings: bool = True) -> Config:
    """Load configuration from an explicit config file path."""
    resolved_path = config_path.expanduser()
    if not resolved_path.exists():
        raise FileNotFoundError(f"Config file not found at {resolved_path}")
    if not resolved_path.is_file():
        raise FileNotFoundError(f"Config path is not a file: {resolved_path}")
    local_settings = Dynaconf(
        envvar_prefix="BORGBOI",
        settings_files=[resolved_path.name],
        settings_dir=str(resolved_path.parent),
        environments=False,
        load_dotenv=True,
        merge_enabled=True,
    )
    return _build_config(local_settings, validate=validate, print_warnings=print_warnings)


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


def save_config(cfg: Config, config_path: Path | None = None) -> None:
    """
    Save configuration to YAML file.

    Args:
        cfg: Config instance to save
        config_path: Optional custom path (defaults to ~/.borgboi/config.yaml)
    """
    if config_path is None:
        config_path = resolve_home_dir() / ".borgboi" / "config.yaml"

    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert config to dict and write to YAML
    config_dict = cfg.model_dump(exclude_none=True, mode="json")

    # Convert Path objects to strings
    if "borg" in config_dict and "default_repo_path" in config_dict["borg"]:
        config_dict["borg"]["default_repo_path"] = str(config_dict["borg"]["default_repo_path"])

    with config_path.open("w") as f:
        yaml.safe_dump(config_dict, f, default_flow_style=False, sort_keys=False)


# Global config instance (singleton)
config = get_config()
