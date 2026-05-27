"""Tests for ReportHistory and its first/second derivatives."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from convergence.history import ReportHistory


def _ts(seconds: float) -> datetime:
    return datetime(2026, 5, 25, 18, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=seconds)


def test_empty_history_returns_none_for_both_derivatives():
    h = ReportHistory()
    assert h.growth_rate_m2_s() is None
    assert h.acceleration_m2_s2() is None


def test_single_sample_still_no_derivatives():
    h = ReportHistory()
    h.record(1.0, _ts(0))
    assert h.growth_rate_m2_s() is None
    assert h.acceleration_m2_s2() is None


def test_two_samples_give_growth_rate_only():
    h = ReportHistory()
    h.record(1.0, _ts(0))
    h.record(2.0, _ts(10))
    growth = h.growth_rate_m2_s()
    assert growth is not None
    assert growth == pytest.approx(1000.0, rel=1e-6)
    assert h.acceleration_m2_s2() is None


def test_constant_growth_gives_zero_acceleration():
    h = ReportHistory()
    h.record(1.0, _ts(0))
    h.record(2.0, _ts(10))
    h.record(3.0, _ts(20))
    growth = h.growth_rate_m2_s()
    accel = h.acceleration_m2_s2()
    assert growth == pytest.approx(1000.0, rel=1e-6)
    assert accel == pytest.approx(0.0, abs=1e-6)


def test_accelerating_growth_gives_positive_acceleration():
    h = ReportHistory()
    h.record(1.0, _ts(0))
    h.record(2.0, _ts(10))
    h.record(4.0, _ts(20))
    assert h.acceleration_m2_s2() > 0.0


def test_decelerating_growth_gives_negative_acceleration():
    h = ReportHistory()
    h.record(1.0, _ts(0))
    h.record(3.0, _ts(10))
    h.record(3.5, _ts(20))
    assert h.acceleration_m2_s2() < 0.0


def test_max_size_enforces_ring_buffer_behavior():
    h = ReportHistory(max_size=3)
    for i in range(10):
        h.record(float(i + 1), _ts(i * 10))
    assert len(h) == 3
    entries = h.entries
    assert entries[0].area_m2 == 8.0 * 10_000
    assert entries[-1].area_m2 == 10.0 * 10_000


def test_max_size_below_three_rejected():
    with pytest.raises(ValueError):
        ReportHistory(max_size=2)


def test_duplicate_timestamp_does_not_divide_by_zero():
    h = ReportHistory()
    same = _ts(0)
    h.record(1.0, same)
    h.record(2.0, same)
    growth = h.growth_rate_m2_s()
    assert growth is not None
    assert growth >= 0
