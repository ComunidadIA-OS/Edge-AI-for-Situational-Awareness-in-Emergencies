"""Ring-buffer of past fire perimeter areas for first/second derivative estimation.

The API server keeps a single ReportHistory instance per drone and calls
``record`` after each inference cycle. ``growth_rate_m2_s`` and
``acceleration_m2_s2`` then become available for the JSON payload so the
frontend can answer "how fast is it growing?" and "is it accelerating?".
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone


_HA_TO_M2 = 10_000.0


@dataclass(frozen=True)
class HistoryEntry:
    timestamp_s: float
    area_m2: float


class ReportHistory:
    """Bounded history of (timestamp, area) samples for derivative estimation."""

    def __init__(self, max_size: int = 30) -> None:
        if max_size < 3:
            raise ValueError("max_size must be at least 3 to allow second derivatives")
        self._entries: deque[HistoryEntry] = deque(maxlen=max_size)

    def record(self, area_ha: float, timestamp: datetime | None = None) -> None:
        ts = (timestamp or datetime.now(timezone.utc)).timestamp()
        if self._entries and ts <= self._entries[-1].timestamp_s:
            ts = self._entries[-1].timestamp_s + 1e-3
        self._entries.append(HistoryEntry(timestamp_s=ts, area_m2=area_ha * _HA_TO_M2))

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def entries(self) -> list[HistoryEntry]:
        return list(self._entries)

    def growth_rate_m2_s(self) -> float | None:
        """First derivative dA/dt using backward difference of the last two samples."""
        if len(self._entries) < 2:
            return None
        prev, curr = self._entries[-2], self._entries[-1]
        dt = curr.timestamp_s - prev.timestamp_s
        if dt <= 0:
            return None
        return (curr.area_m2 - prev.area_m2) / dt

    def acceleration_m2_s2(self) -> float | None:
        """Second derivative d2A/dt2 from the last three samples (centered ratio)."""
        if len(self._entries) < 3:
            return None
        a, b, c = self._entries[-3], self._entries[-2], self._entries[-1]
        dt1 = b.timestamp_s - a.timestamp_s
        dt2 = c.timestamp_s - b.timestamp_s
        if dt1 <= 0 or dt2 <= 0:
            return None
        rate1 = (b.area_m2 - a.area_m2) / dt1
        rate2 = (c.area_m2 - b.area_m2) / dt2
        dt_avg = 0.5 * (dt1 + dt2)
        return (rate2 - rate1) / dt_avg

    def derivatives(self) -> tuple[float | None, float | None]:
        return self.growth_rate_m2_s(), self.acceleration_m2_s2()
