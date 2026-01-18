from collections.abc import Generator

import pytest

from borgboi.clients.borg_client import BorgClient
from borgboi.config import BorgConfig


def test_create_defaults_to_config_compression(monkeypatch: pytest.MonkeyPatch) -> None:
    config = BorgConfig(compression="lz4")
    client = BorgClient(config=config)
    captured_cmd: list[str] = []

    def fake_run_streaming_command(cmd: list[str], passphrase: str | None = None) -> Generator[str, None, None]:
        nonlocal captured_cmd
        captured_cmd = cmd
        if False:
            yield ""

    monkeypatch.setattr(client, "_run_streaming_command", fake_run_streaming_command)

    list(client.create("/repo", "/backup", archive_name="test-archive"))

    assert captured_cmd
    assert f"--compression={config.compression}" in captured_cmd
    assert "--compression=zstd,1" not in captured_cmd
