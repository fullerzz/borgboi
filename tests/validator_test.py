from pathlib import Path

import pytest
from pydantic import ValidationError

from borgboi.clients.utils.borg_logs import ArchiveProgress, LogMessage
from borgboi.models import BorgBoiRepo
from borgboi.validator import (
    exclude_list_created,
    metadata_is_present,
    parse_log,
    parse_logs,
    repo_is_local,
    valid_line,
)


class TestMetadataIsPresent:
    """Test cases for metadata_is_present function."""

    def test_metadata_is_present_true(self, borg_repo: BorgBoiRepo) -> None:
        """Test that function returns True when metadata is present."""
        # borg_repo fixture has metadata
        assert metadata_is_present(borg_repo) is True

    def test_metadata_is_present_false(self, borg_repo_without_excludes: BorgBoiRepo) -> None:
        """Test that function returns False when metadata is None."""
        repo = borg_repo_without_excludes
        repo.metadata = None
        assert metadata_is_present(repo) is False


class TestRepoIsLocal:
    """Test cases for repo_is_local function."""

    def test_repo_is_local_true(self, borg_repo: BorgBoiRepo, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that function returns True for local repository."""
        monkeypatch.setattr("socket.gethostname", lambda: borg_repo.hostname)
        assert repo_is_local(borg_repo) is True

    def test_repo_is_local_false(self, borg_repo: BorgBoiRepo, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that function returns False for remote repository."""
        monkeypatch.setattr("socket.gethostname", lambda: "different-hostname")
        assert repo_is_local(borg_repo) is False

    def test_repo_is_local_with_mock_table_item(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that function works with objects that have hostname attribute."""

        # Create a simple mock object with hostname attribute
        class MockTableItem:
            def __init__(self, hostname: str):
                self.hostname: str = hostname

        table_item = MockTableItem("test-host")

        monkeypatch.setattr("socket.gethostname", lambda: "test-host")
        assert repo_is_local(table_item) is True  # pyright: ignore[reportArgumentType]

        monkeypatch.setattr("socket.gethostname", lambda: "other-host")
        assert repo_is_local(table_item) is False  # pyright: ignore[reportArgumentType]


class TestExcludeListCreated:
    """Test cases for exclude_list_created function."""

    def test_exclude_list_created_true(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that function returns True when exclude file exists."""
        from borgboi.models import BORGBOI_DIR_NAME, EXCLUDE_FILENAME

        # Create the borgboi directory and exclude file
        borgboi_dir: Path = tmp_path / BORGBOI_DIR_NAME
        borgboi_dir.mkdir()
        exclude_file: Path = borgboi_dir / f"test-repo_{EXCLUDE_FILENAME}"
        _ = exclude_file.write_text("*.tmp\n")

        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        assert exclude_list_created("test-repo") is True

    def test_exclude_list_created_false(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that function returns False when exclude file doesn't exist."""
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
        assert exclude_list_created("nonexistent-repo") is False


class TestParseLog:
    """Test cases for parse_log function."""

    def test_parse_log_archive_progress(self) -> None:
        """Test parsing ArchiveProgress log message."""
        # Use the actual ArchiveProgress model structure - needs finished field
        log_json = '{"original_size": 1000, "compressed_size": 500, "deduplicated_size": 300, "nfiles": 10, "path": "/test/path", "time": 1234567890.0, "finished": true}'

        result = parse_log(log_json)
        assert isinstance(result, ArchiveProgress)
        assert result.original_size == 1000
        assert result.compressed_size == 500
        assert result.nfiles == 10

    def test_parse_log_function_exists(self) -> None:
        """Test that parse_log function exists and handles valid LogMessage."""
        # Test with a valid LogMessage since the parsing order seems to prioritize ArchiveProgress
        log_json = '{"levelname": "INFO", "name": "borg", "message": "Test message", "time": 1234567890.0}'

        result = parse_log(log_json)
        assert isinstance(result, LogMessage)
        assert result.levelname == "INFO"
        assert result.message == "Test message"

    def test_parse_log_generic_message(self) -> None:
        """Test parsing generic LogMessage."""
        # Use the actual LogMessage model structure
        log_json = '{"levelname": "INFO", "name": "borg", "message": "Test message", "time": 1234567890.0}'

        result = parse_log(log_json)
        assert isinstance(result, LogMessage)
        assert result.levelname == "INFO"
        assert result.message == "Test message"

    def test_parse_log_invalid_json(self) -> None:
        """Test that invalid JSON raises ValidationError."""
        with pytest.raises(ValidationError):
            _ = parse_log("invalid json")

    def test_parse_log_unknown_type(self) -> None:
        """Test parsing unknown log type falls back to LogMessage."""
        # Use the actual LogMessage model structure
        log_json = '{"levelname": "DEBUG", "name": "test", "message": "Unknown", "time": 1234567890.0}'

        result = parse_log(log_json)
        assert isinstance(result, LogMessage)


class TestParseLogs:
    """Test cases for parse_logs function."""

    def test_parse_logs_log_messages(self) -> None:
        """Test parsing multiple LogMessage entries."""
        log_stream = [
            '{"levelname": "INFO", "name": "borg", "message": "Test message 1", "time": 1234567890.0}',
            '{"levelname": "ERROR", "name": "borg", "message": "Test message 2", "time": 1234567890.0}',
        ]

        results = list(parse_logs(log_stream))
        assert len(results) == 2
        assert isinstance(results[0], LogMessage)
        assert isinstance(results[1], LogMessage)

    def test_parse_logs_empty_stream(self) -> None:
        """Test parsing empty log stream."""
        results = list(parse_logs([]))
        assert len(results) == 0

    def test_parse_logs_invalid_entries(self) -> None:
        """Test that invalid log entries are handled gracefully."""
        log_stream = [
            '{"original_size": 1000, "compressed_size": 500, "deduplicated_size": 300, "nfiles": 10, "path": "/test", "time": 1234567890.0}',
            "invalid json",  # This should fall back to LogMessage validation
            '{"levelname": "ERROR", "name": "borg", "message": "Error occurred", "time": 1234567890.0}',
        ]

        # The invalid JSON should cause a ValidationError that's not caught
        with pytest.raises(ValidationError):
            _ = list(parse_logs(log_stream))


class TestValidLine:
    """Test cases for valid_line function."""

    def test_valid_line_valid_indices(self) -> None:
        """Test that valid line numbers return True."""
        lines = ["line 1", "line 2", "line 3", "line 4"]

        assert valid_line(lines, 1) is True  # First line
        assert valid_line(lines, 2) is True  # Middle line
        assert valid_line(lines, 4) is True  # Last line

    def test_valid_line_invalid_indices(self) -> None:
        """Test that invalid line numbers return False."""
        lines = ["line 1", "line 2", "line 3"]

        assert valid_line(lines, 0) is False  # Zero index
        assert valid_line(lines, -1) is False  # Negative index
        assert valid_line(lines, 4) is False  # Beyond list length

    def test_valid_line_empty_list(self) -> None:
        """Test that any line number is invalid for empty list."""
        lines: list[str] = []

        assert valid_line(lines, 1) is False
        assert valid_line(lines, 0) is False
        assert valid_line(lines, -1) is False

    def test_valid_line_single_item(self) -> None:
        """Test validation with single item list."""
        lines = ["only line"]

        assert valid_line(lines, 1) is True
        assert valid_line(lines, 0) is False
        assert valid_line(lines, 2) is False
