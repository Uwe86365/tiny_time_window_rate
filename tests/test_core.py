import unittest

from tiny_time_window_rate import TimeWindowRateTracker


class FakeClock:
    def __init__(self, start=0.0):
        self.now = float(start)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += float(seconds)


class ConstructorTests(unittest.TestCase):
    def test_rejects_zero_window(self):
        with self.assertRaises(ValueError):
            TimeWindowRateTracker(0)

    def test_rejects_negative_window(self):
        with self.assertRaises(ValueError):
            TimeWindowRateTracker(-1.5)

    def test_accepts_positive_window(self):
        tracker = TimeWindowRateTracker(2.5)
        self.assertEqual(tracker.window_seconds, 2.5)


class RecordTests(unittest.TestCase):
    def test_record_uses_clock_when_timestamp_omitted(self):
        clock = FakeClock(100.0)
        tracker = TimeWindowRateTracker(10.0, clock=clock)
        stored = tracker.record()
        self.assertEqual(stored, 100.0)
        self.assertEqual(tracker.window_count(100.0), 1)

    def test_record_returns_explicit_timestamp(self):
        tracker = TimeWindowRateTracker(10.0, clock=FakeClock(0.0))
        self.assertEqual(tracker.record(42.5), 42.5)

    def test_record_many_accepts_any_iterable(self):
        tracker = TimeWindowRateTracker(10.0, clock=FakeClock(0.0))
        tracker.record_many(ts for ts in (1.0, 2.0, 3.0))
        self.assertEqual(tracker.window_count(1.0), 3)

    def test_clear_removes_events(self):
        tracker = TimeWindowRateTracker(10.0, clock=FakeClock(0.0))
        tracker.record(1.0)
        tracker.record(2.0)
        tracker.clear()
        self.assertEqual(len(tracker), 0)
        self.assertEqual(tracker.window_count(1.0), 0)


class WindowBoundaryTests(unittest.TestCase):
    def test_boundary_event_belongs_to_new_window(self):
        # window = 10, boundary at 20.0; event at 20.0 is in [20, 30).
        tracker = TimeWindowRateTracker(10.0, clock=FakeClock(0.0))
        tracker.record(19.999)
        tracker.record(20.0)
        self.assertEqual(tracker.window_count(19.999), 1)
        self.assertEqual(tracker.window_count(20.0), 1)
        self.assertEqual(tracker.window_count(25.0), 1)

    def test_negative_timestamps_floor_correctly(self):
        # -0.5 // 10 == -1, so window start is -10.0.
        tracker = TimeWindowRateTracker(10.0, clock=FakeClock(0.0))
        tracker.record(-0.5)
        self.assertEqual(tracker.window_count(-0.5), 1)
        self.assertEqual(tracker.window_count(-9.0), 1)
        self.assertEqual(tracker.window_count(0.0), 0)


class SlidingTests(unittest.TestCase):
    def test_sliding_count_is_half_open_on_the_left(self):
        tracker = TimeWindowRateTracker(10.0, clock=FakeClock(0.0))
        tracker.record(10.0)   # exactly at t - window
        tracker.record(20.0)   # exactly at t
        self.assertEqual(tracker.sliding_count(20.0), 1)

    def test_sliding_count_includes_events_at_query_time(self):
        tracker = TimeWindowRateTracker(10.0, clock=FakeClock(0.0))
        tracker.record(20.0)
        self.assertEqual(tracker.sliding_count(20.0), 1)

    def test_sliding_rate_divides_by_window(self):
        tracker = TimeWindowRateTracker(4.0, clock=FakeClock(0.0))
        tracker.record(1.0)
        tracker.record(2.0)
        self.assertEqual(tracker.sliding_rate(3.0), 0.5)

    def test_sliding_count_ignores_future_events(self):
        tracker = TimeWindowRateTracker(10.0, clock=FakeClock(0.0))
        tracker.record(15.0)
        self.assertEqual(tracker.sliding_count(10.0), 0)


class WindowTotalsTests(unittest.TestCase):
    def test_returns_oldest_first_including_gaps(self):
        tracker = TimeWindowRateTracker(10.0, clock=FakeClock(0.0))
        tracker.record(1.0)    # window [0, 10)
        tracker.record(21.0)   # window [20, 30)
        totals = tracker.window_totals(25.0, windows=3)
        self.assertEqual(totals, [(0.0, 1), (10.0, 0), (20.0, 1)])

    def test_single_window_by_default(self):
        tracker = TimeWindowRateTracker(10.0, clock=FakeClock(0.0))
        tracker.record(5.0)
        self.assertEqual(tracker.window_totals(5.0), [(0.0, 1)])

    def test_rejects_zero_windows(self):
        tracker = TimeWindowRateTracker(10.0, clock=FakeClock(0.0))
        with self.assertRaises(ValueError):
            tracker.window_totals(0.0, windows=0)


class PruningTests(unittest.TestCase):
    def test_old_events_are_pruned_on_record(self):
        clock = FakeClock(0.0)
        tracker = TimeWindowRateTracker(10.0, clock=clock)
        tracker.record(0.0)
        clock.advance(25.0)
        tracker.record(None)  # now = 25.0, event at 0.0 is older than 15.0
        self.assertEqual(len(tracker), 1)

    def test_pruning_keeps_event_exactly_at_cutoff(self):
        # cutoff = now - window; an event exactly at cutoff is still kept
        # because the prune test uses <= and the sliding query excludes it.
        clock = FakeClock(10.0)
        tracker = TimeWindowRateTracker(10.0, clock=clock)
        tracker.record(0.0)
        tracker.record(None)  # now = 10.0, cutoff = 0.0, event at 0.0 kept
        self.assertEqual(len(tracker), 2)

    def test_len_prunes_before_counting(self):
        clock = FakeClock(0.0)
        tracker = TimeWindowRateTracker(10.0, clock=clock)
        tracker.record(0.0)
        clock.advance(100.0)
        self.assertEqual(len(tracker), 0)


if __name__ == "__main__":
    unittest.main()
