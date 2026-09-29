"""World-KPI registry and access — the kpis layer interface.

The registry maps each world KPI (``doc/kpis/world.md``) to its source per
market; access reads the stored raw series (datasources layer) and applies the
world-KPI normalization (``world_kpi_calc``, ``doc/kpis/world_calc.md``).

Layering (``doc/architecture_overview.md``)::

    datasources/  →  derivations  →  kpis/ (this module)  →  derived/

A KPI is identified by ``kpi_name`` (the registry foreign key, world.md §2).
``market`` is an access parameter: the same KPI resolves per market. Only KPIs
and markets with a wired source are in the registry — a market that is not yet
sourced is simply not registered (there is no availability model; sources are
added over time).

Consumers (the derived layer, later the engine) call ``world_kpi`` and treat the
result as the KPI's series. They refer to a KPI by name, never re-derive it.
"""

import sqlite3
from dataclasses import dataclass, field
from datetime import date

from db import queries
from db.connection import get_db
from services.world_kpi_calc import KpiPoint, Series, apply

# Canonical market keys (stable, locale-independent; display labels live in the
# docs). A KPI may be defined for any market it has a source for.
MARKET_USA = "usa"
MARKET_JAPAN = "japan"
MARKET_SPAIN_EUROZONE = "spain-eurozone"


class KpiNotDefined(KeyError):
    """Raised when a KPI/market has no wired source."""


@dataclass(frozen=True)
class KpiSource:
    """Where one market's reading of a KPI comes from.

    ``source_kind`` selects the datasource reader (``macro`` reads a macro
    series by ``ref``; further kinds, e.g. the Market API, can be added without
    changing the registry shape). ``normalization`` names a
    ``world_kpi_calc.NORMALIZATIONS`` entry.
    """

    ref: str
    normalization: str = "none"
    source_kind: str = "macro"


@dataclass(frozen=True)
class KpiDefinition:
    """A world KPI: its name and the source per market."""

    kpi_name: str
    markets: dict[str, KpiSource] = field(default_factory=dict)


# Registry of wired world KPIs. Extend by adding markets/sources; a KPI with no
# source for a market is left out (not signalled).
REGISTRY: dict[str, KpiDefinition] = {
    "policy_rate": KpiDefinition(
        "policy_rate",
        {
            MARKET_JAPAN: KpiSource("boj-policy-rate"),
            MARKET_SPAIN_EUROZONE: KpiSource("ecb-deposit-rate"),
        },
    ),
    "inflation_rate": KpiDefinition(
        "inflation_rate",
        {
            MARKET_USA: KpiSource("usa-cpi-yoy", normalization="yoy_from_level"),
            MARKET_SPAIN_EUROZONE: KpiSource("eurozone-cpi-yoy"),
        },
    ),
    "m2_growth": KpiDefinition(
        "m2_growth",
        {
            MARKET_USA: KpiSource("usa-m2-money-supply", normalization="yoy_from_level"),
            MARKET_JAPAN: KpiSource("japan-m2-yoy", normalization="yoy_from_level"),
            MARKET_SPAIN_EUROZONE: KpiSource("eurozone-m2-yoy"),
        },
    ),
}


def list_world_kpis() -> list[str]:
    """Names of every registered world KPI."""
    return sorted(REGISTRY)


def market_keys(kpi_name: str) -> list[str]:
    """Markets a KPI is defined for."""
    return sorted(get_definition(kpi_name).markets)


def get_definition(kpi_name: str) -> KpiDefinition:
    try:
        return REGISTRY[kpi_name]
    except KeyError:
        raise KpiNotDefined(f"unknown world KPI: {kpi_name!r}") from None


def get_source(kpi_name: str, market: str) -> KpiSource:
    definition = get_definition(kpi_name)
    try:
        return definition.markets[market]
    except KeyError:
        raise KpiNotDefined(f"no source for world KPI {kpi_name!r} in market {market!r}") from None


def _read_macro_series(conn: sqlite3.Connection, slug: str) -> Series:
    return [
        KpiPoint(obs_date=date.fromisoformat(row["obs_date"]), value=row["value"])
        for row in queries.get_macro_observations(conn, slug)
    ]


def _read_source(conn: sqlite3.Connection, source: KpiSource) -> Series:
    if source.source_kind == "macro":
        return _read_macro_series(conn, source.ref)
    raise KpiNotDefined(f"unknown source kind: {source.source_kind!r}")


def world_kpi(kpi_name: str, market: str, conn: sqlite3.Connection | None = None) -> Series:
    """Return the normalized series for a world KPI in a market.

    Reads the market's raw source and applies the KPI's normalization. Raises
    ``KpiNotDefined`` when the KPI or market has no wired source.
    """
    source = get_source(kpi_name, market)
    conn = conn if conn is not None else get_db()
    raw = _read_source(conn, source)
    return apply(source.normalization, raw)


def latest_world_kpi(kpi_name: str, market: str, conn: sqlite3.Connection | None = None) -> KpiPoint | None:
    """The most recent point of a world KPI, or None when the series is empty."""
    series = world_kpi(kpi_name, market, conn=conn)
    return max(series, key=lambda point: point.obs_date) if series else None
