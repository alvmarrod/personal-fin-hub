# Macro Data Sources

## Purpose

Design for the backend modules that collect macro time series (policy
rates, CPI, money supply) not available via yfinance. Feeds the
`investing-com:` and `ecb:` rows in `doc/kpis/world.md` §2 (the
rows that were `<external>` before these sources existed). This document
defines the sources and extraction methods only — the actual fetch
implementation (HTTP client, parsing library, scheduling, retry/rate-limit
behavior) is implementation work, not specified here (Phase 1: docs only,
per this project's convention).

Each provider has its own extraction section below; a series belongs to
exactly one provider.

## Provider: Investing.com Economic Calendar

Each series is published on Investing.com's economic calendar as a page
with a table of historical releases. Relevant columns:

- **Release Date** — the date the figure was published.
- **Actual** — the reported value for that release (e.g. `1.00%`,
  `-0.10%`).

The table paginates via a "Show More" control at the bottom — older
history requires repeated pagination, not a single page load.

## Provider: ECB Data Portal

The ECB Data Portal exposes each series through a data-detail JSON API that
returns the full observation history as a JSON array — no pagination. Each
element is one release. Relevant fields:

- **`PERIOD`** — the observation period (ISO timestamp).
- **`OBS`** — the reported value (rounded; e.g. `3.2`).
- **`OBS_VALUE_AS_IS`** — the full-resolution value, kept for reference.
- **`LEGEND`** — release qualifier (e.g. `Provisional value`, `Normal value`).

Other fields (`SERIES`, `FREQUENCY`, `UNIT`, `OBS_STATUS`,
`TREND_INDICATOR`) are provider metadata.

## Series → URL mapping

| Series | doc/kpis/world.md target | Provider | URL | Status |
|---|---|---|---|---|
| BOJ policy rate | `policy_rate`, Japan | Investing.com | <https://www.investing.com/economic-calendar/boj-interest-rate-decision-165> | Wired |
| ECB deposit rate | `policy_rate`, Spain/Eurozone | Investing.com | <https://www.investing.com/economic-calendar/interest-rate-decision-164> | Wired |
| USA CPI YoY | `inflation_rate`, USA | Investing.com | <https://www.investing.com/economic-calendar/cpi-733> | Wired |
| Japan CPI YoY | `inflation_rate`, Japan | Investing.com | <https://www.investing.com/economic-calendar/japan-national-consumer-price-index-(cpi)-yoy-992> | Wired |
| Eurozone CPI YoY | `inflation_rate`, Spain/Eurozone | Investing.com | <https://www.investing.com/economic-calendar/cpi-68> | Wired |
| USA M2 money supply | `m2_growth`, USA — raw input to a YoY derivation | Investing.com | <https://www.investing.com/economic-calendar/us-m2-money-supply-1999> | Wired |
| Japan M2 money stock | `m2_growth`, Japan | Investing.com | <https://www.investing.com/economic-calendar/m2-money-stock-366> | Wired |
| Eurozone M2 | `m2_growth`, Spain/Eurozone | ECB Data Portal | <https://data.ecb.europa.eu/data-detail-api/BSI.M.U2.Y.V.M20.X.I.U2.2300.Z01.A> | Wired |
| Spain CPI YoY | none yet | Investing.com | <https://www.investing.com/economic-calendar/spain-consumer-price-index-(cpi)-yoy-961> | Reserved — not connected to any `doc/kpis/world.md` row. Using Spain's own CPI (instead of the Eurozone HICP) for the "Spain/Eurozone" scope, or splitting it into its own scope, is an open decision for later, not made here. |

## Output shape

Each series is stored as a plain (date, value) time series, in the units the
provider reports. Units are **not** uniform across series — they range from
percentages (policy rates, CPI, the ECB annual-growth-rate M2 series) to raw
levels (USA M2 money supply) — and values are not always clean. Where the
world KPI a series feeds is expressed in a different unit than the reported
value, the module stores the reported series and the conversion is a separate
normalization: see `doc/kpis/world_calc.md`.

## Out of scope

- Fetch implementation (HTML parsing, pagination handling, JSON field
  extraction, scheduling).
- Historical depth to backfill (decided at implementation time, per the
  market-cycle calibration/persistence needs in `doc/derived/macro.md` and
  `doc/systems/market_cycle/state_engine.md`).
- The Spain-specific CPI row above — reserved, not wired in.

## Verification

Each `Wired` row in `macro_data_source.md` maps to exactly one
`<external>`-turned-`investing-com:` or `ecb:` row in `doc/kpis/world.md` §2 by
concept (scope + kpi_name), not by literal URL matching — `doc/kpis/world.md`
carries no URLs by design.
