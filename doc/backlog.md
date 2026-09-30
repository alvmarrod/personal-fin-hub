# Implementation Backlog

Deferred, dependent work to pick up later. Each task resolves specific
decisions and produces concrete deliverables (usually a doc, a migration, or a
tested module). Tasks reference their FK documents so they can be picked up
without re-deriving design intent.

## Status Legend

| Symbol | Meaning |
|--------|---------|
| ⬜ | Pending |
| 🔄 | In progress |
| ✅ | Done |
| 🚧 | Blocked |

## Task Overview

| ID | Task | Depends on | Status |
|----|------|-----------|--------|
| B1 | Macro pipeline design (plan + schema + sources) | — | ✅ |
| B2 | Planned use cases UC-52 / UC-53 | B1 | ⬜ |
| B3 | Backend schema + migration (`macro_series`) | B1 | ✅ |
| B4 | Macro sync service + scheduler | B3 | ✅ |
| B5 | Investment Market Cycle state engine (backend) | B3 | ✅ |
| B6 | Analytics endpoint `GET /analytics/investment-market-cycle` | B5 | ✅ |
| B7 | Frontend view `/investment-market-cycle` | B6 | ✅ |

Critical path: **B1 ✅ → B3 ✅ → B5 ✅ → B6 ✅ → B7 ✅** (complete).

B2 (planned use cases) is the only remaining item in this feature.

---

## B1 · Macro Pipeline Design

**Status**: ✅ · **Depends on**: none

Design record for the macro data pipeline. Delivered as
`doc/datasources/macro.md` (sources, extraction, storage shape). The pipeline
is implemented by B3 + B4. Remaining source gap: `yield_curve_slope` (Japan,
Spain/Eurozone) and Japan CPI still have no source.

### Decisions resolved

1. **Storage model.** `macro_series` (registry: slug, provider, name, unit,
   source_url, update_frequency, last_synced_at) + `macro_series_observations`
   (`slug`, `obs_date`, `value`, unique on `slug+obs_date`), mirroring the
   `prices` / `currencies` time-series and upsert pattern. `provider` is
   nullable so an unsourced series can exist.
2. **Sources per market and indicator.** Per
   `doc/datasources/macro.md`:
   - Inflation: USA CPI YoY → BLS (`CUUR0000SA0`); Eurozone CPI YoY →
     Eurostat (`prc_hicp_manr`). Japan CPI YoY has no source yet. Global
     aggregate = derived.
   - Policy rate: USA keeps the `yfinance:^IRX` (13-week bill proxy); Japan →
     Bank of Japan (`IR01`); Eurozone → ECB Data API (`FM.D.U2.EUR.4F.KR.DFR.LEV`).
   - M2 growth: USA → FRED (`M2SL`, level, YoY derived); Japan → Bank of Japan
     (`MD02`, YoY); Eurozone → ECB Data Portal (YoY).
3. **Cadence and lag.** Monthly publication, about one-month release lag.
4. **Staleness and fallback.** Sync keeps last known data on outage
   (additive upsert); per-series errors surface in the sync result. Low-confidence
   flags already exist in `doc/derived/macro.md` (trend direction).

### Deliverables

- ✅ `doc/datasources/macro.md` — sources table, extraction, output shape.
- ✅ `doc/kpis/world.md` — resolved `<external>` tags to concrete sources.

---

## B2 · Planned Use Cases

**Status**: ⬜ · **Depends on**: B1

Use cases for the Investment Market Cycle feature, per project convention
(new features are modeled in the use-case docs). The B1 storage decision feeds
UC-53 modeling.

### Decisions to resolve

1. **Sync modeling** (UC-53): idempotent upsert, fixed-UTC monthly schedule,
   pacing, no piggybacking. Mirror UC-46/47.
2. **View read modeling** (UC-52): read-only, no currency conversion (macro
   KPIs are rates and percentages).

### Deliverables

- `doc/use_cases.md` — master-table rows for UC-52 and UC-53.
- `doc/uc_9_planned.md` — UC-52 View Investment Market Cycle and UC-53 Sync
  Macro Indicators bodies.

---

## B3 · Schema and Migration

**Status**: ✅ · **Depends on**: B1

