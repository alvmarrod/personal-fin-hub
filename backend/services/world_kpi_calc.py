"""World-KPI derivations — the raw → world-KPI normalization step.

Implements the mathematics defined in ``doc/kpis/world_calc.md``. This is the
layer between the datasources layer (which stores raw reported series) and the
world-KPI registry (``doc/kpis/world.md``): it turns a raw series into the
series the world KPI is expressed as.

A normalization is a pure function ``Series -> Series``. The registry in
``world_kpi_svc`` names the normalization a KPI uses; this module applies it.
Only inputs already expressed in their final form need no normalization
(``none``).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class KpiPoint:
    """One point of a world-KPI series."""

    obs_date: date
    value: float


Series = list[KpiPoint]


def none(series: Series) -> Series:
    """Passthrough: the raw series is already the KPI value."""
    return series


def yoy_from_level(series: Series) -> Series:
    """Year-over-year growth (%) from a monthly level/index series.

    ``yoy_t = (level_t / level_{t-12} - 1) * 100``, matched by calendar month
    (``doc/kpis/world_calc.md``). An observation with no matching month twelve
    periods back is dropped, so the result starts a year into the series.
    """
    by_month = {(point.obs_date.year, point.obs_date.month): point.value for point in series}
    result: Series = []
    for point in sorted(series, key=lambda p: p.obs_date):
        prior = by_month.get((point.obs_date.year - 1, point.obs_date.month))
        if prior:
            result.append(KpiPoint(obs_date=point.obs_date, value=(point.value / prior - 1) * 100))
    return result


NORMALIZATIONS: dict[str, Callable[[Series], Series]] = {
    "none": none,
    "yoy_from_level": yoy_from_level,
}


def apply(normalization: str, series: Series) -> Series:
    """Apply a named normalization; raises ``KeyError`` for an unknown name."""
    return NORMALIZATIONS[normalization](series)
