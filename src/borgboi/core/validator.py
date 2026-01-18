"""Centralized validation rules for BorgBoi.

This module provides a unified Validator class for validating all
input data throughout the application.
"""

import re
from pathlib import Path
from shutil import which

from borgboi.config import Config
from borgboi.core.errors import ValidationError
from borgboi.core.models import RetentionPolicy

# Validation constants
MAX_REPO_NAME_LENGTH = 64
VALID_REPO_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
VALID_COMPRESSIONS = {"none", "lz4", "zstd", "zstd,1", "zstd,3", "zstd,6", "zlib", "zlib,6", "lzma", "lzma,6"}


class Validator:
    """Centralized validation for BorgBoi.

    All validation methods are static and raise ValidationError on failure.
    """

    @staticmethod
    def validate_repo_name(name: str) -> None:
        """Validate a repository name.

        Repository names must:
        - Be 1-64 characters long
        - Start with alphanumeric character
        - Contain only alphanumeric characters, underscores, and hyphens

        Args:
            name: The repository name to validate

        Raises:
            ValidationError: If the name is invalid
        """
        if not name:
            raise ValidationError("Repository name cannot be empty", field="name")

        if len(name) > MAX_REPO_NAME_LENGTH:
            raise ValidationError(
                f"Repository name too long (max {MAX_REPO_NAME_LENGTH} characters)", field="name", value=name
            )

        if not VALID_REPO_NAME_PATTERN.match(name):
            raise ValidationError(
                "Repository name must start with alphanumeric and contain only alphanumeric, underscore, or hyphen",
                field="name",
                value=name,
            )

    @staticmethod
    def validate_path(path: str, must_exist: bool = False, must_be_directory: bool = False) -> None:
        """Validate a file system path.

        Args:
            path: The path to validate
            must_exist: If True, the path must exist
            must_be_directory: If True, the path must be a directory

        Raises:
            ValidationError: If the path is invalid
        """
        if not path:
            raise ValidationError("Path cannot be empty", field="path")

        try:
            path_obj = Path(path)
        except Exception as e:
            raise ValidationError(f"Invalid path format: {e}", field="path", value=path) from e

        if must_exist and not path_obj.exists():
            raise ValidationError(f"Path does not exist: {path}", field="path", value=path)

        if must_be_directory and path_obj.exists() and not path_obj.is_dir():
            raise ValidationError(f"Path is not a directory: {path}", field="path", value=path)

    @staticmethod
    def validate_compression(compression: str) -> None:
        """Validate a compression setting.

        Valid compressions:
        - none: No compression
        - lz4: Fast compression
        - zstd, zstd,1, zstd,3, zstd,6: Zstandard compression
        - zlib, zlib,6: Zlib compression
        - lzma, lzma,6: LZMA compression

        Args:
            compression: The compression setting to validate

        Raises:
            ValidationError: If the compression is invalid
        """
        if not compression:
            raise ValidationError("Compression cannot be empty", field="compression")

        # Allow base algorithm names with any level
        base_algorithm = compression.split(",")[0]
        if base_algorithm not in {"none", "lz4", "zstd", "zlib", "lzma"}:
            raise ValidationError(
                f"Invalid compression algorithm: {base_algorithm}. Valid options: none, lz4, zstd, zlib, lzma",
                field="compression",
                value=compression,
            )

        # Validate level if provided
        if "," in compression:
            try:
                level = int(compression.split(",")[1])
                if level < 0 or level > 22:  # Zstd supports up to 22
                    raise ValidationError(
                        f"Compression level must be 0-22, got {level}", field="compression", value=compression
                    )
            except ValueError as e:
                raise ValidationError(
                    f"Invalid compression level format: {compression}", field="compression", value=compression
                ) from e

    @staticmethod
    def validate_retention_policy(policy: RetentionPolicy) -> None:
        """Validate a retention policy.

        At least one retention period must be set (>0).

        Args:
            policy: The retention policy to validate

        Raises:
            ValidationError: If the policy is invalid
        """
        if policy.keep_daily <= 0 and policy.keep_weekly <= 0 and policy.keep_monthly <= 0 and policy.keep_yearly <= 0:
            raise ValidationError("At least one retention period must be greater than 0", field="retention_policy")

    @staticmethod
    def validate_exclusion_pattern(pattern: str) -> None:
        """Validate an exclusion pattern.

        Args:
            pattern: The exclusion pattern to validate

        Raises:
            ValidationError: If the pattern is invalid
        """
        if not pattern:
            raise ValidationError("Exclusion pattern cannot be empty", field="pattern")

        # Check for obviously dangerous patterns
        dangerous_patterns = {"/", "/*", "/**", "*", "**"}
        if pattern.strip() in dangerous_patterns:
            raise ValidationError(
                f"Dangerous exclusion pattern that would exclude everything: {pattern}",
                field="pattern",
                value=pattern,
            )

    @staticmethod
    def validate_archive_name(name: str) -> None:
        """Validate an archive name.

        Archive names must not be empty or contain special characters
        that could cause issues.

        Args:
            name: The archive name to validate

        Raises:
            ValidationError: If the archive name is invalid
        """
        if not name:
            raise ValidationError("Archive name cannot be empty", field="archive_name")

        # Check for problematic characters
        forbidden_chars = {":", "/", "\\", "\x00"}
        for char in forbidden_chars:
            if char in name:
                raise ValidationError(
                    f"Archive name contains forbidden character: {char!r}",
                    field="archive_name",
                    value=name,
                )

    @staticmethod
    def validate_config(config: Config) -> list[str]:
        """Validate a configuration and return warnings.

        This method checks the configuration for potential issues
        and returns a list of warning messages. It does not raise
        exceptions for non-fatal issues.

        Args:
            config: The configuration to validate

        Returns:
            List of warning messages (empty if no warnings)
        """
        warnings = []

        # Check if borg executable exists
        borg_path = config.borg.executable_path
        if not which(borg_path):
            warnings.append(f"Borg executable not found at '{borg_path}'. Make sure Borg is installed.")

        # Validate compression
        try:
            Validator.validate_compression(config.borg.compression)
        except ValidationError as e:
            warnings.append(f"Invalid compression setting: {e.message}")

        # Check AWS config if not offline
        if not config.offline:
            if not config.aws.s3_bucket:
                warnings.append("AWS S3 bucket not configured. Set 'aws.s3_bucket' in config.")
            if not config.aws.dynamodb_repos_table:
                warnings.append("AWS DynamoDB table not configured. Set 'aws.dynamodb_repos_table' in config.")

        # Validate retention policy
        retention = config.borg.retention
        if retention.keep_daily <= 0 and retention.keep_weekly <= 0 and retention.keep_monthly <= 0:
            warnings.append(
                "Retention policy has all values at 0. No backups will be retained. "
                "Consider setting at least keep_daily > 0."
            )

        # Check storage quota format
        quota = config.borg.storage_quota
        if not re.match(r"^\d+[KMGT]?$", quota, re.IGNORECASE):
            warnings.append(f"Storage quota '{quota}' may be in an invalid format. Expected format: 100G, 500M, etc.")

        return warnings

    @staticmethod
    def validate_passphrase(passphrase: str, min_length: int = 8) -> None:
        """Validate a passphrase for strength.

        Args:
            passphrase: The passphrase to validate
            min_length: Minimum required length (default: 8)

        Raises:
            ValidationError: If the passphrase is too weak
        """
        if not passphrase:
            raise ValidationError("Passphrase cannot be empty", field="passphrase")

        if len(passphrase) < min_length:
            raise ValidationError(f"Passphrase must be at least {min_length} characters", field="passphrase")

    @staticmethod
    def validate_hostname(hostname: str) -> None:
        """Validate a hostname.

        Args:
            hostname: The hostname to validate

        Raises:
            ValidationError: If the hostname is invalid
        """
        if not hostname:
            raise ValidationError("Hostname cannot be empty", field="hostname")

        # Basic hostname validation (RFC 1123)
        if len(hostname) > 253:
            raise ValidationError("Hostname too long (max 253 characters)", field="hostname", value=hostname)

        # Check each label
        labels = hostname.split(".")
        for label in labels:
            if not label:
                raise ValidationError("Hostname contains empty label", field="hostname", value=hostname)
            if len(label) > 63:
                raise ValidationError("Hostname label too long (max 63 characters)", field="hostname", value=hostname)
            if not re.match(r"^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$", label):
                raise ValidationError("Hostname contains invalid characters", field="hostname", value=hostname)
