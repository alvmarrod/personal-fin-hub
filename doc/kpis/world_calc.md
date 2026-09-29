# World KPI Computations

## Purpose

Some world KPIs are not published directly: the provider exposes a raw series
in a different shape, and the KPI value is a normalization of it. This
document defines those normalizations.

Placement in the pipeline:

```text
datasources/  →  kpis/ (this file normalizes a raw series into a world KPI)
              →  derived/  →  systems/
```

A raw series is fetched and parsed per `doc/datasources/macro.md`, which stores
it **as reported** (a level or index where the provider publishes one). When the
world KPI is expressed in a different unit than the reported series — a growth
rate from a level — the conversion happens here. World KPIs already reported in
their final form (Eurozone CPI annual rate, policy rates, Eurozone M2) need no
entry and are passthrough.

## Normalizations

| World KPI | Raw series | Normalization |
|---|---|---|
| `inflation_rate`, USA | CPI-U index, `bls:usa-cpi-yoy` (`CUUR0000SA0`) | Year-over-year growth (below) |
| `m2_growth`, Japan | Japan M2 level, `boj:japan-m2-yoy` (`MD02`) | Year-over-year growth (below) |
| `m2_growth`, USA | USA M2 level, `fred:usa-m2-money-supply` (`M2SL`) | Year-over-year growth (below) |

### Year-over-year growth from a level series

```text
yoy_t = (level_t / level_{t-12} - 1) * 100
```

- `level_t` is the level for the observation month; `level_{t-12}` is the level
  for the same calendar month one year earlier.
- Cadence is monthly. An observation with no matching month twelve periods
  back has no YoY value yet.
- The result is a percentage, consistent with the other rate series.

Implemented in `backend/services/world_kpi_calc.py`
(`yoy_from_level`, selected by name from the world-KPI registry in
`backend/services/world_kpi_svc.py`).

### Precision

The provider may report a rounded and a full-resolution value. The
normalization uses the full-resolution value where the provider offers one
(the ECB Data Portal's `OBS_VALUE_AS_IS`; FRED's `M2SL` as reported), so the
ratio is not computed from rounded inputs. See `doc/datasources/macro.md` for
the per-provider fields.

### Revisions

A published level can be revised. Because every YoY value depends on two
levels twelve months apart, a revised level changes the YoY value for that
month and the eleven following months — re-derive all affected points rather
than only the latest.

## Out of scope

- Fetch and parsing of the raw series — see `doc/datasources/macro.md`.
- Our KPIs built on top of world KPIs (trends, real interest rate, aggregates)
  — these are derived KPIs, not world KPIs.
- Storage, scheduling, and backfill depth — decided by the macro pipeline.

## Verification

Each entry names the raw series it consumes and the world KPI it produces; the
raw series appears in `doc/datasources/macro.md`'s mapping table, and the
produced KPI appears as an `ecb:`/`boj:`/`bls:`/`eurostat:`/`fred:` row in
`doc/kpis/world.md` §2.
