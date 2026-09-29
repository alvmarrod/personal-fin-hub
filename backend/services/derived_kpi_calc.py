"""Derived macro mathematics — the world-KPI → derived-KPI step.

Implements the computations defined in ``doc/derived/macro.md``. The functions
are generic and typed: they operate on ``DatedSeries`` values that carry a
``resolution``, so they can navigate the series correctly and refuse
incompatible inputs.

The trend is the **immediate slope**: for each point, the direction of the
change from the previous point (not a regression or CAGR over a window). A
policy-rate series is an irregular step; ``to_monthly`` forward-fills it to a
month-end grid first.
"""

import math
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

# Comparison floor: any real change is noticeable, but float representation
# noise must not register as one.
_EPSILON = 1e-9


class Resolution(StrEnum):
    """Cadence of a series."""

    MONTHLY = "monthly"
    DAILY = "daily"
    EVENT = "event"


class TrendDirection(StrEnum):
    """Direction of the immediate slope (``doc/derived/macro.md``)."""

    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"


@dataclass(frozen=True)
class DatedPoint[T]:
    """One point of a dated series."""

    obs_date: date
    value: T


@dataclass(frozen=True)
class DatedSeries[T]:
    """A series of dated points plus its resolution (ascending by date)."""

    resolution: Resolution
    points: tuple[DatedPoint[T], ...]


def _last_day_of_month(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def _month_key(value: date) -> tuple[int, int]:
    return (value.year, value.month)


def to_monthly(series: DatedSeries[float], *, as_of: date | None = None) -> DatedSeries[float]:
    """Resample a series to a monthly grid (forward-filled to month-end).

    A monthly series is returned unchanged. For an event/daily series, each
    calendar month from the first observation to ``as_of`` (default today) gets
    the value of the most recent observation on or before that month's end. The
    current (partial) month uses ``as_of`` itself, so it reflects the latest
    known value.
    """
    if series.resolution is Resolution.MONTHLY or not series.points:
        return series

    as_of = as_of or date.today()
    points = series.points
    start = _month_key(points[0].obs_date)
    end = _month_key(as_of)

    result: list[DatedPoint[float]] = []
    year, month = start
    while (year, month) <= end:
        month_end = _last_day_of_month(year, month)
        as_of_date = min(month_end, as_of)
        value = _latest_at_or_before(points, as_of_date)
        if value is not None:
            result.append(DatedPoint(obs_date=as_of_date, value=value))
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return DatedSeries(resolution=Resolution.MONTHLY, points=tuple(result))


def _latest_at_or_before(points: tuple[DatedPoint[float], ...], when: date) -> float | None:
    latest: float | None = None
    for point in points:
        if point.obs_date <= when:
            latest = point.value
        else:
            break
    return latest


def slope_step(series: DatedSeries[float], *, deadband: float = 0.0) -> DatedSeries[TrendDirection]:
    """Immediate-slope direction at each point (vs the previous point).

    ``direction = sign(value_t - value_{t-1})``: ``increasing`` / ``decreasing``,
    or ``stable`` when ``|Δ| <= deadband`` (plus a float-noise floor). The first
    point has no predecessor and is omitted.
    """
    threshold = deadband + _EPSILON
    directions: list[DatedPoint[TrendDirection]] = []
    previous: DatedPoint[float] | None = None
    for point in series.points:
        if previous is not None:
            delta = point.value - previous.value
            if math.isclose(delta, 0.0, rel_tol=0.0, abs_tol=threshold) or abs(delta) <= threshold:
                direction = TrendDirection.STABLE
            elif delta > 0:
                direction = TrendDirection.INCREASING
            else:
                direction = TrendDirection.DECREASING
            directions.append(DatedPoint(obs_date=point.obs_date, value=direction))
        previous = point
    return DatedSeries(resolution=series.resolution, points=tuple(directions))


def real_rate(policy: DatedSeries[float], inflation: DatedSeries[float]) -> DatedSeries[float]:
    """``real_rate = policy_rate - inflation_rate``, aligned by calendar month.

    Both inputs must be monthly. Only months present in both series produce a
    point.
    """
    inflation_by_month = {_month_key(point.obs_date): point.value for point in inflation.points}
    result: list[DatedPoint[float]] = []
    for point in policy.points:
        inflation_value = inflation_by_month.get(_month_key(point.obs_date))
        if inflation_value is not None:
            result.append(DatedPoint(obs_date=point.obs_date, value=point.value - inflation_value))
    return DatedSeries(resolution=Resolution.MONTHLY, points=tuple(result))
