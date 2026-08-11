# Plan — Market API Outage UX (Plan D)

**Status**: active
**Depends on**: External API Resilience (Phases 1–4, shipped in backend `0.9.0` + frontend `0.7.0`).
**Scope**: user-facing signals when the Market API is down or data is old. No changes to the retry/circuit/health backend machinery already shipped.

## Design decisions

- **Two independent badges**, never conflated:
  1. **Freshness badge — always present** (authed, global): *"Market data from {date}"*. Represents the newest stored market **price** timestamp (`MAX(prices.timestamp)`), not the breaker's `last_success_at` (API success ≠ fresh data). Shows "No market data yet" when the `prices` table is empty.
  2. **Availability badge — only when down**: *"Market API not available"*. Driven by the `/health` poll; hidden on recovery. Debounced (2 consecutive failed polls) to avoid flicker.
- **Data source**: both badges read from `/health` (polled every 60s from the frontend). Backend adds `checks.market_data_last_updated` (ISO timestamp of newest price row, `null` when none) — no new endpoints.
- **Scope**: freshness badge covers **prices only**. Currency/fx rates keep their existing signal (income page `exchangeRateNote`).
- **Formatting**: timezone-aware via the existing `formatTimestamp()` in `$lib/preferences/timezone.svelte.ts` (user's selected timezone, not server UTC).
- **Keep existing Phase 3 callout** on Portfolio Assets (transaction-fallback / no-price) — different nuance ("valued at purchase price"), additive to the badges.
- **Svelte 5 runes only**; i18n keys added to EN + ES; no backend behavior change to retry/circuit/fail-fast.

## Part A — Fix the silent no-op (open-circuit sync)

**Problem**: when the breaker is open, `POST /market/sync-prices` and `POST /currencies/sync` return HTTP 200 with `circuit_open: true` + `skipped`; the sync handlers ignore the body → the button silently "succeeds".

**Change** (frontend only; backend already sends the data):

- `portfolio-assets/+page.svelte` `handleSyncPrices()` and `currencies/+page.svelte` `handleSync()`: read the response body; if `resp.circuit_open === true`, set a `syncWarning` state (not `error` — keeps the page content visible) and render a warning callout (`.rate-warning` style): *"Market data is temporarily unavailable. Nothing was synced — using cached data."*
- i18n: `portfolioAssets.syncUnavailable`, `currencies.syncUnavailable` (EN/ES).

## Part B — Health polling store + availability badge

**Problem**: `/health` exists but only Docker uses it; the app never tells the user the API is down.

**Change**:

- New runes store `frontend/src/lib/stores/health.svelte.ts` (pattern like `$lib/preferences/currency.svelte.ts`): module-scope `$state` with `marketApi` (`ok`/`unavailable`/`unknown`), `circuit`, `marketDataLastUpdated` (`string | null`), `lastChecked`. Exports `initHealthPolling()` + `dismissOutage()`.
- `initHealthPolling()`: `api.get('/health')` on start + every 60s; parse `checks.market_api`, `checks.market_api_circuit`, `checks.market_data_last_updated`. **Debounce**: only flip to `unavailable` after 2 consecutive failed/unhealthy polls; recover immediately on a healthy poll. Poll error → `unknown` (badge hidden — no false alarm while the app itself is offline).
- New `frontend/src/lib/components/HealthBadges.svelte`: renders in `+layout.svelte` between `<Header>` and `<main>` (authed branch only):
  - Freshness badge (always): "Market data from {date}" / "No market data yet".
  - Availability badge (only when `unavailable`): "Market API not available", dismissible per session.
- i18n: `health.marketDataTitle` ("Market data from {date}"), `health.marketDataNone` ("No market data yet"), `health.marketApiUnavailable`, `health.dismiss` (EN/ES).
- Call `initHealthPolling()` from the layout, guarded, once authed.

## Part C — (replaced) two-badge design above

The original "stale price threshold callout" is dropped in favor of the persistent freshness badge.

## i18n keys added (EN + ES)

`portfolioAssets.syncUnavailable`, `currencies.syncUnavailable`, `health.marketDataTitle`, `health.marketDataNone`, `health.marketApiUnavailable`, `health.dismiss`.

## Backend change

- `backend/routes/health.py`: add `checks["market_data_last_updated"]` = `MAX(timestamp)` over `prices` (ISO string or `null`). One query; no new endpoint.
- New test in `tests/test_health.py`: field present, ISO when prices exist, `null` when none.

## Tests (frontend)

- Sync open-circuit warning on Portfolio Assets + Currencies pages (Part A).
- Health store: parses `/health`; debounce (1 bad poll → still ok, 2 → unavailable); recovers on healthy poll.
- HealthBadges: freshness badge renders date / "No market data yet"; availability badge appears only when unavailable and honors dismiss.
- Existing `src/lib/tests/portfolio-assets.test.js` tests stay green (callout unchanged).

## Gates

`bun run test`, `bun run build`, `bun run validate-i18n`; backend `ruff` + `mypy` + `pytest` re-run (regression). `python3 scripts/changelog-check.py` (no version bump unless the user opts to fold this into a release).

## Out of scope

Fx-rate freshness in the global badge (kept as the income-page note); threshold-based "stale" warnings; changes to retry/circuit/fail-fast behavior.