Implemented. Migrations `024_macro_series` (tables + seed), `025_ecb_deposit_rate_source`
and `026_official_macro_sources` (provider CHECK widened to
`ecb`/`boj`/`bls`/`eurostat`/`fred`, nullable provider/source_url, official-source
repointing).

### Decisions resolved

1. Column set per the `doc/datasources/macro.md` contract.
2. Unique / upsert key: `slug` + `obs_date`.
3. Index `idx_macro_obs_slug` for time-series reads.

### Deliverables

- ✅ Migration files (`024`–`026`).
- ✅ Query helpers in `backend/db/queries.py`.
- ✅ Schema tests.

---

## B4 · Macro Sync Service and Scheduler

**Status**: ✅ · **Depends on**: B3

Implemented: fetch, normalize, and store the macro series on a schedule.

### Decisions resolved

1. Per-provider fetchers: official sources — ECB Data API, Bank of Japan,
   BLS, Eurostat, FRED (`backend/services/macro_client.py`).
2. Value normalization: YoY derived at the source where the KPI is a growth
   rate (BLS CPI-U, BOJ M2); change-point reduction for policy-rate series.
3. Pacing and schedule: twice-daily cron (`macro.sync_hours_utc`) with a
   12-hour freshness skip.
4. Staleness: provider outage keeps last known data (additive upsert).
5. Manual trigger (`scripts/macro_sync.py`) and scheduled trigger
   (`macro_sync` APScheduler job).

### Deliverables

- ✅ Fetcher and service (`macro_client.py`, `macro_sync_svc.py`).
- ✅ APScheduler job.
- ✅ Tests.

---

## B5 · State Engine Backend

**Status**: ✅ · **Depends on**: B3

Implemented in `backend/services/market_cycle_engine.py` per
`doc/systems/market_cycle/state_engine.md`.

### Decisions resolved

1. Signal computation: `real_rates_high`/`_low`, `real_rates_declining`,
   `real_rates_climbing`, `hikes_resumed`, `hikes_stopped`, `cuts_stopped`,
   `first_cut_detected` (state-gated, persistent).
2. Transition statuses by consecutive months held (emerging 1 / near 2 /
   triggered 3), configurable.
3. Tie-hold rule and `ambiguous_confirmation`.
4. Per-scope configuration (`market_cycle.*` in `config.json`); the engine is a
   stateless replay.
5. Entry-signal derivation (`favourable` = High Real Rates; `strong` = First
   Rate Cut).

### Deliverables

- ✅ Engine module and unit tests (`tests/test_market_cycle_engine.py`).

---

## B6 · Analytics Endpoint

**Status**: ✅ · **Depends on**: B5

Implemented: `GET /analytics/investment-market-cycle?scope=` returns the engine
status object.

### Decisions resolved

1. Response contract: the §9 object as a Pydantic `MarketCycleStatus`.
2. `scope` validation: lowercase keys (`usa`, `japan`, `spain-eurozone`,
   `global`); unknown/unsourced scope → 400.
3. No-data: 400; the view renders a warning + empty state.

### Deliverables

- ✅ Endpoint and tests (`tests/test_market_cycle_endpoint.py`).
- ✅ `doc/subsystems/api_endpoints.md` switched to implemented.

---

## B7 · Frontend View

**Status**: ✅ · **Depends on**: B6

Implemented: the `/investment-market-cycle` page per its view spec.

### Decisions resolved

1. Diagram: hand-built SVG.
2. Animation: CSS pulse by status, honoring `prefers-reduced-motion`.
3. Colour mapping from the view spec's semantic scheme.
4. i18n keys with `en`/`es` parity.
5. Empty-state UI + scope selector (wired scopes enabled, others disabled).

### Deliverables

- ✅ Page + components (`StateDiagram`, `MarketCycleLegend`) and tests.
- ✅ Route registered in `doc/subsystems/UI.md`.
- ✅ i18n keys in both dictionaries.
- ✅ Frontend tests + tutorial.

---

## Non-Blocking Follow-ups

- Auto-refresh interval on the view (a later version may poll).
- Future `austrian-market-cycle` HLD. Separate deliverable. Its KPIs already
  share `doc/kpis/world.md`.
