"""Derived macro KPIs — registry and access (the derived layer interface).

Implements the registry in ``doc/derived/macro.md``: our own KPIs computed from
world KPIs (and from other derived KPIs). Layering
(``doc/architecture_overview.md``)::

    datasources/  →  derivations  →  kpis/  →  derived/ (this module)  →  systems/

Each derived KPI declares its **inputs** (world- or derived-KPI names), its
**computation**, and its **value kind** (per the doc: a level is numeric, a
trend is a direction). The markets a KPI can be computed for are the
**intersection of its inputs' markets**, so when a source is added the derived
KPI extends automatically — there is no availability model.

Values are computed on demand from stored history; nothing is persisted.
"""

import sqlite3
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from db.connection import get_db
from services import world_kpi_svc
from services.config import config
from services.derived_kpi_calc import (
    DatedPoint,
    DatedSeries,
    Resolution,
    TrendDirection,
    real_rate,
    slope_step,
    to_monthly,
)

# A derived series is numeric (levels) or a direction (trends).
DerivedSeries = DatedSeries[float] | DatedSeries[TrendDirection]


class DerivedNotDefined(KeyError):
    """Raised when a derived KPI/market has no wired inputs."""


class ValueKind(StrEnum):
    """Output type of a derived KPI, per its spec in ``doc/derived/macro.md``."""

    NUMERIC = "numeric"
    DIRECTION = "direction"
    BOOL = "bool"  # reserved for state-engine signals (Phase 4)


@dataclass(frozen=True)
class DerivedDefinition:
    """A derived KPI: its inputs, computation, and output kind."""

    name: str
    inputs: tuple[str, ...]
    computation: str
    value_kind: ValueKind


_REGISTRY_LIST = [
    DerivedDefinition("policy_rate_trend", ("policy_rate",), "slope_step", ValueKind.DIRECTION),
    DerivedDefinition("inflation_rate_trend", ("inflation_rate",), "slope_step", ValueKind.DIRECTION),
    DerivedDefinition("m2_growth_trend", ("m2_growth",), "slope_step", ValueKind.DIRECTION),
    DerivedDefinition("real_interest_rate", ("policy_rate", "inflation_rate"), "real_rate", ValueKind.NUMERIC),
    DerivedDefinition("real_interest_rate_trend", ("real_interest_rate",), "slope_step", ValueKind.DIRECTION),
]
REGISTRY: dict[str, DerivedDefinition] = {definition.name: definition for definition in _REGISTRY_LIST}


def list_derived_kpis() -> list[str]:
    """Names of every registered derived KPI."""
    return sorted(REGISTRY)


def get_definition(name: str) -> DerivedDefinition:
    try:
        return REGISTRY[name]
    except KeyError:
        raise DerivedNotDefined(f"unknown derived KPI: {name!r}") from None


def _input_markets(name: str) -> set[str]:
    if name in REGISTRY:
        return set(market_keys(name))
    return set(world_kpi_svc.market_keys(name))


def market_keys(name: str) -> list[str]:
    """Markets a derived KPI can be computed for (intersection of its inputs')."""
    definition = get_definition(name)
    markets: set[str] | None = None
    for input_name in definition.inputs:
        input_markets = _input_markets(input_name)
        markets = input_markets if markets is None else markets & input_markets
    return sorted(markets or set())


def _world_series(name: str, market: str, conn: sqlite3.Connection) -> DatedSeries[float]:
    source = world_kpi_svc.get_source(name, market)
    points = world_kpi_svc.world_kpi(name, market, conn=conn)
    return DatedSeries(
        resolution=Resolution(source.resolution),
        points=tuple(DatedPoint(obs_date=point.obs_date, value=point.value) for point in points),
    )


def _resolve_series(name: str, market: str, conn: sqlite3.Connection) -> DatedSeries[float]:
    """Resolve a numeric series by name: a derived KPI, else a world KPI."""
    if name in REGISTRY:
        return cast(DatedSeries[float], _compute(name, market, conn))
    return _world_series(name, market, conn)


def _compute(name: str, market: str, conn: sqlite3.Connection) -> DerivedSeries:
    definition = get_definition(name)
    if definition.computation == "slope_step":
        base = to_monthly(_resolve_series(definition.inputs[0], market, conn))
        return slope_step(base, deadband=config.derived_trend_deadband)
    if definition.computation == "real_rate":
        policy = to_monthly(_resolve_series(definition.inputs[0], market, conn))
        inflation = to_monthly(_resolve_series(definition.inputs[1], market, conn))
        return real_rate(policy, inflation)
    raise DerivedNotDefined(f"unknown computation: {definition.computation!r}")


def derived_kpi(name: str, market: str, conn: sqlite3.Connection | None = None) -> DerivedSeries:
    """Return the series for a derived KPI in a market.

    Raises ``DerivedNotDefined`` when the KPI is unknown or the market lacks a
    wired input.
    """
    if name not in REGISTRY:
        raise DerivedNotDefined(f"unknown derived KPI: {name!r}")
    if market not in market_keys(name):
        raise DerivedNotDefined(f"no inputs for derived KPI {name!r} in market {market!r}")
    conn = conn if conn is not None else get_db()
    return _compute(name, market, conn)


def latest_derived_kpi(name: str, market: str, conn: sqlite3.Connection | None = None) -> DatedPoint | None:
    """The most recent point of a derived KPI, or None when the series is empty."""
    series = derived_kpi(name, market, conn=conn)
    if not series.points:
        return None
    return cast(DatedPoint, max(series.points, key=lambda point: point.obs_date))
