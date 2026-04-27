from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from opentelemetry import trace
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags, TraceState, use_span

from borgboi.config import Config, TelemetryConfig
from borgboi.tui.support.telemetry import capture_span

from .conftest import FakeTracer


class _ConfigMethodHost:
    def __init__(self, config: Config | None) -> None:
        self._config = config

    @capture_span("tui.test.sync")
    def run(self, value: str) -> str:
        return value.upper()

    @capture_span("tui.test.explode")
    def explode(self) -> None:
        raise RuntimeError("boom")

    @capture_span("tui.test.current-span")
    def current_span_is_valid(self) -> bool:
        return trace.get_current_span().get_span_context().is_valid


class _AsyncConfigMethodHost:
    def __init__(self, config: Config | None) -> None:
        self._config = config

    @capture_span("tui.test.async")
    async def run(self, value: str) -> str:
        return value.upper()


class _OrchestratorMethodHost:
    def __init__(self, config: Config) -> None:
        self._orchestrator = SimpleNamespace(config=config)

    @capture_span("tui.test.orchestrator")
    def run(self) -> str:
        return "ok"


class _AppMethodHost:
    def __init__(self, config: Config) -> None:
        self.app = SimpleNamespace(_config=config)

    @capture_span("tui.test.app")
    def run(self) -> str:
        return "ok"


def test_capture_span_wraps_sync_methods(fake_tui_tracer: FakeTracer) -> None:
    host = _ConfigMethodHost(Config(telemetry=TelemetryConfig(enabled=True, capture_tui=True)))

    assert host.run("alpha") == "ALPHA"
    assert fake_tui_tracer.started_spans == ["tui.test.sync"]
    assert host.run.__name__ == "run"
    assert cast("Any", host.run).__wrapped__.__name__ == "run"


@pytest.mark.asyncio
async def test_capture_span_wraps_async_methods(fake_tui_tracer: FakeTracer) -> None:
    host = _AsyncConfigMethodHost(Config(telemetry=TelemetryConfig(enabled=True, capture_tui=True)))

    assert await host.run("beta") == "BETA"
    assert fake_tui_tracer.started_spans == ["tui.test.async"]


def test_capture_span_uses_orchestrator_config(fake_tui_tracer: FakeTracer) -> None:
    host = _OrchestratorMethodHost(Config(telemetry=TelemetryConfig(enabled=True, capture_tui=True)))

    assert host.run() == "ok"
    assert fake_tui_tracer.started_spans == ["tui.test.orchestrator"]


def test_capture_span_uses_app_config(fake_tui_tracer: FakeTracer) -> None:
    host = _AppMethodHost(Config(telemetry=TelemetryConfig(enabled=True, capture_tui=True)))

    assert host.run() == "ok"
    assert fake_tui_tracer.started_spans == ["tui.test.app"]


def test_capture_span_skips_when_tui_capture_disabled(fake_tui_tracer: FakeTracer) -> None:
    host = _ConfigMethodHost(Config(telemetry=TelemetryConfig(capture_tui=False)))

    assert host.run("gamma") == "GAMMA"
    assert fake_tui_tracer.started_spans == []


def test_capture_span_skips_when_telemetry_disabled(fake_tui_tracer: FakeTracer) -> None:
    host = _ConfigMethodHost(Config(telemetry=TelemetryConfig(enabled=False, capture_tui=True)))

    assert host.run("gamma") == "GAMMA"
    assert fake_tui_tracer.started_spans == []


def test_capture_span_tolerates_missing_config(fake_tui_tracer: FakeTracer) -> None:
    host = _ConfigMethodHost(None)

    assert host.run("delta") == "DELTA"
    assert fake_tui_tracer.started_spans == []


def test_capture_span_preserves_exceptions(fake_tui_tracer: FakeTracer) -> None:
    host = _ConfigMethodHost(Config(telemetry=TelemetryConfig(enabled=True, capture_tui=True)))

    with pytest.raises(RuntimeError, match="boom"):
        host.explode()

    assert fake_tui_tracer.started_spans == ["tui.test.explode"]


def test_capture_span_disabled_blocks_parent_span_leak(fake_tui_tracer: FakeTracer) -> None:
    host = _ConfigMethodHost(Config(telemetry=TelemetryConfig(capture_tui=False)))

    span_context = SpanContext(
        trace_id=int("1234" * 8, 16),
        span_id=int("abcd" * 4, 16),
        is_remote=False,
        trace_flags=TraceFlags(0x01),
        trace_state=TraceState(),
    )

    with use_span(NonRecordingSpan(span_context), end_on_exit=False):
        assert host.current_span_is_valid() is False

    assert fake_tui_tracer.started_spans == []
