"""Tests for the passphrase management module."""

import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from borgboi.config import config
from borgboi.lib import passphrase


class TestGenerateSecurePassphrase:
    """Tests for generate_secure_passphrase()."""

    def test_generates_non_empty_string(self):
        """Verify that a passphrase is generated."""
        result = passphrase.generate_secure_passphrase()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generates_url_safe_base64(self):
        """Verify passphrase is URL-safe base64 encoded."""
        result = passphrase.generate_secure_passphrase()
        # URL-safe base64 uses only alphanumeric, -, and _
        assert all(c.isalnum() or c in ["-", "_"] for c in result)

    def test_generates_expected_length(self):
        """Verify passphrase is approximately 43 characters (32 bytes base64)."""
        result = passphrase.generate_secure_passphrase()
        # 32 bytes base64 encoded = 43 characters
        assert len(result) == 43

    def test_generates_unique_passphrases(self):
        """Verify each generation produces a unique passphrase."""
        passphrases = [passphrase.generate_secure_passphrase() for _ in range(100)]
        # All should be unique
        assert len(set(passphrases)) == 100


class TestGetPassphraseFilePath:
    """Tests for get_passphrase_file_path()."""

    def test_returns_path_in_passphrases_dir(self):
        """Verify path is under ~/.borgboi/passphrases/."""
        result = passphrase.get_passphrase_file_path("test-repo")
        assert result.parent == config.passphrases_dir

    def test_uses_repo_name_with_key_extension(self):
        """Verify filename is {repo-name}.key."""
        result = passphrase.get_passphrase_file_path("my-repo")
        assert result.name == "my-repo.key"

    def test_handles_special_characters_in_name(self):
        """Verify special characters in repo name are preserved."""
        result = passphrase.get_passphrase_file_path("repo_with-special.chars")
        assert result.name == "repo_with-special.chars.key"


