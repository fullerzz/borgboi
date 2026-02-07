"""Tests for borgboi configuration module."""

from pathlib import Path

import pytest

from borgboi import config as config_module
from borgboi.config import (
    CONFIG_ENV_VAR_MAP,
    AWSConfig,
    BorgConfig,
    Config,
    RetentionConfig,
    UIConfig,
    get_env_overrides,
    load_config_from_path,
    resolve_home_dir,
    save_config,
)


@pytest.fixture(autouse=True)
def _reset_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Reset config module before each test to ensure clean state.

    Also reloads dependent modules (like passphrase) that import config,
    so they get the fresh config reference.
    """
    _clear_borgboi_env_vars(monkeypatch)
    monkeypatch.setenv("BORGBOI_HOME", str(tmp_path))

    # Clear the cached config so next get_config() will re-read from fresh DB
    config_module.get_config.cache_clear()


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
    assert aws.dynamodb_repos_table == "bb-repos"
    assert aws.dynamodb_archives_table == "bb-archives"
    assert aws.s3_bucket == "bb-backups"
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
    assert borg.default_repo_path == config_module.resolve_home_dir() / ".borgboi" / "repositories"
    assert borg.compression == "zstd,6"
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
    assert cfg.aws.dynamodb_repos_table == "bb-repos"
    assert cfg.borg.compression == "zstd,6"
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
    import borgboi.config

    cfg = Config()
    # Use the module attribute (which may be monkeypatched) rather than the locally imported function
    assert cfg.borgboi_dir == borgboi.config.resolve_home_dir() / ".borgboi"


def test_config_excludes_filename_property() -> None:
    """Test that excludes_filename property returns correct value."""
    cfg = Config()
    assert cfg.excludes_filename == "excludes.txt"


def test_resolve_home_dir_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that resolve_home_dir returns user home by default."""
    monkeypatch.delenv("BORGBOI_HOME", raising=False)
    home = resolve_home_dir()
    assert home == Path.home()


