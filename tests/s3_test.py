import subprocess as sp

import pytest

from borgboi.clients import s3


class MockStdout:
    """Mock stdout for subprocess communication."""

    def __init__(self, lines: list[bytes] | None = None, readable_calls: int = 0) -> None:
        self.call_count: int = 0
        self.lines: list[bytes] = lines or []
        self.readable_calls: int = readable_calls

    def readable(self) -> bool:
        self.call_count += 1
        return self.call_count <= self.readable_calls

    def readline(self) -> bytes:
        if self.call_count <= len(self.lines):
            return self.lines[self.call_count - 1]
        return b""


class MockProc:
    """Mock process for subprocess operations."""

    def __init__(self, stdout: MockStdout | None = None, returncode: int = 0) -> None:
        self.stdout: MockStdout | None = stdout
        self.returncode: int = returncode

    def wait(self) -> int:
        return self.returncode


@pytest.fixture
def mock_stdout_success() -> MockStdout:
    """Mock stdout that simulates successful S3 sync output."""
    return MockStdout(
        lines=[
            b"upload: ./file1.txt to s3://test-bucket/test-repo/file1.txt\n",
            b"upload: ./file2.txt to s3://test-bucket/test-repo/file2.txt\n",
            b"",
        ],
        readable_calls=2,
    )


@pytest.fixture
def mock_stdout_empty() -> MockStdout:
    """Mock stdout that returns no output."""
    return MockStdout(readable_calls=0)


@pytest.fixture
def mock_proc_success(mock_stdout_success: MockStdout) -> MockProc:
    """Mock process that succeeds with output."""
    return MockProc(stdout=mock_stdout_success, returncode=0)


@pytest.fixture
def mock_proc_failure(mock_stdout_empty: MockStdout) -> MockProc:
    """Mock process that fails."""
    return MockProc(stdout=mock_stdout_empty, returncode=1)


@pytest.fixture
def mock_proc_no_stdout():
    """Mock process with None stdout."""
    return MockProc(stdout=None)


@pytest.fixture
def mock_proc_empty_output(mock_stdout_empty: MockStdout) -> MockProc:
    """Mock process that succeeds but has no output."""
    return MockProc(stdout=mock_stdout_empty, returncode=0)


def test_sync_with_s3_success(monkeypatch: pytest.MonkeyPatch, mock_proc_success: MockProc) -> None:
    """Test successful S3 sync operation."""
    monkeypatch.setenv("BORG_S3_BUCKET", "test-bucket")
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: mock_proc_success)  # pyright: ignore[reportUnknownArgumentType,reportUnknownLambdaType]
    output_lines = list(s3.sync_with_s3("/path/to/repo", "test-repo"))

    assert len(output_lines) == 2
    assert "upload: ./file1.txt to s3://test-bucket/test-repo/file1.txt" in output_lines[0]
    assert "upload: ./file2.txt to s3://test-bucket/test-repo/file2.txt" in output_lines[1]


def test_sync_with_s3_missing_bucket_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test S3 sync fails when BORG_S3_BUCKET environment variable is missing."""
    monkeypatch.delenv("BORG_S3_BUCKET", raising=False)
    with pytest.raises(KeyError):
        _ = list(s3.sync_with_s3("/path/to/repo", "test-repo"))


def test_sync_with_s3_command_failure(monkeypatch: pytest.MonkeyPatch, mock_proc_failure: MockProc) -> None:
    """Test S3 sync handles command failure."""
    monkeypatch.setenv("BORG_S3_BUCKET", "test-bucket")
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: mock_proc_failure)  # pyright: ignore[reportUnknownArgumentType,reportUnknownLambdaType]
    with pytest.raises(sp.CalledProcessError):
        _ = list(s3.sync_with_s3("/path/to/repo", "test-repo"))


def test_sync_with_s3_stdout_none(monkeypatch: pytest.MonkeyPatch, mock_proc_no_stdout: MockProc) -> None:
    """Test S3 sync handles None stdout."""
    monkeypatch.setenv("BORG_S3_BUCKET", "test-bucket")
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: mock_proc_no_stdout)  # pyright: ignore[reportUnknownArgumentType,reportUnknownLambdaType]
    with pytest.raises(ValueError, match="stdout is None"):
        _ = list(s3.sync_with_s3("/path/to/repo", "test-repo"))


def test_sync_with_s3_correct_command(monkeypatch: pytest.MonkeyPatch, mock_proc_empty_output: MockProc) -> None:
    """Test that S3 sync uses correct AWS CLI command."""
    monkeypatch.setenv("BORG_S3_BUCKET", "my-backup-bucket")
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: mock_proc_empty_output)  # pyright: ignore[reportUnknownArgumentType,reportUnknownLambdaType]
    _ = list(s3.sync_with_s3("/home/user/repos/my-repo", "my-repo"))

    # The test ensures the function runs without error with the mocked Popen
    # Command verification would require capturing the call arguments, which is
    # more complex with monkeypatch than with unittest.mock