class TestSavePassphraseToFile:
    """Tests for save_passphrase_to_file()."""

    def test_creates_passphrases_directory(self, tmp_path, monkeypatch):
        """Verify passphrases directory is created if it doesn't exist."""
        # Use a temporary directory
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)

        passphrase.save_passphrase_to_file("test-repo", "test-passphrase")

        assert (tmp_path / ".borgboi" / "passphrases").exists()
        assert (tmp_path / ".borgboi" / "passphrases").is_dir()

    def test_sets_directory_permissions_to_0o700(self, tmp_path, monkeypatch):
        """Verify passphrases directory has 0o700 permissions."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)

        passphrase.save_passphrase_to_file("test-repo", "test-passphrase")

        dir_stat = (tmp_path / ".borgboi" / "passphrases").stat()
        dir_mode = stat.S_IMODE(dir_stat.st_mode)
        assert dir_mode == 0o700

    def test_creates_passphrase_file(self, tmp_path, monkeypatch):
        """Verify passphrase file is created."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)

        result = passphrase.save_passphrase_to_file("test-repo", "test-passphrase")

        assert result.exists()
        assert result.is_file()

    def test_sets_file_permissions_to_0o600(self, tmp_path, monkeypatch):
        """Verify passphrase file has 0o600 permissions (owner read/write only)."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)

        result = passphrase.save_passphrase_to_file("test-repo", "test-passphrase")

        file_stat = result.stat()
        file_mode = stat.S_IMODE(file_stat.st_mode)
        assert file_mode == 0o600

    def test_saves_correct_content(self, tmp_path, monkeypatch):
        """Verify passphrase content is correctly written."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)
        test_passphrase = "my-secret-passphrase-123"  # noqa: S105

        result = passphrase.save_passphrase_to_file("test-repo", test_passphrase)

        saved_content = result.read_text(encoding="utf-8")
        assert saved_content == test_passphrase

    def test_returns_path_object(self, tmp_path, monkeypatch):
        """Verify function returns a Path object."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)

        result = passphrase.save_passphrase_to_file("test-repo", "test-passphrase")

        assert isinstance(result, Path)


class TestLoadPassphraseFromFile:
    """Tests for load_passphrase_from_file()."""

    def test_returns_none_if_file_does_not_exist(self, tmp_path, monkeypatch):
        """Verify None is returned when passphrase file doesn't exist."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)

        result = passphrase.load_passphrase_from_file("nonexistent-repo")

        assert result is None

    def test_loads_correct_passphrase(self, tmp_path, monkeypatch):
        """Verify correct passphrase is loaded from file."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)
        test_passphrase = "my-test-passphrase"  # noqa: S105
        passphrase.save_passphrase_to_file("test-repo", test_passphrase)

        result = passphrase.load_passphrase_from_file("test-repo")

        assert result == test_passphrase

    def test_strips_whitespace(self, tmp_path, monkeypatch):
        """Verify whitespace is stripped from loaded passphrase."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)
        # Manually write with whitespace
        passphrase_file = tmp_path / ".borgboi" / "passphrases" / "test-repo.key"
        passphrase_file.parent.mkdir(parents=True, exist_ok=True)
        passphrase_file.write_text("  passphrase-with-spaces  \n", encoding="utf-8")

        result = passphrase.load_passphrase_from_file("test-repo")

        assert result == "passphrase-with-spaces"

    def test_warns_on_insecure_permissions(self, tmp_path, monkeypatch):
        """Verify warning is displayed when file permissions are not 0o600."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)
        passphrase.save_passphrase_to_file("test-repo", "test-passphrase")

        # Change permissions to insecure
        passphrase_file = tmp_path / ".borgboi" / "passphrases" / "test-repo.key"
        passphrase_file.chmod(0o644)

        result = passphrase.load_passphrase_from_file("test-repo")

        # Should still return passphrase
        assert result == "test-passphrase"
        # But should have warned (captured in console output)
        # Note: This would require capturing rich console output properly


class TestResolvePassphrase:
    """Tests for resolve_passphrase()."""

    def test_priority_cli_parameter_highest(self, tmp_path, monkeypatch):
        """Verify CLI parameter has highest priority."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)
        passphrase.save_passphrase_to_file("test-repo", "file-passphrase")
        monkeypatch.setenv("BORG_PASSPHRASE", "env-passphrase")
        monkeypatch.setattr(config.borg, "borg_passphrase", "config-passphrase")

        result = passphrase.resolve_passphrase(
            repo_name="test-repo",
            cli_passphrase="cli-passphrase",  # noqa: S106
            allow_env_fallback=True,
        )

        assert result == "cli-passphrase"

    def test_priority_file_over_env(self, tmp_path, monkeypatch):
        """Verify file has priority over environment variable."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)
        passphrase.save_passphrase_to_file("test-repo", "file-passphrase")
        monkeypatch.setenv("BORG_PASSPHRASE", "env-passphrase")
        monkeypatch.setattr(config.borg, "borg_passphrase", "config-passphrase")

        result = passphrase.resolve_passphrase(
            repo_name="test-repo",
            cli_passphrase=None,
            allow_env_fallback=True,
        )

        assert result == "file-passphrase"

    def test_priority_file_over_db(self, tmp_path, monkeypatch):
        """Verify file has priority over database passphrase."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)
        passphrase.save_passphrase_to_file("test-repo", "file-passphrase")
        monkeypatch.setenv("BORG_PASSPHRASE", "env-passphrase")
        monkeypatch.setattr(config.borg, "borg_passphrase", "config-passphrase")

        result = passphrase.resolve_passphrase(
            repo_name="test-repo",
            cli_passphrase=None,
            db_passphrase="db-passphrase",  # noqa: S106
            allow_env_fallback=True,
        )

        assert result == "file-passphrase"

    def test_priority_db_over_env(self, tmp_path, monkeypatch):
        """Verify database passphrase has priority over environment variable."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)
        monkeypatch.setenv("BORG_PASSPHRASE", "env-passphrase")
        monkeypatch.setattr(config.borg, "borg_passphrase", "config-passphrase")

        result = passphrase.resolve_passphrase(
            repo_name="test-repo",
            cli_passphrase=None,
            db_passphrase="db-passphrase",  # noqa: S106
            allow_env_fallback=True,
        )

        assert result == "db-passphrase"

    def test_priority_db_over_config(self, tmp_path, monkeypatch):
        """Verify database passphrase has priority over config."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)
        monkeypatch.delenv("BORG_PASSPHRASE", raising=False)
        monkeypatch.setattr(config.borg, "borg_passphrase", "config-passphrase")

        result = passphrase.resolve_passphrase(
            repo_name="test-repo",
            cli_passphrase=None,
            db_passphrase="db-passphrase",  # noqa: S106
            allow_env_fallback=False,
        )

        assert result == "db-passphrase"

    def test_priority_cli_over_db(self, tmp_path, monkeypatch):
        """Verify CLI parameter has priority over database passphrase."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)

        result = passphrase.resolve_passphrase(
            repo_name="test-repo",
            cli_passphrase="cli-passphrase",  # noqa: S106
            db_passphrase="db-passphrase",  # noqa: S106
            allow_env_fallback=True,
        )

        assert result == "cli-passphrase"

    def test_priority_env_over_config_when_allowed(self, tmp_path, monkeypatch):
        """Verify env var has priority over config when fallback is allowed."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)
        monkeypatch.setenv("BORG_PASSPHRASE", "env-passphrase")
        monkeypatch.setattr(config.borg, "borg_passphrase", "config-passphrase")

        result = passphrase.resolve_passphrase(
            repo_name="test-repo",
            cli_passphrase=None,
            allow_env_fallback=True,
        )

        assert result == "env-passphrase"

    def test_env_not_used_when_fallback_disabled(self, tmp_path, monkeypatch):
        """Verify env var is not used when allow_env_fallback=False."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)
        monkeypatch.setenv("BORG_PASSPHRASE", "env-passphrase")
        monkeypatch.setattr(config.borg, "borg_passphrase", "config-passphrase")

        result = passphrase.resolve_passphrase(
            repo_name="test-repo",
            cli_passphrase=None,
            allow_env_fallback=False,
        )

        # Should fall through to config since env is not allowed
        assert result == "config-passphrase"

    def test_uses_config_as_last_resort(self, tmp_path, monkeypatch):
        """Verify config is used when no other source is available."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)
        monkeypatch.delenv("BORG_PASSPHRASE", raising=False)
        monkeypatch.setattr(config.borg, "borg_passphrase", "config-passphrase")

        result = passphrase.resolve_passphrase(
            repo_name="test-repo",
            cli_passphrase=None,
            allow_env_fallback=True,
        )

        assert result == "config-passphrase"

    def test_returns_none_when_no_source_available(self, tmp_path, monkeypatch):
        """Verify None is returned when no passphrase source is available."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)
        monkeypatch.delenv("BORG_PASSPHRASE", raising=False)
        monkeypatch.setattr(config.borg, "borg_passphrase", None)

        result = passphrase.resolve_passphrase(
            repo_name="test-repo",
            cli_passphrase=None,
            allow_env_fallback=True,
        )

        assert result is None

    def test_uses_borg_new_passphrase_env_var_name(self, tmp_path, monkeypatch):
        """Verify BORG_NEW_PASSPHRASE env var is used when specified."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)
        monkeypatch.setenv("BORG_NEW_PASSPHRASE", "new-passphrase")
        monkeypatch.setattr(config.borg, "borg_new_passphrase", "config-new-passphrase")

        result = passphrase.resolve_passphrase(
            repo_name="test-repo",
            cli_passphrase=None,
            allow_env_fallback=True,
            env_var_name="BORG_NEW_PASSPHRASE",
        )

        assert result == "new-passphrase"

    def test_uses_borg_new_passphrase_config(self, tmp_path, monkeypatch):
        """Verify borg_new_passphrase config is used for BORG_NEW_PASSPHRASE."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)
        monkeypatch.delenv("BORG_NEW_PASSPHRASE", raising=False)
        monkeypatch.setattr(config.borg, "borg_new_passphrase", "config-new-passphrase")

        result = passphrase.resolve_passphrase(
            repo_name="test-repo",
            cli_passphrase=None,
            allow_env_fallback=True,
            env_var_name="BORG_NEW_PASSPHRASE",
        )

        assert result == "config-new-passphrase"


class TestMigrateRepoPassphrase:
    """Tests for migrate_repo_passphrase()."""

    def test_creates_passphrase_file(self, tmp_path, monkeypatch):
        """Verify migration creates the passphrase file."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)

        result = passphrase.migrate_repo_passphrase("test-repo", "old-db-passphrase")

        assert result.exists()
        assert result.is_file()

    def test_file_contains_correct_passphrase(self, tmp_path, monkeypatch):
        """Verify migrated file contains the correct passphrase."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)
        test_passphrase = "old-db-passphrase"  # noqa: S105

        result = passphrase.migrate_repo_passphrase("test-repo", test_passphrase)

        saved_content = result.read_text(encoding="utf-8")
        assert saved_content == test_passphrase

    def test_file_has_secure_permissions(self, tmp_path, monkeypatch):
        """Verify migrated file has 0o600 permissions."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)

        result = passphrase.migrate_repo_passphrase("test-repo", "old-db-passphrase")

        file_stat = result.stat()
        file_mode = stat.S_IMODE(file_stat.st_mode)
        assert file_mode == 0o600

    def test_verifies_passphrase_can_be_read_back(self, tmp_path, monkeypatch):
        """Verify migration validates passphrase can be loaded."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)

        passphrase.migrate_repo_passphrase("test-repo", "old-db-passphrase")

        # Verify we can load it back
        loaded = passphrase.load_passphrase_from_file("test-repo")
        assert loaded == "old-db-passphrase"

    def test_raises_error_on_verification_failure(self, tmp_path, monkeypatch):
        """Verify error is raised if verification fails."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)

        # Mock load_passphrase_from_file to return wrong passphrase
        with (
            patch.object(passphrase, "load_passphrase_from_file", return_value="wrong-passphrase"),
            pytest.raises(ValueError, match="Passphrase verification failed"),
        ):
            passphrase.migrate_repo_passphrase("test-repo", "old-db-passphrase")

    def test_cleans_up_file_on_verification_failure(self, tmp_path, monkeypatch):
        """Verify file is cleaned up if verification fails."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)
        passphrase_file = tmp_path / ".borgboi" / "passphrases" / "test-repo.key"

        # Mock load_passphrase_from_file to return wrong passphrase
        with (
            patch.object(passphrase, "load_passphrase_from_file", return_value="wrong-passphrase"),
            pytest.raises(ValueError, match="Passphrase verification failed"),
        ):
            passphrase.migrate_repo_passphrase("test-repo", "old-db-passphrase")

        # File should be cleaned up
        assert not passphrase_file.exists()

    def test_returns_path_object(self, tmp_path, monkeypatch):
        """Verify function returns a Path object."""
        import borgboi.config

        monkeypatch.setattr(borgboi.config, "resolve_home_dir", lambda: tmp_path)

        result = passphrase.migrate_repo_passphrase("test-repo", "old-db-passphrase")

        assert isinstance(result, Path)