def test_resolve_home_dir_with_borgboi_home(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that resolve_home_dir respects BORGBOI_HOME."""
    monkeypatch.setenv("BORGBOI_HOME", "/custom/home")
    home = resolve_home_dir()
    assert home == Path("/custom/home")


def test_borg_config_default_repo_path_uses_resolved_home(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test BorgConfig default repo path follows resolved home directory."""
    monkeypatch.setattr(config_module, "resolve_home_dir", lambda: Path("/custom/home"))

    borg = BorgConfig()

    assert borg.default_repo_path == Path("/custom/home") / ".borgboi" / "repositories"


def test_save_config_default_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test saving config to default YAML file."""
    import borgboi.config

    monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)

    cfg = Config(offline=True, debug=True)
    save_config(cfg)

    config_file = tmp_path / ".borgboi" / "config.yaml"
    assert config_file.exists()

    import yaml

    with config_file.open() as f:
        saved_data = yaml.safe_load(f)

    assert saved_data["offline"] is True
    assert saved_data["debug"] is True


def test_save_config_yaml_path(tmp_path: Path) -> None:
    """Test saving config to a YAML path."""
    config_file = tmp_path / "custom_config.yaml"

    cfg = Config(offline=True)
    save_config(cfg, config_file)

    assert config_file.exists()

    import yaml

    with config_file.open() as f:
        saved_data = yaml.safe_load(f)

    assert saved_data["offline"] is True


def test_load_config_from_path_rejects_directory(tmp_path: Path) -> None:
    """Test load_config_from_path rejects directory paths."""
    config_dir = tmp_path / "config-dir"
    config_dir.mkdir()

    with pytest.raises(FileNotFoundError, match="not a file"):
        load_config_from_path(config_dir)


def test_load_config_from_path_env_override_handles_non_dict_intermediate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test env overrides when a nested section exists but is not a mapping."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("aws: bad\n")

    monkeypatch.setenv("BORGBOI_AWS__S3_BUCKET", "env-bucket")

    cfg = load_config_from_path(config_file, validate=False)

    assert cfg.aws.s3_bucket == "env-bucket"


def test_get_config_with_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that environment variables override defaults."""
    monkeypatch.setenv("BORGBOI_OFFLINE", "true")
    monkeypatch.setenv("BORGBOI_DEBUG", "true")
    monkeypatch.setenv("BORGBOI_AWS__S3_BUCKET", "env-bucket")
    monkeypatch.setenv("BORGBOI_AWS__REGION", "us-east-1")
    monkeypatch.setenv("BORGBOI_BORG__COMPRESSION", "lz4")
    monkeypatch.setenv("BORGBOI_BORG__RETENTION__KEEP_DAILY", "14")

    config_module.get_config.cache_clear()
    cfg = config_module.get_config()

    assert cfg.offline is True
    assert cfg.debug is True
    assert cfg.aws.s3_bucket == "env-bucket"
    assert cfg.aws.region == "us-east-1"
    assert cfg.borg.compression == "lz4"
    assert cfg.borg.retention.keep_daily == 14


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
    monkeypatch.setenv(env_var, str(expected_value))

    config_module.get_config.cache_clear()
    cfg = config_module.get_config()

    # Navigate to the config value using the path
    value = cfg
    for part in config_path.split("."):
        value = getattr(value, part)

    if isinstance(expected_value, (bool, int)):
        assert value == expected_value
    else:
        assert value == expected_value


def _clear_borgboi_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear all BORGBOI_* environment variables to ensure clean test state."""
    for env_var in CONFIG_ENV_VAR_MAP.values():
        monkeypatch.delenv(env_var, raising=False)


def test_get_env_overrides_empty_when_no_env_vars_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that get_env_overrides returns empty dict when no env vars are set."""
    _clear_borgboi_env_vars(monkeypatch)

    overrides = get_env_overrides()
    assert overrides == {}


def test_get_env_overrides_returns_set_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that get_env_overrides returns mapping for set env vars."""
    _clear_borgboi_env_vars(monkeypatch)
    monkeypatch.setenv("BORGBOI_OFFLINE", "true")
    monkeypatch.setenv("BORGBOI_AWS__S3_BUCKET", "test-bucket")

    overrides = get_env_overrides()

    assert "offline" in overrides
    assert overrides["offline"] == "BORGBOI_OFFLINE"
    assert "aws.s3_bucket" in overrides
    assert overrides["aws.s3_bucket"] == "BORGBOI_AWS__S3_BUCKET"
    # Other env vars should not be in the result
    assert "debug" not in overrides


def test_get_env_overrides_includes_nested_config_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that nested config paths like borg.retention.keep_daily are handled."""
    _clear_borgboi_env_vars(monkeypatch)
    monkeypatch.setenv("BORGBOI_BORG__RETENTION__KEEP_DAILY", "30")

    overrides = get_env_overrides()

    assert "borg.retention.keep_daily" in overrides
    assert overrides["borg.retention.keep_daily"] == "BORGBOI_BORG__RETENTION__KEEP_DAILY"


def test_config_env_var_map_completeness() -> None:
    """Test that CONFIG_ENV_VAR_MAP covers all expected config paths."""
    # Verify key configuration paths are mapped
    expected_paths = [
        "offline",
        "debug",
        "aws.s3_bucket",
        "aws.region",
        "aws.profile",
        "borg.compression",
        "borg.storage_quota",
        "borg.retention.keep_daily",
        "borg.retention.keep_weekly",
        "borg.retention.keep_monthly",
        "borg.retention.keep_yearly",
        "ui.theme",
        "ui.show_progress",
    ]

    for path in expected_paths:
        assert path in CONFIG_ENV_VAR_MAP, f"Missing config path in CONFIG_ENV_VAR_MAP: {path}"


def test_get_env_overrides_all_config_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that all mapped config paths can be detected as overridden."""
    _clear_borgboi_env_vars(monkeypatch)

    # Set all env vars
    for env_var in CONFIG_ENV_VAR_MAP.values():
        monkeypatch.setenv(env_var, "test-value")

    overrides = get_env_overrides()

    # All paths should be in the result
    for config_path_key in CONFIG_ENV_VAR_MAP:
        assert config_path_key in overrides, f"Missing config path in overrides: {config_path_key}"
