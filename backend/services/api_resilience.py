"""Resilience for the external Market API client: retry + circuit breaker.

Retry: transient failures (``httpx.TransportError``, HTTP 5xx, 429) are retried
with exponential backoff + jitter. Non-transient 4xx (including 404) fail fast so
``MarketAPINotFound`` stays authoritative.

Circuit breaker: a per-``base_url`` in-process, thread-safe state machine
(``closed → open → half-open → closed``). On a confirmed outage every caller
fails fast instead of stalling on N timeouts.

Config (``backend/config.json`` → ``market_api.*``):

- ``retry_attempts`` — max attempts (default 3)
- ``retry_base_delay`` — initial backoff seconds (default 0.5)
- ``retry_max_delay`` — backoff ceiling in seconds (default 10)
- ``circuit_failure_threshold`` — consecutive failures to open (default 5)
- ``circuit_cooldown_seconds`` — how long the circuit stays open (default 60)
"""

import random
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from enum import Enum

import httpx

from services.config import config

RETRY_AFTER_CAP_SECONDS = 60


class CircuitState(Enum):
    """State of a circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"


class CircuitBreaker:
    """Thread-safe fail-fast circuit breaker keyed by ``base_url``.

    closed → open → half-open → closed. While ``OPEN`` every request fails fast
    (no network activity). After the cooldown the first caller becomes a single
    ``HALF_OPEN`` trial request: success recovers to ``CLOSED``, failure re-opens
    the circuit with a fresh cooldown.
    """

    def __init__(
        self,
        failure_threshold: int,
        cooldown_seconds: float,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self._failure_threshold = max(1, failure_threshold)
        self._cooldown_seconds = cooldown_seconds
        self._now = now
        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at = 0.0
        self._last_success_at: str | None = None

    @property
    def state(self) -> CircuitState:
        """Current circuit state (thread-safe read)."""
        with self._lock:
            return self._state

    def is_open(self) -> bool:
        """True when normal traffic must not flow (open or half-open)."""
        with self._lock:
            return self._state is not CircuitState.CLOSED

    def allow_request(self) -> bool:
        """Grant or deny a request; transitions open → half-open after cooldown.

        Only one half-open trial is allowed at a time.
        """
        with self._lock:
            if self._state is CircuitState.CLOSED:
                return True
            if self._state is CircuitState.OPEN:
                if self._now() - self._opened_at >= self._cooldown_seconds:
                    self._state = CircuitState.HALF_OPEN
                    return True
                return False
            return False

    def can_proceed(self) -> bool:
        """Read-only peek: would a request be granted right now?

        Like ``allow_request`` but never consumes the half-open trial and
        never mutates state. True when closed, or open with the cooldown
        elapsed (the next ``allow_request`` would grant the trial); False
        when open within the cooldown or while a half-open trial is in
        flight. Callers that only fail fast — not perform the request —
        must use this instead of ``allow_request``.
        """
        with self._lock:
            if self._state is CircuitState.CLOSED:
                return True
            if self._state is CircuitState.OPEN:
                return self._now() - self._opened_at >= self._cooldown_seconds
            return False

    def record_success(self) -> None:
        """Record a successful request; recovers half-open and resets failures."""
        with self._lock:
            self._consecutive_failures = 0
            self._last_success_at = datetime.now(UTC).isoformat()
            if self._state is CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record a failed request; opens the circuit at the failure threshold."""
        with self._lock:
            if self._state is CircuitState.CLOSED:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._failure_threshold:
                    self._state = CircuitState.OPEN
                    self._opened_at = self._now()
            elif self._state is CircuitState.HALF_OPEN:
                self._consecutive_failures = 0
                self._state = CircuitState.OPEN
                self._opened_at = self._now()

    @property
    def consecutive_failures(self) -> int:
        """Current consecutive-failure count (thread-safe read, for tests/health)."""
        with self._lock:
            return self._consecutive_failures

    @property
    def last_success_at(self) -> str | None:
        """ISO timestamp of the last successful request (for health)."""
        with self._lock:
            return self._last_success_at


_breakers: dict[str, CircuitBreaker] = {}
_breakers_lock = threading.Lock()


def get_breaker(base_url: str) -> CircuitBreaker:
    """Get the shared circuit breaker for a ``base_url`` (created on first use)."""
    with _breakers_lock:
        breaker = _breakers.get(base_url)
        if breaker is None:
            breaker = CircuitBreaker(
                failure_threshold=config.market_api_circuit_failure_threshold,
                cooldown_seconds=config.market_api_circuit_cooldown_seconds,
            )
            _breakers[base_url] = breaker
        return breaker


def reset_breakers() -> None:
    """Drop all cached breakers (test isolation only)."""
    with _breakers_lock:
        _breakers.clear()


def is_retryable_transport_error(exc: BaseException) -> bool:
    """True for transient network-level failures (connect/read/write/timeout)."""
    return isinstance(exc, httpx.TransportError)


def should_retry_http(status_code: int) -> bool:
    """True for transient HTTP failures: 5xx and 429."""
    return status_code >= 500 or status_code == 429


def backoff_delay(attempt: int, base: float, maximum: float) -> float:
    """Exponential backoff for *attempt* (1-based): base * 2**(attempt-1), capped."""
    return min(base * (2 ** (attempt - 1)), maximum)


def jitter(delay: float) -> float:
    """Apply ±20% jitter to a delay to avoid thundering-herd retries."""
    return delay * random.uniform(0.8, 1.2)


def retry_after_seconds(response: httpx.Response) -> float | None:
    """Parse the ``Retry-After`` header (integer seconds, capped at 60).

    Returns None when the header is absent or not an integer.
    """
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return min(int(value), RETRY_AFTER_CAP_SECONDS)
    except (TypeError, ValueError):
        return None


def sleep_between_attempts(
    attempt: int,
    base: float,
    maximum: float,
    response: httpx.Response | None = None,
) -> None:
    """Sleep the backoff delay for *attempt*, honoring ``Retry-After`` on 429."""
    delay = retry_after_seconds(response) if response is not None else None
    if delay is None:
        delay = jitter(backoff_delay(attempt, base, maximum))
    time.sleep(delay)
