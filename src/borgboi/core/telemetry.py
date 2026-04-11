"""OpenTelemetry bootstrap and helpers for borgboi."""

from __future__ import annotations

import logging as stdlib_logging
import os
import socket
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_version
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span, SpanContext
from opentelemetry.util.types import AttributeValue
from structlog.contextvars import bind_contextvars

if TYPE_CHECKING:
    from collections.abc import Mapping

    from borgboi.config import Config

_LOGGER_NAMESPACE = "borgboi"
_OTEL_LOG_HANDLER_NAME = "borgboi-otel-log-export"


@dataclass(frozen=True)
class TelemetrySession:
    enabled: bool
    logs_export_enabled: bool


class _TelemetryState:
    traces_initialized = False
    logs_initialized = False
    botocore_instrumented = False
    tracer_provider: TracerProvider | None = None
    logger_provider: LoggerProvider | None = None
    log_handler: LoggingHandler | None = None


def _get_service_version() -> str:
    try:
        return get_version("borgboi")
    except PackageNotFoundError:
        return "0.0.0"


def _build_resource(config: Config) -> Resource:
    attributes: dict[str, AttributeValue] = {
        "service.version": _get_service_version(),
        "service.instance.id": socket.gethostname(),
        "borgboi.mode.offline": config.offline,
    }
    if os.getenv("OTEL_SERVICE_NAME") is None:
        attributes["service.name"] = config.telemetry.service_name
    return Resource.create(attributes)


def _ensure_trace_provider(resource: Resource, trace_endpoint: str | None) -> None:
    if _TelemetryState.traces_initialized:
        return

    tracer_provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=trace_endpoint) if trace_endpoint else OTLPSpanExporter()
    tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(tracer_provider)
    _TelemetryState.tracer_provider = tracer_provider
    _TelemetryState.traces_initialized = True


def _ensure_log_export(resource: Resource, logs_endpoint: str | None) -> None:
    if _TelemetryState.logs_initialized:
        return

    exporter = OTLPLogExporter(endpoint=logs_endpoint) if logs_endpoint else OTLPLogExporter()
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
    set_logger_provider(logger_provider)

    handler = LoggingHandler(level=stdlib_logging.NOTSET, logger_provider=logger_provider)
    handler.set_name(_OTEL_LOG_HANDLER_NAME)
    stdlib_logging.getLogger(_LOGGER_NAMESPACE).addHandler(handler)

    _TelemetryState.logger_provider = logger_provider
    _TelemetryState.log_handler = handler
    _TelemetryState.logs_initialized = True


def _ensure_botocore_instrumentation() -> None:
    if _TelemetryState.botocore_instrumented:
        return

    BotocoreInstrumentor().instrument()
    _TelemetryState.botocore_instrumented = True


def _warn(message: str) -> None:
    sys.stderr.write(f"warning: {message}\n")


def configure_telemetry(config: Config) -> TelemetrySession:
    """Enable OpenTelemetry tracing and optional log export for the process.

    Any exporter/instrumentation failure degrades to a disabled session rather
    than crashing the CLI — telemetry must never be the thing that breaks borgboi.
    """
    if not config.telemetry.enabled:
        return TelemetrySession(enabled=False, logs_export_enabled=False)

    resource = _build_resource(config)

    try:
        _ensure_trace_provider(resource, config.telemetry.trace_endpoint)
    except Exception as exc:
        _warn(f"telemetry: failed to initialize trace exporter ({exc}); traces disabled for this run")
        return TelemetrySession(enabled=False, logs_export_enabled=False)

    try:
        _ensure_botocore_instrumentation()
    except Exception as exc:
        _warn(f"telemetry: failed to instrument botocore ({exc}); AWS spans will be missing")

    logs_export_enabled = False
    if config.telemetry.export_logs:
        try:
            _ensure_log_export(resource, config.telemetry.logs_endpoint)
            logs_export_enabled = True
        except Exception as exc:
            _warn(f"telemetry: failed to initialize log exporter ({exc}); log export disabled for this run")

    return TelemetrySession(enabled=True, logs_export_enabled=logs_export_enabled)


def get_tracer(name: str) -> trace.Tracer:
    """Return a tracer for borgboi instrumentation."""
    return trace.get_tracer(name, _get_service_version())


def _format_trace_id(trace_id: int) -> str:
    return f"{trace_id:032x}"


def _format_span_id(span_id: int) -> str:
    return f"{span_id:016x}"


def get_current_span_context() -> SpanContext | None:
    """Return the active span context when a valid span is current."""
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return None
    return span_context


def get_current_trace_id() -> str | None:
    """Return the active trace id formatted for logs and CLI output."""
    span_context = get_current_span_context()
    if span_context is None:
        return None
    return _format_trace_id(span_context.trace_id)


def get_current_span_id() -> str | None:
    """Return the active span id formatted for logs."""
    span_context = get_current_span_context()
    if span_context is None:
        return None
    return _format_span_id(span_context.span_id)


def bind_trace_contextvars() -> None:
    """Bind active trace metadata into structlog contextvars when present."""
    span_context = get_current_span_context()
    if span_context is None:
        return

    bind_contextvars(
        trace_id=_format_trace_id(span_context.trace_id),
        span_id=_format_span_id(span_context.span_id),
        trace_flags=f"{int(span_context.trace_flags):02x}",
    )


def set_span_attributes(span: Span, attributes: Mapping[str, AttributeValue | None]) -> None:
    """Apply non-null attributes to a span."""
    for key, value in attributes.items():
        if value is None:
            continue
        span.set_attribute(key, value)


def force_flush_telemetry() -> bool:
    """Flush telemetry providers without shutting down the process-global state.

    Returns ``True`` when every active provider flushed cleanly; ``False`` if a
    provider timed out, raised, or otherwise reported a failure. Warnings are
    written to stderr for each failure so the CLI can still communicate success
    honestly in the exit summary.
    """
    ok = True
    if _TelemetryState.tracer_provider is not None:
        try:
            if not _TelemetryState.tracer_provider.force_flush():
                _warn("telemetry: trace flush timed out; some spans may have been dropped")
                ok = False
        except Exception as exc:
            _warn(f"telemetry: trace flush raised ({exc}); some spans may have been dropped")
            ok = False
    if _TelemetryState.logger_provider is not None:
        try:
            if not _TelemetryState.logger_provider.force_flush():
                _warn("telemetry: log flush timed out; some log records may have been dropped")
                ok = False
        except Exception as exc:
            _warn(f"telemetry: log flush raised ({exc}); some log records may have been dropped")
            ok = False
    return ok


def telemetry_is_active() -> bool:
    """Return whether this process already has telemetry providers installed."""
    return _TelemetryState.tracer_provider is not None or _TelemetryState.logger_provider is not None


def reset_telemetry_for_tests() -> None:
    """Reset handler state used by tests without relying on process restart."""
    namespace_logger = stdlib_logging.getLogger(_LOGGER_NAMESPACE)
    if _TelemetryState.log_handler is not None:
        namespace_logger.removeHandler(_TelemetryState.log_handler)
        _TelemetryState.log_handler.close()

    if _TelemetryState.logger_provider is not None:
        _TelemetryState.logger_provider.shutdown()

    if _TelemetryState.tracer_provider is not None:
        _TelemetryState.tracer_provider.shutdown()

    _TelemetryState.logs_initialized = False
    _TelemetryState.traces_initialized = False
    _TelemetryState.botocore_instrumented = False
    _TelemetryState.logger_provider = None
    _TelemetryState.tracer_provider = None
    _TelemetryState.log_handler = None
