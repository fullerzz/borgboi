import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import borgboi.cli as cli_package
import borgboi.config as config_module
import borgboi.core.logging as logging_module
from borgboi.config import Config, LoggingConfig, TelemetryConfig
from borgboi.core.telemetry import TelemetrySession, reset_telemetry_for_tests
from tests.cli_helpers import invoke_cli

cli_main = importlib.import_module("borgboi.cli.main")
BorgBoiContext = cli_main.BorgBoiContext
_print_exit_summary = cli_main._print_exit_summary
_resolve_trace_endpoint = cli_main._resolve_trace_endpoint


def _read_active_log_entries() -> list[dict[str, object]]:
    log_file = logging_module._LoggingState.active_log_file
    assert log_file is not None
    return [json.loads(line) for line in log_file.read_text().splitlines() if line.strip()]


def test_help(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = invoke_cli(cli_main.cli, ["--help"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "repo" in captured.out
    assert "backup" in captured.out
    assert "config" in captured.out


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = invoke_cli(cli_main.cli, ["version"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.startswith("borgboi ")


def test_lazy_commands_are_importable() -> None:
    for name in ("repo", "backup", "s3", "exclusions", "config"):
        assert cli_main.app[name] is not None


def test_package_exports_root_app() -> None:
    assert cli_package.app is cli_main.app
    assert cli_package.cli is cli_main.cli


def test_repo_create(
    monkeypatch: pytest.MonkeyPatch,
    repo_storage_dir: Path,
    backup_target_dir: Path,
) -> None:
    class _FakeOrchestrator:
        def __init__(self, config: object) -> None:
            del config

        def create_repo(
            self,
            *,
            path: str,
            backup_target: str,
            name: str,
            passphrase: str | None = None,
        ) -> object:
            _ = backup_target, passphrase
            return SimpleNamespace(path=path, name=name)

    monkeypatch.setattr("borgboi.core.orchestrator.Orchestrator", _FakeOrchestrator)

    exit_code = invoke_cli(
        cli_main.cli,
        [
            "repo",
            "create",
            "--path",
            str(repo_storage_dir),
            "--backup-target",
            str(backup_target_dir),
            "--name",
            "test-repo",
        ],
    )

    assert exit_code == 0


def test_root_offline_flag_is_accepted(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = invoke_cli(cli_main.cli, ["--offline", "s3", "stats"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "offline mode" in captured.out.lower()


def test_cli_logging_redacts_passphrase_tokens(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class _FakeOrchestrator:
        def __init__(self, config: object) -> None:
            del config

        def create_repo(
            self,
            *,
            path: str,
            backup_target: str,
            name: str,
            passphrase: str | None = None,
        ) -> object:
            _ = backup_target, passphrase
            return SimpleNamespace(path=path, name=name)

    monkeypatch.setattr("borgboi.core.orchestrator.Orchestrator", _FakeOrchestrator)
    monkeypatch.setenv("BORGBOI_LOGGING__ENABLED", "true")
    config_module.get_config.cache_clear()
    repo_path = tmp_path / "repo"
    backup_target = tmp_path / "backup-target"

    exit_code = invoke_cli(
        cli_main.cli,
        [
            "repo",
            "create",
            "--path",
            str(repo_path),
            "--backup-target",
            str(backup_target),
            "--name",
            "test-repo",
            "--passphrase",
            "super-secret",
        ],
    )

    assert exit_code == 0

    logs_dir = config_module.resolve_home_dir() / ".borgboi" / "logs"
    log_file = next(logs_dir.glob("borgboi_*.log"))
    log_entries = [json.loads(line) for line in log_file.read_text().splitlines() if line.strip()]
    command_entry = next(entry for entry in log_entries if entry["event"] == "Running CLI command")

    assert command_entry["tokens"][-2:] == ["--passphrase", "[REDACTED]"]
    assert "super-secret" not in log_file.read_text()


def test_repo_create_logs_structured_cli_events(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home_dir = tmp_path / "home"

    class _FakeOrchestrator:
        def __init__(self, config: object) -> None:
            del config

        def create_repo(
            self,
            *,
            path: str,
            backup_target: str,
            name: str,
            passphrase: str | None = None,
        ) -> object:
            _ = backup_target, passphrase
            return SimpleNamespace(path=path, name=name)

    monkeypatch.setattr("borgboi.core.orchestrator.Orchestrator", _FakeOrchestrator)
    monkeypatch.setenv("BORGBOI_HOME", str(home_dir))
    monkeypatch.setenv("BORGBOI_LOGGING__ENABLED", "true")
    monkeypatch.setenv("BORGBOI_DEBUG", "true")
    config_module.get_config.cache_clear()

    repo_path = tmp_path / "repo"
    backup_target = tmp_path / "backup-target"
    exit_code = invoke_cli(
        cli_main.cli,
        [
            "repo",
            "create",
            "--path",
            str(repo_path),
            "--backup-target",
            str(backup_target),
            "--name",
            "test-repo",
        ],
    )

    assert exit_code == 0

    log_entries = _read_active_log_entries()
    assert any(
        entry["event"] == "Running repository create command"
        and entry["logger"] == "borgboi.cli.repo"
        and entry["repo_name"] == "test-repo"
        and entry["repo_path"] == str(repo_path)
        and entry["backup_target"] == str(backup_target)
        for entry in log_entries
    )
    assert any(
        entry["event"] == "Repository create command completed"
        and entry["logger"] == "borgboi.cli.repo"
        and entry["repo_name"] == "test-repo"
        and entry["repo_path"] == str(repo_path)
        for entry in log_entries
    )


def test_s3_stats_logs_offline_skip_warning(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home_dir = tmp_path / "home"

    monkeypatch.setenv("BORGBOI_HOME", str(home_dir))
    monkeypatch.setenv("BORGBOI_LOGGING__ENABLED", "true")
    monkeypatch.setenv("BORGBOI_DEBUG", "true")
    config_module.get_config.cache_clear()

    exit_code = invoke_cli(cli_main.cli, ["--offline", "s3", "stats"])

    assert exit_code == 0

    log_entries = _read_active_log_entries()
    assert any(
        entry["event"] == "Skipping S3 stats command in offline mode"
        and entry["logger"] == "borgboi.cli.s3"
        and entry["level"] == "info"
        for entry in log_entries
    )


def test_cli_flushes_process_telemetry_even_when_current_run_is_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_telemetry_for_tests()
    flush_calls: list[bool] = []

    class _NoOpSpan:
        def __enter__(self) -> "_NoOpSpan":
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            del exc_type, exc, tb

        def set_attribute(self, _key: str, _value: object) -> None:
            pass

    class _NoOpTracer:
        def start_as_current_span(self, _name: str) -> _NoOpSpan:
            return _NoOpSpan()

    monkeypatch.setattr(
        cli_main, "configure_telemetry", lambda _cfg: TelemetrySession(enabled=False, logs_export_enabled=False)
    )
    monkeypatch.setattr(cli_main, "configure_logging", lambda _cfg: None)
    monkeypatch.setattr(cli_main, "telemetry_is_active", lambda: True)

    def _force_flush_telemetry() -> bool:
        flush_calls.append(True)
        return True

    monkeypatch.setattr(cli_main, "force_flush_telemetry", _force_flush_telemetry)
    monkeypatch.setattr(cli_main, "_TRACER", _NoOpTracer())

    exit_code = invoke_cli(cli_main.cli, ["version"])

    assert exit_code == 0
    assert flush_calls == [True]


class TestResolveTraceEndpoint:
    def test_config_wins_over_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://env-traces")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://env-generic")
        cfg = Config(telemetry=TelemetryConfig(enabled=True, trace_endpoint="http://cfg"))

        assert _resolve_trace_endpoint(cfg) == "http://cfg"

    def test_traces_env_beats_generic_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://env-traces")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://env-generic")
        cfg = Config(telemetry=TelemetryConfig(enabled=True))

        assert _resolve_trace_endpoint(cfg) == "http://env-traces"

    def test_generic_env_used_when_traces_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://env-generic")
        cfg = Config(telemetry=TelemetryConfig(enabled=True))

        assert _resolve_trace_endpoint(cfg) == "http://env-generic"

    def test_returns_none_when_nothing_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        cfg = Config(telemetry=TelemetryConfig(enabled=True))

        assert _resolve_trace_endpoint(cfg) is None


class TestPrintExitSummary:
    @pytest.fixture(autouse=True)
    def _clean_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    def _ctx(self) -> Any:
        ctx = BorgBoiContext()
        ctx.trace_id = "fallback-trace"
        return ctx

    def test_silent_when_nothing_enabled(self, capsys: pytest.CaptureFixture[str]) -> None:
        cfg = Config(
            logging=LoggingConfig(enabled=False),
            telemetry=TelemetryConfig(enabled=False),
        )
        _print_exit_summary(
            self._ctx(),
            cfg,
            TelemetrySession(enabled=False, logs_export_enabled=False),
            otel_trace_id=None,
            flush_ok=True,
        )
        assert capsys.readouterr().out == ""

    def test_logging_only_uses_ctx_trace_id_no_suffix(self, capsys: pytest.CaptureFixture[str]) -> None:
        cfg = Config(
            logging=LoggingConfig(enabled=True),
            telemetry=TelemetryConfig(enabled=False),
        )
        _print_exit_summary(
            self._ctx(),
            cfg,
            TelemetrySession(enabled=False, logs_export_enabled=False),
            otel_trace_id=None,
            flush_ok=True,
        )
        out = capsys.readouterr().out
        assert "fallback-trace" in out
        assert "Traces" not in out

    def test_telemetry_only_prefers_otel_trace_id(self, capsys: pytest.CaptureFixture[str]) -> None:
        cfg = Config(
            logging=LoggingConfig(enabled=False),
            telemetry=TelemetryConfig(enabled=True, trace_endpoint="http://tempo"),
        )
        _print_exit_summary(
            self._ctx(),
            cfg,
            TelemetrySession(enabled=True, logs_export_enabled=False),
            otel_trace_id="otel-xyz",
            flush_ok=True,
        )
        out = capsys.readouterr().out
        assert "otel-xyz" in out
        assert "fallback-trace" not in out
        assert "Traces sent to http://tempo" in out

    def test_flush_failure_says_queued(self, capsys: pytest.CaptureFixture[str]) -> None:
        cfg = Config(
            logging=LoggingConfig(enabled=True),
            telemetry=TelemetryConfig(enabled=True, trace_endpoint="http://tempo"),
        )
        _print_exit_summary(
            self._ctx(),
            cfg,
            TelemetrySession(enabled=True, logs_export_enabled=False),
            otel_trace_id="otel-xyz",
            flush_ok=False,
        )
        out = capsys.readouterr().out
        assert "Traces queued for http://tempo" in out
        assert "Traces sent to" not in out

    def test_default_endpoint_message_when_unresolved(self, capsys: pytest.CaptureFixture[str]) -> None:
        cfg = Config(
            logging=LoggingConfig(enabled=True),
            telemetry=TelemetryConfig(enabled=True),
        )
        _print_exit_summary(
            self._ctx(),
            cfg,
            TelemetrySession(enabled=True, logs_export_enabled=False),
            otel_trace_id="otel-xyz",
            flush_ok=True,
        )
        normalized = " ".join(capsys.readouterr().out.split())
        assert "the configured OTLP endpoint" in normalized
        assert "Traces sent to the configured OTLP endpoint" in normalized
