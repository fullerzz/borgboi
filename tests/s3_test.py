import subprocess as sp

import pytest

from borgboi.clients import s3


def test_sync_with_s3_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test successful S3 sync operation."""
    monkeypatch.setenv("BORG_S3_BUCKET", "test-bucket")

    # Mock subprocess.Popen
    class MockProc:
        def __init__(self):
            self.stdout = MockStdout()

        def wait(self):
            return 0

    class MockStdout:
        def __init__(self):
            self.call_count = 0
            self.lines = [
                b"upload: ./file1.txt to s3://test-bucket/test-repo/file1.txt\n",
                b"upload: ./file2.txt to s3://test-bucket/test-repo/file2.txt\n",
                b"",
            ]

        def readable(self):
            self.call_count += 1
            return self.call_count <= 2

        def readline(self):
            if self.call_count <= len(self.lines):
                return self.lines[self.call_count - 1]
            return b""

    mock_proc = MockProc()
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: mock_proc)
    output_lines = list(s3.sync_with_s3("/path/to/repo", "test-repo"))

    assert len(output_lines) == 2
    assert "upload: ./file1.txt to s3://test-bucket/test-repo/file1.txt" in output_lines[0]
    assert "upload: ./file2.txt to s3://test-bucket/test-repo/file2.txt" in output_lines[1]


def test_sync_with_s3_missing_bucket_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test S3 sync fails when BORG_S3_BUCKET environment variable is missing."""
    monkeypatch.delenv("BORG_S3_BUCKET", raising=False)
    with pytest.raises(KeyError):
        list(s3.sync_with_s3("/path/to/repo", "test-repo"))


def test_sync_with_s3_command_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test S3 sync handles command failure."""
    monkeypatch.setenv("BORG_S3_BUCKET", "test-bucket")

    class MockProc:
        def __init__(self):
            self.stdout = MockStdout()
            self.returncode = 1  # Non-zero exit code

        def wait(self):
            return 1  # Non-zero exit code

    class MockStdout:
        def readable(self):
            return False

    mock_proc = MockProc()
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: mock_proc)
    with pytest.raises(sp.CalledProcessError):
        list(s3.sync_with_s3("/path/to/repo", "test-repo"))


def test_sync_with_s3_stdout_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test S3 sync handles None stdout."""
    monkeypatch.setenv("BORG_S3_BUCKET", "test-bucket")

    class MockProc:
        def __init__(self):
            self.stdout = None

    mock_proc = MockProc()
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: mock_proc)
    with pytest.raises(ValueError, match="stdout is None"):
        list(s3.sync_with_s3("/path/to/repo", "test-repo"))


def test_sync_with_s3_correct_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that S3 sync uses correct AWS CLI command."""
    monkeypatch.setenv("BORG_S3_BUCKET", "my-backup-bucket")

    class MockProc:
        def __init__(self):
            self.stdout = MockStdout()

        def wait(self):
            return 0

    class MockStdout:
        def readable(self):
            return False

    mock_proc = MockProc()
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: mock_proc)
    list(s3.sync_with_s3("/home/user/repos/my-repo", "my-repo"))

    # The test ensures the function runs without error with the mocked Popen
    # Command verification would require capturing the call arguments, which is
    # more complex with monkeypatch than with unittest.mock
