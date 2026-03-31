import sys
from collections.abc import Generator
from types import SimpleNamespace

import pytest

from borgboi.clients.borg_client import BorgClient
from borgboi.config import BorgConfig
from borgboi.core.output import SilentOutputHandler


def test_create_defaults_to_config_compression(monkeypatch: pytest.MonkeyPatch) -> None:
    config = BorgConfig(compression="lz4")
    client = BorgClient(config=config)
    captured_cmd: list[str] = []

    def fake_run_streaming_command(cmd: list[str], passphrase: str | None = None) -> Generator[str]:
        nonlocal captured_cmd
        captured_cmd = cmd
        if False:
            yield ""

    monkeypatch.setattr(client, "_run_streaming_command", fake_run_streaming_command)

    list(client.create("/repo", "/backup", archive_name="test-archive"))

    assert captured_cmd
    assert f"--compression={config.compression}" in captured_cmd
    assert "--compression=zstd,1" not in captured_cmd


# -- _run_streaming_command line-ending tests ----------------------------------
# Borg progress messages use \r to overwrite the current terminal line.
# The TextIOWrapper in _run_streaming_command must split on \r, \n, and \r\n
# so each progress tick becomes its own yielded line.


def _make_client() -> BorgClient:
    """Create a BorgClient with silent output for testing."""
    return BorgClient(output_handler=SilentOutputHandler())


@pytest.mark.parametrize(
    ("script", "expected"),
    [
        pytest.param(
            r"import sys; sys.stderr.buffer.write(b'alpha\nbeta\ngamma\n')",
            ["alpha\n", "beta\n", "gamma\n"],
            id="newline",
        ),
        pytest.param(
            r"import sys; sys.stderr.buffer.write(b'tick1\rtick2\rtick3\r')",
            ["tick1\n", "tick2\n", "tick3\n"],
            id="carriage-return",
        ),
        pytest.param(
            r"import sys; sys.stderr.buffer.write(b'line1\r\nline2\r\n')",
            ["line1\n", "line2\n"],
            id="crlf",
        ),
        pytest.param(
            r"import sys; sys.stderr.buffer.write(b'progress\rinfo\nwarn\r\ndone\n')",
            ["progress\n", "info\n", "warn\n", "done\n"],
            id="mixed",
        ),
    ],
)
def test_streaming_command_splits_on_all_line_endings(
    script: str,
    expected: list[str],
) -> None:
    """_run_streaming_command must correctly split \\r, \\n, and \\r\\n."""
    client = _make_client()
    cmd = [sys.executable, "-c", script]
    lines = list(client._run_streaming_command(cmd))
    assert lines == expected


def test_set_storage_quota_uses_borg_config(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BorgClient(config=BorgConfig(executable_path="borg"), output_handler=SilentOutputHandler())
    captured: dict[str, object] = {}
    test_passphrase = "secret"  # noqa: S105

    def fake_run_command(
        cmd: list[str],
        passphrase: str | None = None,
        capture_output: bool = True,
    ) -> object:
        captured["cmd"] = cmd
        captured["passphrase"] = passphrase
        captured["capture_output"] = capture_output
        return object()

    monkeypatch.setattr(client, "_run_command", fake_run_command)

    client.set_storage_quota("/repo", "200G", passphrase=test_passphrase)

    assert captured["cmd"] == [
        "borg",
        "config",
        "--log-json",
        "--progress",
        "/repo",
        "storage_quota",
        "200G",
    ]
    assert captured["passphrase"] == test_passphrase


def test_get_additional_free_space_reads_borg_config(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BorgClient(config=BorgConfig(executable_path="borg"), output_handler=SilentOutputHandler())
    captured: dict[str, object] = {}

    def fake_run_command(
        cmd: list[str],
        passphrase: str | None = None,
        capture_output: bool = True,
    ) -> SimpleNamespace:
        captured["cmd"] = cmd
        captured["passphrase"] = passphrase
        captured["capture_output"] = capture_output
        return SimpleNamespace(stdout="2G\n")

    monkeypatch.setattr(client, "_run_command", fake_run_command)

    assert client.get_additional_free_space("/repo") == "2G"
    assert captured["cmd"] == ["borg", "config", "/repo", "additional_free_space"]
    assert captured["passphrase"] is None
    assert captured["capture_output"] is True


def test_get_storage_quota_treats_zero_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BorgClient(config=BorgConfig(executable_path="borg"), output_handler=SilentOutputHandler())
    captured: dict[str, object] = {}

    def fake_run_command(
        cmd: list[str],
        passphrase: str | None = None,
        capture_output: bool = True,
    ) -> SimpleNamespace:
        captured["cmd"] = cmd
        captured["passphrase"] = passphrase
        captured["capture_output"] = capture_output
        return SimpleNamespace(stdout="0\n")

    monkeypatch.setattr(client, "_run_command", fake_run_command)

    assert client.get_storage_quota("/repo") is None
    assert captured["cmd"] == ["borg", "config", "/repo", "storage_quota"]
    assert captured["passphrase"] is None
    assert captured["capture_output"] is True
