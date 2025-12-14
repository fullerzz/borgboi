"""Tests for borgboi configuration module."""

import importlib
from pathlib import Path

import pytest

from borgboi import config as config_module
from borgboi.config import (
    AWSConfig,
    BorgConfig,
    Config,
    RetentionConfig,
    UIConfig,
    resolve_home_dir,
    save_config,
)


@pytest.fixture(autouse=True)
def _reset_config() -> None:
    """Reset config module before each test to ensure clean state."""
    # Reload config module to get fresh instance
    importlib.reload(config_module)


def test_retention_config_defaults() -> None:
    """Test that RetentionConfig has correct defaults."""
    retention = RetentionConfig()
    assert retention.keep_daily == 7
    assert retention.keep_weekly == 4
    assert retention.keep_monthly == 6
    assert retention.keep_yearly == 0


def test_retention_config_custom_values() -> None:
    """Test RetentionConfig with custom values."""
    retention = RetentionConfig(keep_daily=14, keep_weekly=8, keep_monthly=12, keep_yearly=2)
    assert retention.keep_daily == 14
    assert retention.keep_weekly == 8
    assert retention.keep_monthly == 12
    assert retention.keep_yearly == 2


def test_aws_config_defaults() -> None:
    """Test that AWSConfig has correct defaults."""
    aws = AWSConfig()
    assert aws.dynamodb_repos_table == "borgboi-repos"
    assert aws.dynamodb_archives_table == "borgboi-archives"
    assert aws.s3_bucket == "borgboi-backup"
    assert aws.region == "us-west-1"
    assert aws.profile is None


def test_aws_config_custom_values() -> None:
    """Test AWSConfig with custom values."""
    aws = AWSConfig(
        dynamodb_repos_table="custom-repos",
        dynamodb_archives_table="custom-archives",
        s3_bucket="custom-bucket",
        region="us-east-1",
        profile="myprofile",
    )
    assert aws.dynamodb_repos_table == "custom-repos"
    assert aws.dynamodb_archives_table == "custom-archives"
    assert aws.s3_bucket == "custom-bucket"
    assert aws.region == "us-east-1"
    assert aws.profile == "myprofile"


def test_borg_config_defaults() -> None:
    """Test that BorgConfig has correct defaults."""
    borg = BorgConfig()
    assert borg.executable_path == "borg"
    assert borg.default_repo_path == Path.home() / ".borgboi" / "repositories"
    assert borg.compression == "zstd,1"
    assert borg.checkpoint_interval == 900
    assert borg.storage_quota == "100G"
    assert borg.additional_free_space == "2G"
    assert borg.retention.keep_daily == 7


def test_borg_config_custom_values() -> None:
    """Test BorgConfig with custom values."""
    borg = BorgConfig(
        executable_path="/usr/local/bin/borg",
        default_repo_path=Path("/custom/path"),
        compression="lz4",
        checkpoint_interval=600,
        storage_quota="200G",
        additional_free_space="5G",
        retention=RetentionConfig(keep_daily=14),
    )
    assert borg.executable_path == "/usr/local/bin/borg"
    assert borg.default_repo_path == Path("/custom/path")
    assert borg.compression == "lz4"
    assert borg.checkpoint_interval == 600
    assert borg.storage_quota == "200G"
    assert borg.additional_free_space == "5G"
    assert borg.retention.keep_daily == 14


def test_ui_config_defaults() -> None:
    """Test that UIConfig has correct defaults."""
    ui = UIConfig()
    assert ui.theme == "catppuccin"
    assert ui.show_progress is True
    assert ui.color_output is True
    assert ui.table_style == "rounded"


def test_ui_config_custom_values() -> None:
    """Test UIConfig with custom values."""
    ui = UIConfig(theme="monokai", show_progress=False, color_output=False, table_style="simple")
    assert ui.theme == "monokai"
    assert ui.show_progress is False
    assert ui.color_output is False
    assert ui.table_style == "simple"


def test_config_defaults() -> None:
    """Test that Config has correct defaults."""
    cfg = Config()
    assert cfg.aws.dynamodb_repos_table == "borgboi-repos"
    assert cfg.borg.compression == "zstd,1"
    assert cfg.ui.theme == "catppuccin"
    assert cfg.offline is False
    assert cfg.debug is False


def test_config_custom_values() -> None:
    """Test Config with custom values."""
    cfg = Config(
        aws=AWSConfig(s3_bucket="custom-bucket"),
        borg=BorgConfig(compression="lz4"),
        ui=UIConfig(theme="monokai"),
        offline=True,
        debug=True,
    )
    assert cfg.aws.s3_bucket == "custom-bucket"
    assert cfg.borg.compression == "lz4"
    assert cfg.ui.theme == "monokai"
    assert cfg.offline is True
    assert cfg.debug is True


