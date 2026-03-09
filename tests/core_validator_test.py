from pathlib import Path

import pytest

from borgboi.config import Config
from borgboi.core.errors import ValidationError
from borgboi.core.models import RetentionPolicy
from borgboi.core.validator import MAX_REPO_NAME_LENGTH, Validator


@pytest.mark.parametrize("name", ["repo", "repo-1", "repo_1", "R2D2"])
def test_validate_repo_name_accepts_valid_names(name: str) -> None:
    Validator.validate_repo_name(name)


def test_validate_repo_name_rejects_empty_name() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Validator.validate_repo_name("")

    assert exc_info.value.field == "name"


def test_validate_repo_name_rejects_name_longer_than_max() -> None:
    name = "a" * (MAX_REPO_NAME_LENGTH + 1)

    with pytest.raises(ValidationError) as exc_info:
        Validator.validate_repo_name(name)

    assert exc_info.value.field == "name"
    assert exc_info.value.value == name


@pytest.mark.parametrize("name", ["-repo", "_repo", "repo name", "repo!", ".repo"])
def test_validate_repo_name_rejects_invalid_start_or_characters(name: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        Validator.validate_repo_name(name)

    assert exc_info.value.field == "name"
    assert exc_info.value.value == name


def test_validate_path_rejects_empty_path() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Validator.validate_path("")

    assert exc_info.value.field == "path"


def test_validate_path_rejects_missing_path_when_must_exist(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing"

    with pytest.raises(ValidationError) as exc_info:
        Validator.validate_path(missing_path.as_posix(), must_exist=True)

    assert exc_info.value.field == "path"
    assert exc_info.value.value == missing_path.as_posix()


def test_validate_path_rejects_file_when_directory_required(tmp_path: Path) -> None:
    file_path = tmp_path / "repo.txt"
    file_path.write_text("data", encoding="utf-8")

    with pytest.raises(ValidationError) as exc_info:
        Validator.validate_path(file_path.as_posix(), must_exist=True, must_be_directory=True)

    assert exc_info.value.field == "path"
    assert exc_info.value.value == file_path.as_posix()


def test_validate_path_allows_missing_directory_when_only_directory_required(tmp_path: Path) -> None:
    Validator.validate_path((tmp_path / "future-repo").as_posix(), must_be_directory=True)


@pytest.mark.parametrize("compression", ["none", "lz4", "zstd,6", "zlib,0", "lzma,22"])
def test_validate_compression_accepts_known_algorithms_and_levels(compression: str) -> None:
    Validator.validate_compression(compression)


def test_validate_compression_rejects_unknown_algorithm() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Validator.validate_compression("brotli")

    assert exc_info.value.field == "compression"
    assert exc_info.value.value == "brotli"


def test_validate_compression_rejects_non_numeric_level() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Validator.validate_compression("zstd,fast")

    assert exc_info.value.field == "compression"
    assert exc_info.value.value == "zstd,fast"


def test_validate_compression_rejects_out_of_range_level() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Validator.validate_compression("zstd,23")

    assert exc_info.value.field == "compression"
    assert exc_info.value.value == "zstd,23"


def test_validate_retention_policy_requires_at_least_one_positive_value() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Validator.validate_retention_policy(RetentionPolicy(keep_daily=0, keep_weekly=0, keep_monthly=0, keep_yearly=0))

    assert exc_info.value.field == "retention_policy"


@pytest.mark.parametrize("pattern", ["/", "/*", "/**", "*", "**"])
def test_validate_exclusion_pattern_rejects_dangerous_match_all_patterns(pattern: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        Validator.validate_exclusion_pattern(pattern)

    assert exc_info.value.field == "pattern"
    assert exc_info.value.value == pattern


@pytest.mark.parametrize("name", ["archive:1", "archive/name", r"archive\name", "bad\x00name"])
def test_validate_archive_name_rejects_forbidden_characters(name: str) -> None:
    if name == "bad\\x00name":
        name = "bad\x00name"

    with pytest.raises(ValidationError) as exc_info:
        Validator.validate_archive_name(name)

    assert exc_info.value.field == "archive_name"
    assert exc_info.value.value == name


@pytest.mark.parametrize("passphrase", ["", "short"])
def test_validate_passphrase_rejects_empty_or_too_short(passphrase: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        Validator.validate_passphrase(passphrase)

    assert exc_info.value.field == "passphrase"


@pytest.mark.parametrize("hostname", ["host", "host.local", "a-b.example"])
def test_validate_hostname_accepts_valid_rfc1123_style_names(hostname: str) -> None:
    Validator.validate_hostname(hostname)


@pytest.mark.parametrize("hostname", ["a..b", "-bad", "bad-", "bad_label"])
def test_validate_hostname_rejects_empty_label_or_invalid_characters(hostname: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        Validator.validate_hostname(hostname)

    assert exc_info.value.field == "hostname"
    assert exc_info.value.value == hostname


def test_validate_config_returns_expected_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("borgboi.core.validator.which", lambda _: None)
    config = Config(offline=False)
    config.borg.executable_path = "missing-borg"
    config.borg.compression = "brotli"
    config.borg.retention.keep_daily = 0
    config.borg.retention.keep_weekly = 0
    config.borg.retention.keep_monthly = 0
    config.borg.retention.keep_yearly = 5
    config.borg.storage_quota = "fifty"
    config.aws.s3_bucket = ""
    config.aws.dynamodb_repos_table = ""

    warnings = Validator.validate_config(config)

    assert any("Borg executable not found" in warning for warning in warnings)
    assert any("Invalid compression setting" in warning for warning in warnings)
    assert any("AWS S3 bucket not configured" in warning for warning in warnings)
    assert any("AWS DynamoDB table not configured" in warning for warning in warnings)
    assert any("Retention policy has all values at 0" in warning for warning in warnings)
    assert any("Storage quota 'fifty'" in warning for warning in warnings)


def test_validate_config_skips_aws_warnings_in_offline_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("borgboi.core.validator.which", lambda _: "/usr/bin/borg")
    config = Config(offline=True)
    config.aws.s3_bucket = ""
    config.aws.dynamodb_repos_table = ""

    warnings = Validator.validate_config(config)

    assert not any("AWS S3 bucket not configured" in warning for warning in warnings)
    assert not any("AWS DynamoDB table not configured" in warning for warning in warnings)
