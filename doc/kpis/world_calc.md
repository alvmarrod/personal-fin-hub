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

A raw series is fetched and parsed per `doc/datasources/macro.md`. When the
world KPI it feeds is expressed in a different unit than the reported series,
the module stores the reported series and the conversion lives here. World
KPIs that are already reported in their final form (CPI, policy rates, Japan
M2, Eurozone M2) need no entry in this file — they are passthrough, stored as
reported.

## Normalizations

| World KPI | Raw series | Normalization |
|---|---|---|
| `m2_growth`, USA | USA M2 money supply (level), `fred:usa-m2-money-supply` (`M2SL`) | Year-over-year growth (below) |

Two other series are already normalized **at the source** (the client derives
YoY before storage, so this file has no entry for them): USA CPI YoY
(`bls:usa-cpi-yoy`, from the CPI-U index) and Japan M2 YoY (`boj:japan-m2-yoy`,
from the M2 level). Eurozone CPI YoY (`eurostat:eurozone-cpi-yoy`) and the
policy rates are reported in their final form.

### Year-over-year growth from a level series

```text
yoy_t = (level_t / level_{t-12} - 1) * 100
```

- `level_t` is the level for the observation month; `level_{t-12}` is the level
  for the same calendar month one year earlier.
- Cadence is monthly. An observation with no matching month twelve periods
  back has no YoY value yet.
- The result is a percentage, consistent with the other rate series.

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
