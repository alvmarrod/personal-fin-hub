"""Registry of long-running background work and the maintenance window.

The backup page must not replace the database while a market or FX sync is
writing to it, and the restore itself must block other API callers. Both
checks use this module: ``tracked`` marks a job as running, ``maintenance``
opens the window in which the API middleware rejects non-backup requests.
"""

import functools
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

_lock = threading.Lock()
_running: dict[str, int] = {}
_started: dict[str, str] = {}
_maintenance = False


@contextmanager
def track(name: str) -> Iterator[None]:
    """Mark ``name`` as running for the duration of the block."""
    with _lock:
        _running[name] = _running.get(name, 0) + 1
        _started.setdefault(name, datetime.now(UTC).isoformat())
    try:
        yield
    finally:
        with _lock:
            left = _running.get(name, 0) - 1
            if left > 0:
                _running[name] = left
            else:
                _running.pop(name, None)
                _started.pop(name, None)


def tracked(name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator form of :func:`track` for service entry points."""

    def wrap(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def inner(*args: Any, **kwargs: Any) -> Any:
            with track(name):
                return fn(*args, **kwargs)

        return inner

    return wrap


def running() -> list[dict[str, str]]:
    """Running operations, oldest first."""
    with _lock:
        return [{"name": name, "started_at": _started[name]} for name in _running]


def is_idle() -> bool:
    with _lock:
        return not _running


@contextmanager
def maintenance() -> Iterator[None]:
    """Open the restore window: API requests other than backups get 503."""
    global _maintenance
    with _lock:
        _maintenance = True
    try:
        yield
    finally:
        with _lock:
            _maintenance = False


def in_maintenance() -> bool:
    with _lock:
        return _maintenance


def reset() -> None:
    """Test helper: clear all state."""
    global _maintenance
    with _lock:
        _running.clear()
        _started.clear()
        _maintenance = False
