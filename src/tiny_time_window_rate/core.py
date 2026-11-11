"""Core implementation of a fixed-window event rate tracker."""

from __future__ import annotations

import time
from collections import deque
from typing import Callable, Deque, Iterable, List, Tuple


class TimeWindowRateTracker:
    """Tracks event timestamps and reports counts in fixed-size windows.

    The tracker is deliberately clock-injectable: every method that needs the
    current time calls ``self._clock()``. This keeps the class deterministic in
    tests without monkey-patching ``time.monotonic`` and without sleeping.

    Windows are anchored to the unix epoch (or, for a monotonic clock, to 0),
    so a window boundary is a multiple of ``window_seconds``. Events that fall
    exactly on a boundary belong to the window that starts there. This is the
    simplest rule that is consistent across calls and avoids off-by-one drift.

    Args:
        window_seconds: Width of each fixed window in seconds. Must be > 0.
        clock: Callable returning a float number of seconds. Defaults to
            ``time.monotonic``. The returned value must be monotonically
            non-decreasing for sliding queries to be meaningful.

    Raises:
        ValueError: If ``window_seconds`` is not strictly positive.
    """

    def __init__(
        self,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.window_seconds = float(window_seconds)
        self._clock = clock
        # Timestamps are kept in insertion order. We never rely on the clock
        # going backwards; if it does, the deque still preserves arrival order
        # and sliding queries simply see a non-monotonic tail.
        self._events: Deque[float] = deque()

    # -- internals ---------------------------------------------------------

    def _window_start(self, timestamp: float) -> float:
        """Return the start of the window containing ``timestamp``."""
        return (timestamp // self.window_seconds) * self.window_seconds

    def _prune(self, now: float) -> None:
        """Drop events older than the window that contains ``now``.

        Anything older than ``now - window_seconds`` cannot contribute to a
        per-window count for the current window, and cannot contribute to the
        sliding total either. Dropping it keeps memory bounded by the number
        of events in the most recent window(s) the caller actually queries.
        """
        cutoff = now - self.window_seconds
        events = self._events
        while events and events[0] < cutoff:
            events.popleft()

    # -- recording ---------------------------------------------------------

    def record(self, timestamp: float | None = None) -> float:
        """Record an event at ``timestamp`` (defaults to the current clock).

        Returns the timestamp that was stored, which is useful when the caller
        lets the tracker pick the time.
        """
        if timestamp is None:
            timestamp = self._clock()
        timestamp = float(timestamp)
        self._events.append(timestamp)
        self._prune(self._clock())
        return timestamp

    def record_many(self, timestamps: Iterable[float]) -> None:
        """Record several events. The clock is consulted once at the end."""
        for ts in timestamps:
            self._events.append(float(ts))
        self._prune(self._clock())

    def clear(self) -> None:
        """Forget every recorded event."""
        self._events.clear()

    # -- queries -----------------------------------------------------------

    def window_count(self, timestamp: float | None = None) -> int:
        """Return the number of events in the window containing ``timestamp``."""
        if timestamp is None:
            timestamp = self._clock()
        start = self._window_start(timestamp)
        end = start + self.window_seconds
        return sum(1 for ts in self._events if start <= ts < end)

    def sliding_count(self, timestamp: float | None = None) -> int:
        """Return events in the half-open interval ``(t - window, t]``.

        This is the classic rolling rate numerator: the most recent
        ``window_seconds`` worth of events, including one exactly at ``t`` and
        excluding one exactly at ``t - window_seconds``.
        """
        if timestamp is None:
            timestamp = self._clock()
        cutoff = timestamp - self.window_seconds
        return sum(1 for ts in self._events if cutoff < ts <= timestamp)

    def sliding_rate(self, timestamp: float | None = None) -> float:
        """Return ``sliding_count / window_seconds`` events per second."""
        return self.sliding_count(timestamp) / self.window_seconds

    def window_totals(
        self, timestamp: float | None = None, windows: int = 1
    ) -> List[Tuple[float, int]]:
        """Return ``(window_start, count)`` for the last ``windows`` windows.

        The final entry is the window containing ``timestamp``. Earlier
        entries are the preceding windows, oldest first. Windows with no
        events are included with a count of zero, which makes the result
        suitable for plotting without additional gap filling.
        """
        if windows < 1:
            raise ValueError("windows must be at least 1")
        if timestamp is None:
            timestamp = self._clock()
        current_start = self._window_start(timestamp)
        result: List[Tuple[float, int]] = []
        for i in range(windows - 1, -1, -1):
            start = current_start - i * self.window_seconds
            end = start + self.window_seconds
            count = sum(1 for ts in self._events if start <= ts < end)
            result.append((start, count))
        return result

    def __len__(self) -> int:
        """Number of events currently retained (after pruning)."""
        self._prune(self._clock())
        return len(self._events)
