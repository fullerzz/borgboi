import sys
from collections.abc import Generator

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
    ("label", "script", "expected"),
    [
        pytest.param(
            "newline",
            r"import sys; sys.stderr.buffer.write(b'alpha\nbeta\ngamma\n')",
            ["alpha\n", "beta\n", "gamma\n"],
            id="newline",
        ),
        pytest.param(
            "carriage_return",
            r"import sys; sys.stderr.buffer.write(b'tick1\rtick2\rtick3\r')",
            ["tick1\n", "tick2\n", "tick3\n"],
            id="carriage-return",
        ),
        pytest.param(
            "crlf",
            r"import sys; sys.stderr.buffer.write(b'line1\r\nline2\r\n')",
            ["line1\n", "line2\n"],
            id="crlf",
        ),
        pytest.param(
            "mixed",
            r"import sys; sys.stderr.buffer.write(b'progress\rinfo\nwarn\r\ndone\n')",
            ["progress\n", "info\n", "warn\n", "done\n"],
            id="mixed",
        ),
    ],
)
def test_streaming_command_splits_on_all_line_endings(
    label: str,
    script: str,
    expected: list[str],
) -> None:
    """_run_streaming_command must correctly split \\r, \\n, and \\r\\n."""
    client = _make_client()
    cmd = [sys.executable, "-c", script]
    lines = list(client._run_streaming_command(cmd))
    assert lines == expected
