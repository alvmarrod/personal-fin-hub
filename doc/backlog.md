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
| B1 | Macro pipeline design (plan + schema + sources) | — | ⬜ |
| B2 | Planned use cases UC-52 / UC-53 | B1 | ⬜ |
| B3 | Backend schema + migration (`macro_indicators`) | B1 | ⬜ |
| B4 | Macro sync service + scheduler | B3 | ⬜ |
| B5 | Investment Market Cycle state engine (backend) | B3 | ⬜ |
| B6 | Analytics endpoint `GET /analytics/investment-market-cycle` | B5 | ⬜ |
| B7 | Frontend view `/investment-market-cycle` | B6 | ⬜ |

Critical path: **B1 → B3 → B5 → B6 → B7**.

B2 and B4 are parallelizable with the critical path.

---

## B1 · Macro Pipeline Design

**Status**: ⬜ · **Depends on**: none

Design decision record for the macro data pipeline. The pipeline is the
critical path for the Investment Market Cycle: `yield_curve_slope` (Japan,
Spain/Eurozone) has no source, and the sourced series still need a fetch and
storage pipeline (`doc/datasources/macro.md` defines the sources).

### Decisions to resolve

1. **Storage model.** Recommended: a new `macro_indicators` table with
   `scope`, `indicator`, `date`, `value`, `source`, mirroring the
   `prices` / `currencies` time-series and upsert pattern. Rejected
   alternatives: reuse `prices` (OHLCV per market-asset, wrong fit); compute
   on the fly from the external API (trend and persistence need history).
2. **Sources per market and indicator.** Per
   `doc/datasources/macro.md`:
   - Inflation: USA / Japan / Eurozone CPI YoY → investing.com economic
     calendar. Global aggregate = derived.
   - Policy rate: USA keeps the `yfinance:^IRX` (13-week bill proxy); Japan /
     Eurozone → investing.com (BoJ policy rate, ECB deposit rate).
   - M2 growth: USA / Japan → investing.com (USA level, YoY derived);
     Eurozone → ECB Data Portal (YoY).
3. **Cadence and lag.** Monthly publication, about one-month release lag.
4. **Staleness and fallback.** Extend the `calculations/finance.md` §16.4
   closest-in-time and stale conventions to a monthly rhythm. Low-confidence
   flags already exist in `doc/derived/macro.md` (trend direction).

### Deliverables

- `doc/plans/macro_data_pipeline.md` — sources table, cadence, sync
  semantics, storage decision and rationale, fallback rules.
- `doc/subsystems/database.md` — `macro_indicators` schema.
- `doc/kpis/world.md` — resolve `<external>` tags to concrete
  sources and reference the pipeline.

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

**Status**: ⬜ · **Depends on**: B1

Implement the `macro_indicators` table.

### Decisions to resolve

1. Column set and types per the `database.md` contract from B1.
2. Unique / upsert key (`scope` + `indicator` + `date`).
3. Index strategy for time-series reads.

### Deliverables

- Migration file.
- ORM model.
- Schema tests.

---

## B4 · Macro Sync Service and Scheduler

**Status**: ⬜ · **Depends on**: B3

Fetch, normalize, and store the macro series on a schedule.

### Decisions to resolve

1. Per-provider fetchers: investing.com economic calendar, ECB Data Portal.
2. Value normalization to annualized percentages.
3. Pacing and schedule (monthly, fixed UTC).
4. Staleness metadata, RateMetadata-style.
5. Manual trigger vs. scheduled trigger. Mirror UC-46/47.

### Deliverables

- Fetcher and service.
- APScheduler job.
- Tests.

---

## B5 · State Engine Backend

**Status**: ⬜ · **Depends on**: B3

Implement the Investment Market Cycle state engine per its contract.

### Decisions to resolve

1. Signal computation: `real_rates_high`, `real_rates_low`,
   `real_rates_declining`, `hikes_resumed`, `hikes_stopped`, `cuts_stopped`,
   `first_cut_detected`.
2. Transition evaluation and statuses (`Inactive` / `Emerging` / `Near` /
   `Triggered`).
3. Tie-hold rule and `ambiguous_confirmation`.
4. Per-scope configuration.
5. Entry-signal derivation (`favourable`, `strong`).

### Deliverables

- Engine module and unit tests per
  `doc/systems/market_cycle/state_engine.md` §1–§9.

---

## B6 · Analytics Endpoint

**Status**: ⬜ · **Depends on**: B5

Expose the engine status object.

### Decisions to resolve

1. Response contract: the engine §9 JSON.
2. `scope` parameter validation.
3. No-data empty-state behavior.

### Deliverables

- `GET /analytics/investment-market-cycle?scope=` and tests.
- `doc/subsystems/api_endpoints.md` — switch the endpoint from planned to
  implemented.

---

## B7 · Frontend View

**Status**: ⬜ · **Depends on**: B6

Build the Investment Market Cycle page per its view spec.

### Decisions to resolve

1. Diagram rendering: SVG; circular vs. horizontal.
2. Animation mapping: pulse / blink for `Emerging` / `Near` / `Triggered`.
3. Colour mapping from the view spec.
4. i18n keys with `en`/`es` parity.
5. Empty-state UI and scope selector.

### Deliverables

- Page and components per
  `doc/subsystems/views/investment_market_cycle.md`.
- Route registration in `doc/subsystems/UI.md`.
- i18n keys in both dictionaries.
- Frontend tests.

---

## Non-Blocking Follow-ups

- Auto-refresh interval on the view (a later version may poll).
- Future `austrian-market-cycle` HLD. Separate deliverable. Its KPIs already
  share `doc/kpis/world.md`.
