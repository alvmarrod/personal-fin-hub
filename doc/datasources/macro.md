# Macro Data Sources

## Purpose

Design for the backend modules that collect macro time series (policy
rates, CPI, money supply) not available via yfinance. Feeds the `ecb:`,
`boj:`, `bls:`, `eurostat:`, and `fred:` rows in `doc/kpis/world.md` §2 (the
rows that were `<external>` before these sources existed). This document
defines the sources and extraction methods only — the actual fetch
implementation (HTTP client, parsing, scheduling, retry/rate-limit behavior)
is implementation work.

Each provider has its own extraction section below; a series belongs to
exactly one provider. All sources are official, machine-readable APIs —
no HTML scraping, no browser automation, no API keys.

## Provider: ECB Data API

Two ECB endpoints are used:

- **data-api (SDMX-JSON)** — `data-api.ecb.europa.eu/service/data/…`. The
  response is SDMX-JSON: `dataSets[].series[].observations` keyed by the index
  of the `TIME_PERIOD` observation dimension. Used for the deposit-facility
  "date of changes" series.
- **Data Portal (data-detail JSON)** — `data.ecb.europa.eu/data-detail-api/…`.
  Returns the full observation history as a JSON array. Elements carry
  `PERIOD`, `OBS`, `OBS_VALUE_AS_IS` (full-resolution, preferred), and
  `LEGEND`.

## Provider: Bank of Japan (Time-Series Data Search API)

`www.stat-search.boj.or.jp/api/v1/getDataCode?db=<DB>&code=<CODE>` returns JSON:
`RESULTSET[].VALUES` with parallel `SURVEY_DATES` and `VALUES` arrays. Dates are
`YYYYMMDD` (daily) or `YYYYMM` (monthly).

- **Policy rate**: db `IR01`, code `MADR1Z@D` ("The Basic Discount Rate and
  Basic Loan Rate", daily, percent per annum). The daily series repeats the rate
  until it changes; the client keeps only the change points, so the stored
  series is one observation per policy-rate change.
- **M2 money stock**: db `MD02`, code `MAM1NAM2M2MO` ("M2/Average Amounts
  Outstanding", monthly, 100 million yen). Stored as the reported level; the
  YoY growth rate is a world-KPI normalization (`doc/kpis/world_calc.md`).

## Provider: U.S. Bureau of Labor Statistics (Public Data API)

`api.bls.gov/publicAPI/v2/timeseries/data/` (POST JSON, keyless). Series
`CUUR0000SA0` is the CPI-U, U.S. city average, All items, monthly, not
seasonally adjusted (index). An unregistered v2 query is capped at 10 years, so
the client requests the most recent 10 years. Stored as the reported index; the
YoY growth rate is a world-KPI normalization (`doc/kpis/world_calc.md`).

## Provider: Eurostat

`ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_manr`
(JSON-stat, keyless). Dataset `prc_hicp_manr` is "HICP - monthly data (annual
rate of change)"; dimensions `geo=EA` (Euro area), `coicop=CP00` (All-items
HICP), `unit=RCH_A` (annual rate of change). The response's `value` maps a flat
observation index to the value, and `dimension.time.category.index` maps period
labels to indices. The value is already the annual rate — no conversion.

## Provider: Federal Reserve H.6 via FRED

`fred.stlouisfed.org/graph/fredgraph.csv?id=M2SL` (CSV, keyless). Series `M2SL`
is M2 Money Stock, monthly, seasonally adjusted, billions of dollars (level).
Stored as-is; the YoY growth rate is a world-KPI normalization
(`doc/kpis/world_calc.md`).

## Provider: External Market API (market symbol)

A market symbol served by the External Market API (`doc/datasources/market_api.md`)
used as a macro series: the CLOSE value per date. History is requested in
≤1-year windows (the provider's max span). Used for the USA policy-rate proxy.

- **USA 13-week T-bill yield**: symbol `^IRX`, daily, percent per annum. This is
  a *proxy* for the USA `policy_rate` (the Fed funds target is not published as
  a plain series here). Stored as reported; no normalization.

## Series → source mapping

| Series | doc/kpis/world.md target | Provider | Series / code | Status |
|---|---|---|---|---|
| USA 13-week T-bill yield | `policy_rate`, USA — proxy | External Market API | `^IRX` | Wired |
| BOJ policy rate | `policy_rate`, Japan | Bank of Japan | `IR01` / `MADR1Z@D` | Wired |
| ECB deposit rate | `policy_rate`, Spain/Eurozone | ECB Data API | `FM.D.U2.EUR.4F.KR.DFR.LEV` | Wired |
| USA CPI YoY | `inflation_rate`, USA | BLS | `CUUR0000SA0` | Wired |
| Japan CPI YoY | `inflation_rate`, Japan | — | — | **No datasource yet** (unassigned) |
| Eurozone CPI YoY | `inflation_rate`, Spain/Eurozone | Eurostat | `prc_hicp_manr` (EA/CP00/RCH_A) | Wired |
| USA M2 money supply | `m2_growth`, USA — level, YoY derived downstream | FRED | `M2SL` | Wired |
| Japan M2 money stock | `m2_growth`, Japan — level, YoY derived in `doc/kpis/world_calc.md` | Bank of Japan | `MD02` / `MAM1NAM2M2MO` | Wired |
| Eurozone M2 | `m2_growth`, Spain/Eurozone | ECB Data Portal | `BSI.M.U2.Y.V.M20.X.I.U2.2300.Z01.A` | Wired |
| Spain CPI YoY | none yet | — | — | Reserved — not wired in |

## Output shape

Each series is stored as a plain (date, value) time series. Units are **not**
uniform: percentages (policy rates, CPI YoY, the ECB annual-growth-rate M2
series) and levels (USA M2 money supply). Where the stored value differs from
the world KPI a series feeds (a level that the KPI expresses as YoY), the
conversion is either done at the source (Japan M2, USA CPI) or documented as a
normalization in `doc/kpis/world_calc.md` (USA M2).

## Out of scope

- Historical depth to backfill (decided at implementation time, per the
  market-cycle calibration/persistence needs in `doc/derived/macro.md` and
  `doc/systems/market_cycle/state_engine.md`).
- The Spain-specific CPI row above — reserved, not wired in.
- Japan CPI YoY — no official source wired yet.

## Implemented (Phase 1)

The retrieval and storage layer is implemented (tables `macro_series` and
`macro_series_observations`; see `backend/services/macro_client.py` and
`backend/services/macro_sync_svc.py`).

- **Transport**: plain HTTP against official JSON/CSV/SDMX endpoints. No HTML
  scraping, no browser automation, no API keys.
- **Raw storage**: series are stored **as reported** (a level or index where the
  provider publishes one). All raw→KPI conversion (YoY) is a separate
  normalization in the world-KPI layer (`doc/kpis/world_calc.md`), not done here.
- **Change points**: the ECB deposit-rate and BOJ policy-rate daily series are
  reduced to change points (one observation per rate change).
- **Refresh**: twice daily (config `macro.sync_hours_utc`), with a 12-hour
  freshness skip (`macro.sync_freshness_hours`).
- **No datasource**: a series with a NULL provider/source_url (Japan CPI today)
  is skipped by the sync.
- **Eurostat recency**: `prc_hicp_manr` can lag by a few months; a different
  source may be needed later if greater recency is required.

## Verification

Each `Wired` row in this document maps to exactly one `ecb:`/`boj:`/`bls:`/
`eurostat:`/`fred:` row in `doc/kpis/world.md` §2 by concept (scope +
kpi_name), not by literal URL matching — `doc/kpis/world.md` carries no URLs by
design.
