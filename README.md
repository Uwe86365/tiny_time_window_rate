# tiny_time_window_rate

Tracks event counts in fixed time windows and exposes per-window totals plus a sliding-window aggregate count for rate display.

```python
from tiny_time_window_rate import TimeWindowRateTracker

tracker = TimeWindowRateTracker(window_seconds=10.0)
tracker.record()          # uses time.monotonic()
tracker.record(1234.5)    # explicit timestamp

print(tracker.window_count())          # events in the current fixed window
print(tracker.sliding_count())         # events in the last 10 seconds
print(tracker.sliding_rate())          # events per second
print(tracker.window_totals(windows=3))  # [(start, count), ...]
```

## Why this exists

Rate displays usually need two different numbers: a stable per-window total for charting, and a smoother sliding count for a live rate. Computing both from the same event list avoids duplicating bookkeeping and keeps the two numbers consistent with each other. The trade-off is that the tracker keeps raw timestamps rather than per-window counters, so memory is proportional to the events in the retained window. For the intended use — a few thousand events per window — that is far simpler than maintaining a ring of counters and reconciling it with sliding queries.

## The edge you will hit

Window boundaries are anchored to the epoch, so a window starts at a multiple of `window_seconds`, not at the first event. An event recorded exactly on a boundary belongs to the window that starts there. Sliding queries are half-open on the left: `(t - window, t]`. If you need a different boundary rule, record events with timestamps you have already adjusted.

## API

- `TimeWindowRateTracker(window_seconds, clock=time.monotonic)` — raises `ValueError` if `window_seconds <= 0`.
- `record(timestamp=None) -> float` — records an event; returns the stored timestamp.
- `record_many(timestamps) -> None` — records an iterable of timestamps.
- `clear() -> None` — forgets all events.
- `window_count(timestamp=None) -> int` — events in the fixed window containing `timestamp`.
- `sliding_count(timestamp=None) -> int` — events in `(timestamp - window_seconds, timestamp]`.
- `sliding_rate(timestamp=None) -> float` — `sliding_count / window_seconds`.
- `window_totals(timestamp=None, windows=1) -> list[tuple[float, int]]` — oldest-first `(window_start, count)` pairs, including empty windows. Raises `ValueError` if `windows < 1`.
- `len(tracker) -> int` — number of retained events after pruning.

## Performance

The window keeps a bounded buffer, so `push` is constant time and memory does not
grow with the length of the stream. `peak` and `trough` are linear in the window
size, which is the trade that keeps `push` cheap.