def test_config_borgboi_dir_property() -> None:
    """Test that borgboi_dir property returns correct path."""
    cfg = Config()
    assert cfg.borgboi_dir == resolve_home_dir() / ".borgboi"


def test_config_excludes_filename_property() -> None:
    """Test that excludes_filename property returns correct value."""
    cfg = Config()
    assert cfg.excludes_filename == "excludes.txt"


def test_resolve_home_dir_default() -> None:
    """Test that resolve_home_dir returns user home by default."""
    home = resolve_home_dir()
    assert home == Path.home()


def test_resolve_home_dir_with_borgboi_home(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that resolve_home_dir respects BORGBOI_HOME."""
    monkeypatch.setenv("BORGBOI_HOME", "/custom/home")
    home = resolve_home_dir()
    assert home == Path("/custom/home")


def test_save_config_default_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test saving config to default path."""
    # Use tmp_path as home directory
    monkeypatch.setenv("BORGBOI_HOME", str(tmp_path))

    cfg = Config(offline=True, debug=True)
    save_config(cfg)

    config_file = tmp_path / ".borgboi" / "config.yaml"
    assert config_file.exists()

    # Read and verify content
    import yaml

    with config_file.open() as f:
        saved_data = yaml.safe_load(f)

    assert saved_data["offline"] is True
    assert saved_data["debug"] is True


def test_save_config_custom_path(tmp_path: Path) -> None:
    """Test saving config to custom path."""
    config_file = tmp_path / "custom_config.yaml"

    cfg = Config(offline=True)
    save_config(cfg, config_file)

    assert config_file.exists()

    # Read and verify content
    import yaml

    with config_file.open() as f:
        saved_data = yaml.safe_load(f)

    assert saved_data["offline"] is True


def test_get_config_with_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that environment variables override defaults."""
    monkeypatch.setenv("BORGBOI_OFFLINE", "true")
    monkeypatch.setenv("BORGBOI_DEBUG", "true")
    monkeypatch.setenv("BORGBOI_AWS__S3_BUCKET", "env-bucket")
    monkeypatch.setenv("BORGBOI_AWS__REGION", "us-east-1")
    monkeypatch.setenv("BORGBOI_BORG__COMPRESSION", "lz4")
    monkeypatch.setenv("BORGBOI_BORG__RETENTION__KEEP_DAILY", "14")

    # Reload config to pick up env vars
    importlib.reload(config_module)
    from borgboi.config import config

    assert config.offline is True
    assert config.debug is True
    assert config.aws.s3_bucket == "env-bucket"
    assert config.aws.region == "us-east-1"
    assert config.borg.compression == "lz4"
    assert config.borg.retention.keep_daily == 14


@pytest.mark.parametrize(
    ("env_var", "config_path", "expected_value"),
    [
        ("BORGBOI_OFFLINE", "offline", True),
        ("BORGBOI_DEBUG", "debug", True),
        ("BORGBOI_AWS__DYNAMODB_REPOS_TABLE", "aws.dynamodb_repos_table", "custom-table"),
        ("BORGBOI_AWS__S3_BUCKET", "aws.s3_bucket", "custom-bucket"),
        ("BORGBOI_AWS__REGION", "aws.region", "eu-west-1"),
        ("BORGBOI_BORG__COMPRESSION", "borg.compression", "lzma"),
        ("BORGBOI_BORG__STORAGE_QUOTA", "borg.storage_quota", "500G"),
        ("BORGBOI_BORG__CHECKPOINT_INTERVAL", "borg.checkpoint_interval", 1800),
        ("BORGBOI_BORG__RETENTION__KEEP_DAILY", "borg.retention.keep_daily", 30),
        ("BORGBOI_BORG__RETENTION__KEEP_WEEKLY", "borg.retention.keep_weekly", 8),
        ("BORGBOI_UI__THEME", "ui.theme", "monokai"),
        ("BORGBOI_UI__SHOW_PROGRESS", "ui.show_progress", False),
    ],
)
def test_env_var_overrides(
    monkeypatch: pytest.MonkeyPatch, env_var: str, config_path: str, expected_value: object
) -> None:
    """Test that individual environment variables override config."""
    # Set the environment variable
    monkeypatch.setenv(env_var, str(expected_value))

    # Reload config to pick up env var
    importlib.reload(config_module)
    from borgboi.config import config

    # Navigate to the config value using the path
    value = config
    for part in config_path.split("."):
        value = getattr(value, part)

    # For boolean and int values, assert directly; for strings, assert as-is
    if isinstance(expected_value, (bool, int)):
        assert value == expected_value
    else:
        assert value == expected_value
