"""In-process sliding-window rate limiter for unauthenticated endpoints.

Implemented with the standard library only so the auth layer gains
brute-force protection without a new runtime dependency or a shared store.
The limiter is deliberately per-process: with a single uvicorn worker (the
supported deployment for the in-process realtime hubs) the configured limits
are exact. If the backend is ever run with multiple workers, every worker
keeps its own counters, so the effective limit is ``max_requests`` per worker;
a shared store (e.g. Redis) would be needed for global accounting.

Keys are caller-controlled (the auth endpoints use the client IP from the
ASGI scope). Proxies are not trusted: ``X-Forwarded-For`` is never read, so a
reverse proxy must be configured to speak to the app directly or terminate
connections per client IP.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass

# Hard ceiling on tracked keys so a flood of spoofed source addresses cannot
# grow memory without bound. Oldest entries are pruned first.
_MAX_TRACKED_KEYS = 65_536


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    """Outcome of one rate-limit check."""

    allowed: bool
    retry_after_seconds: int


class SlidingWindowRateLimiter:
    """Thread-safe per-key sliding window counter.

    ``max_requests`` are allowed within a moving ``window_seconds``; the next
    request is rejected until the oldest hit leaves the window. Limits are
    read through ``get_limits`` on every call so tests and operators can
    change them without restarting the process.
    """

    def __init__(self, get_limits: "callable() -> tuple[int, float]") -> None:
        self._get_limits = get_limits
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, *, now: float | None = None) -> RateLimitDecision:
        """Record a request for ``key`` and report whether it is allowed."""

        timestamp = time.monotonic() if now is None else now
        max_requests, window = self._get_limits()
        if max_requests <= 0:  # feature disabled
            return RateLimitDecision(allowed=True, retry_after_seconds=0)

        with self._lock:
            events = self._events[key]
            cutoff = timestamp - window
            while events and events[0] <= cutoff:
                events.popleft()
            allowed = len(events) < max_requests
            if allowed:
                events.append(timestamp)
            retry_after = 0
            if not allowed and events:
                # Time until the oldest hit expires and frees a slot.
                retry_after = max(1, int(round(events[0] + window - timestamp)))
            self._prune(timestamp, window)
        return RateLimitDecision(allowed=allowed, retry_after_seconds=retry_after)

    def _prune(self, timestamp: float, window: float) -> None:
        """Drop expired keys so the tracker cannot grow without bound.

        Caller must hold the lock.
        """

        if len(self._events) <= _MAX_TRACKED_KEYS:
            return
        cutoff = timestamp - window
        stale = [
            key for key, events in self._events.items() if not events or events[-1] <= cutoff
        ]
        for key in stale:
            del self._events[key]

    def reset(self) -> None:
        """Clear all counters (used by tests)."""

        with self._lock:
            self._events.clear()


__all__ = ["RateLimitDecision", "SlidingWindowRateLimiter"]
