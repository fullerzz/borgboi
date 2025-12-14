"""Configuration management for borgboi using dynaconf and Pydantic."""

import os
from functools import lru_cache
from pathlib import Path
from platform import system

import yaml
from dynaconf import Dynaconf  # type: ignore[import-untyped]
from pydantic import BaseModel, Field


class RetentionConfig(BaseModel):
    """Borg backup retention policy configuration."""

    keep_daily: int = 7
    keep_weekly: int = 4
    keep_monthly: int = 6
    keep_yearly: int = 0


class AWSConfig(BaseModel):
    """AWS service configuration."""

    dynamodb_repos_table: str = "borgboi-repos"
    dynamodb_archives_table: str = "borgboi-archives"
    s3_bucket: str = "borgboi-backup"
    region: str = "us-west-1"
    profile: str | None = None


class BorgConfig(BaseModel):
    """Borg-specific configuration."""

    executable_path: str = "borg"
    default_repo_path: Path = Field(default_factory=lambda: Path.home() / ".borgboi" / "repositories")
    compression: str = "zstd,1"
    checkpoint_interval: int = 900  # seconds
    storage_quota: str = "100G"
    additional_free_space: str = "2G"
    retention: RetentionConfig = Field(default_factory=RetentionConfig)


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


@lru_cache(maxsize=1)
def get_config() -> Config:
    """
    Load and return validated configuration from dynaconf settings.

    Returns:
        Config: Validated configuration instance
    """
    return Config(
        aws=AWSConfig(
            dynamodb_repos_table=str(settings.get("aws.dynamodb_repos_table", "borgboi-repos")),
            dynamodb_archives_table=str(settings.get("aws.dynamodb_archives_table", "borgboi-archives")),
            s3_bucket=str(settings.get("aws.s3_bucket", "borgboi-backup")),
            region=str(settings.get("aws.region", "us-west-1")),
            profile=settings.get("aws.profile") if settings.get("aws.profile") is not None else None,
        ),
        borg=BorgConfig(
            executable_path=str(settings.get("borg.executable_path", "borg")),
            default_repo_path=Path(
                str(settings.get("borg.default_repo_path", str(resolve_home_dir() / ".borgboi" / "repositories")))
            ),
            compression=str(settings.get("borg.compression", "zstd,1")),
            checkpoint_interval=int(settings.get("borg.checkpoint_interval", 900)),
            storage_quota=str(settings.get("borg.storage_quota", "100G")),
            additional_free_space=str(settings.get("borg.additional_free_space", "2G")),
            retention=RetentionConfig(
                keep_daily=int(settings.get("borg.retention.keep_daily", 7)),
                keep_weekly=int(settings.get("borg.retention.keep_weekly", 4)),
                keep_monthly=int(settings.get("borg.retention.keep_monthly", 6)),
                keep_yearly=int(settings.get("borg.retention.keep_yearly", 0)),
            ),
        ),
        ui=UIConfig(
            theme=str(settings.get("ui.theme", "catppuccin")),
            show_progress=bool(settings.get("ui.show_progress", True)),
            color_output=bool(settings.get("ui.color_output", True)),
            table_style=str(settings.get("ui.table_style", "rounded")),
        ),
        offline=bool(settings.get("offline", False)),
        debug=bool(settings.get("debug", False)),
    )


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
