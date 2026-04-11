"""Tests for borgboi OpenTelemetry configuration helpers."""

from __future__ import annotations

import logging as stdlib_logging
from collections.abc import Generator
from typing import cast

import pytest

from borgboi.config import Config, TelemetryConfig
from borgboi.core import telemetry
from borgboi.core.telemetry import (
    _OTEL_LOG_HANDLER_NAME,
    _TelemetryState,
    configure_telemetry,
    force_flush_telemetry,
    reset_telemetry_for_tests,
    telemetry_is_active,
)

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture(autouse=True)
def _reset_telemetry_state() -> Generator[None]:
    reset_telemetry_for_tests()
    yield
    reset_telemetry_for_tests()


def test_configure_telemetry_disabled_returns_inactive_session() -> None:
    cfg = Config(telemetry=TelemetryConfig(enabled=False))

    session = configure_telemetry(cfg)

    assert session.enabled is False
    assert session.logs_export_enabled is False
    assert _TelemetryState.logs_initialized is False


def test_configure_telemetry_log_export_uses_default_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _StubExporter:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def shutdown(self) -> None:
            pass

    monkeypatch.setattr(telemetry, "OTLPLogExporter", _StubExporter)

    cfg = Config(telemetry=TelemetryConfig(enabled=True, export_logs=True))
    session = configure_telemetry(cfg)

    assert session.enabled is True
    assert session.logs_export_enabled is True
    assert captured == {}


def test_configure_telemetry_trace_export_uses_default_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _StubExporter:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def shutdown(self) -> None:
            pass

    monkeypatch.setattr(telemetry, "OTLPSpanExporter", _StubExporter)

    cfg = Config(telemetry=TelemetryConfig(enabled=True))
    session = configure_telemetry(cfg)

    assert session.enabled is True
    assert captured == {}


def test_configure_telemetry_trace_export_honors_trace_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _StubExporter:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def shutdown(self) -> None:
            pass

    monkeypatch.setattr(telemetry, "OTLPSpanExporter", _StubExporter)

    trace_endpoint = "http://tempo.example:4318/v1/traces"
    cfg = Config(telemetry=TelemetryConfig(enabled=True, trace_endpoint=trace_endpoint))

    session = configure_telemetry(cfg)

    assert session.enabled is True
    assert cast(str, captured.get("endpoint")) == trace_endpoint


def test_configure_telemetry_log_export_honors_loki_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _StubExporter:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def shutdown(self) -> None:
            pass

    monkeypatch.setattr(telemetry, "OTLPLogExporter", _StubExporter)

    loki_endpoint = "http://loki.example:3100/otlp/v1/logs"
    cfg = Config(
        telemetry=TelemetryConfig(
            enabled=True,
            export_logs=True,
            logs_endpoint=loki_endpoint,
        )
    )

    session = configure_telemetry(cfg)

    assert session.logs_export_enabled is True
    assert cast(str, captured.get("endpoint")) == loki_endpoint


class _RecordingExporter:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs

    def shutdown(self) -> None:
        pass


def test_configure_telemetry_mixed_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    span_calls: list[dict[str, object]] = []
    log_calls: list[dict[str, object]] = []

    class _SpanExporter(_RecordingExporter):
        def __init__(self, **kwargs: object) -> None:
            super().__init__(**kwargs)
            span_calls.append(kwargs)

    class _LogExporter(_RecordingExporter):
        def __init__(self, **kwargs: object) -> None:
            super().__init__(**kwargs)
            log_calls.append(kwargs)

    monkeypatch.setattr(telemetry, "OTLPSpanExporter", _SpanExporter)
    monkeypatch.setattr(telemetry, "OTLPLogExporter", _LogExporter)

    trace_endpoint = "http://tempo.example:4318/v1/traces"
    cfg = Config(
        telemetry=TelemetryConfig(
            enabled=True,
            export_logs=True,
            trace_endpoint=trace_endpoint,
            logs_endpoint=None,
        )
    )

    configure_telemetry(cfg)

    assert len(span_calls) == 1
    assert span_calls[0].get("endpoint") == trace_endpoint
    assert len(log_calls) == 1
    assert "endpoint" not in log_calls[0]


def test_configure_telemetry_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    span_ctor_count = 0

    class _SpanExporter(_RecordingExporter):
        def __init__(self, **kwargs: object) -> None:
            super().__init__(**kwargs)
            nonlocal span_ctor_count
            span_ctor_count += 1

    monkeypatch.setattr(telemetry, "OTLPSpanExporter", _SpanExporter)

    cfg = Config(telemetry=TelemetryConfig(enabled=True))
    configure_telemetry(cfg)
    configure_telemetry(cfg)

    assert span_ctor_count == 1
    assert _TelemetryState.traces_initialized is True


def test_configure_telemetry_attaches_log_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(telemetry, "OTLPLogExporter", _RecordingExporter)

    cfg = Config(telemetry=TelemetryConfig(enabled=True, export_logs=True))
    configure_telemetry(cfg)

    handlers = stdlib_logging.getLogger("borgboi").handlers
    assert any(h.get_name() == _OTEL_LOG_HANDLER_NAME for h in handlers)


def test_configure_telemetry_trace_exporter_failure_degrades(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class _Boom:
        def __init__(self, **_: object) -> None:
            raise RuntimeError("bad endpoint")

    monkeypatch.setattr(telemetry, "OTLPSpanExporter", _Boom)

    cfg = Config(telemetry=TelemetryConfig(enabled=True, trace_endpoint="http://nope"))
    session = configure_telemetry(cfg)

    assert session.enabled is False
    assert session.logs_export_enabled is False
    assert "trace exporter" in capsys.readouterr().err


def test_configure_telemetry_log_exporter_failure_keeps_traces(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(telemetry, "OTLPSpanExporter", _RecordingExporter)

    class _Boom:
        def __init__(self, **_: object) -> None:
            raise RuntimeError("loki down")

    monkeypatch.setattr(telemetry, "OTLPLogExporter", _Boom)

    cfg = Config(
        telemetry=TelemetryConfig(enabled=True, export_logs=True, logs_endpoint="http://nope"),
    )
    session = configure_telemetry(cfg)

    assert session.enabled is True
    assert session.logs_export_enabled is False
    assert "log exporter" in capsys.readouterr().err


def test_force_flush_telemetry_reports_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(telemetry, "OTLPSpanExporter", _RecordingExporter)
    cfg = Config(telemetry=TelemetryConfig(enabled=True))
    configure_telemetry(cfg)

    assert _TelemetryState.tracer_provider is not None
    monkeypatch.setattr(_TelemetryState.tracer_provider, "force_flush", lambda *_args, **_kwargs: False)

    assert force_flush_telemetry() is False
    assert "trace flush timed out" in capsys.readouterr().err


def test_force_flush_telemetry_reports_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(telemetry, "OTLPSpanExporter", _RecordingExporter)
    cfg = Config(telemetry=TelemetryConfig(enabled=True))
    configure_telemetry(cfg)

    assert _TelemetryState.tracer_provider is not None
    monkeypatch.setattr(_TelemetryState.tracer_provider, "force_flush", lambda *_args, **_kwargs: True)

    assert force_flush_telemetry() is True


def test_telemetry_is_active_reflects_process_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(telemetry, "OTLPSpanExporter", _RecordingExporter)

    assert telemetry_is_active() is False

    cfg = Config(telemetry=TelemetryConfig(enabled=True))
    configure_telemetry(cfg)

    assert telemetry_is_active() is True
