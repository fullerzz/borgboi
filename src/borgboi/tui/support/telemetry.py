"""Telemetry helpers for TUI method instrumentation."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import AbstractContextManager
from functools import wraps
from inspect import iscoroutinefunction
from typing import TYPE_CHECKING, ParamSpec, TypeVar, cast

from opentelemetry.trace import INVALID_SPAN as _NOOP_SPAN
from opentelemetry.trace import Span, use_span

from borgboi.core.telemetry import get_tracer

if TYPE_CHECKING:
    from borgboi.config import Config

P = ParamSpec("P")
R = TypeVar("R")

tracer = get_tracer(__name__)


def _resolve_config(instance: object) -> Config | None:
    direct_config = getattr(instance, "_config", None)
    if direct_config is not None:
        return cast("Config", direct_config)

    orchestrator = getattr(instance, "_orchestrator", None)
    orchestrator_config = getattr(orchestrator, "config", None)
    if orchestrator_config is not None:
        return cast("Config", orchestrator_config)

    app = getattr(instance, "app", None)
    app_config = getattr(app, "_config", None)
    if app_config is not None:
        return cast("Config", app_config)

    return None


def _span_context(instance: object, name: str) -> AbstractContextManager[Span]:
    config = _resolve_config(instance)
    if config is None or not config.telemetry.enabled or not config.telemetry.capture_tui:
        return cast("AbstractContextManager[Span]", use_span(_NOOP_SPAN, end_on_exit=False))
    return tracer.start_as_current_span(name)


def capture_span(name: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Capture a TUI span around the decorated method when enabled."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        if iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                instance = args[0] if args else None
                with _span_context(instance, name):
                    result = await cast(Callable[P, Awaitable[R]], func)(*args, **kwargs)
                    return result

            return cast("Callable[P, R]", async_wrapper)

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            instance = args[0] if args else None
            with _span_context(instance, name):
                return func(*args, **kwargs)

        return cast("Callable[P, R]", sync_wrapper)

    return decorator
