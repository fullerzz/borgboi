"""Tests for borgboi OpenTelemetry configuration helpers."""

from __future__ import annotations

from collections.abc import Generator
from typing import cast

import pytest

from borgboi.config import Config, TelemetryConfig
from borgboi.core import telemetry
from borgboi.core.telemetry import _TelemetryState, configure_telemetry, reset_telemetry_for_tests

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
