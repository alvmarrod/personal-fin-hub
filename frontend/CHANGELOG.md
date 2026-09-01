# Changelog

All notable changes to the frontend service.

## [0.20.0] — 2026-09-01

### Changed

- **Balance Snapshots grouped by Entity and Currency**: the balance-snapshots table now groups snapshots by (entity, currency) pair instead of listing each snapshot as a flat row. Each group row shows the entity name, currency, latest amount, latest date, latest notes, and a snapshot count badge. A chevron (▶/▼) expands the group to reveal a nested table with all individual snapshots for that pair, sorted most-recent-first. Edit and delete actions live on the individual snapshot rows inside the expanded sub-table. Entity filter and pagination operate on groups. Amounts use `formatAmount` with the currency symbol appended (e.g. `€1,234`), and the sub-table columns have improved spacing.

- **Portfolio Assets buy-lot sub-table in display currency**: the expanded buy-lot sub-table now shows two money columns — a Native Amount column (each lot's cost basis in its original currency with that currency's symbol) and a Display Amount column (the same cost basis converted to the page's selected currency at the buy date, with the display-currency symbol). The separate plain currency-code column was removed, and the sub-table gained spacing between columns (via `border-spacing`), matching the Tax and Balance Snapshots sub-tables.

### Fixed

- **Tax expanded-table currency display**: the per-item sub-table now renders each column in the correct currency. The Native Amount column uses the item's own currency symbol (e.g. `$` for a USD transaction even when the page is in EUR) instead of the display-currency symbol, matching the documented "original currency" semantics. The Tax Owed column shows the actual withheld amount in its native currency for confirmed-source items and the model-computed amount in the display currency for computed items — previously both were prefixed with the display-currency symbol, which made confirmed values look as though they should convert when changing the page currency. The sub-table also gained spacing between columns (via `border-spacing`) to match the balance-snapshots sub-table.

## [0.21.0] — 2026-08-30

### Fixed

- **Tutorials re-played on every page visit**: leaving a page through its final navigate step dropped the tutorial's active state without marking the page seen, so every chained page re-started its tutorial on the next visit (with a spurious "paused" toast on each hop). A page is now marked seen the moment its tutorial starts, and a navigate-step handoff calls `finish()` so the cross-page chain stays alive. No page auto-plays its tutorial more than once, regardless of whether it was finished, skipped, or abandoned.

## [0.20.0] — 2026-08-30

### Fixed

- **Test noise from chart rendering**: pages that render Chart.js charts under jsdom logged an unhandled `getContext` warning and a "Failed to create chart" error for every test. A vitest setup file now stubs the 2D canvas context and mocks `chart.js`, so tests run clean (168 passing, zero stderr noise).

## [0.19.0] — 2026-08-30

### Changed

- **Adaptive amount formatting**: amounts now render through a shared `formatAmount(value, currency)` helper that uses the app locale (`en-US` / `es-ES`) and adjusts decimal precision to magnitude — 0 decimals for large amounts (≥ 1,000; JPY ≥ 10,000), 2 for regular amounts, 3 for sub-unit values. Trailing zeros are never shown.

### Fixed

- **JPY grouping on the Dividends and Income pages**: the transaction tables showed the thousands separator only for amounts of 10,000 and above (the locale default). Grouping is now always shown, so `8.340` JPY renders consistently; the by-asset table uses the same formatting.
- **Realized Gains (FIFO) table on the Performance page**: the sell price, sell total, cost basis, and realized P&L cells now render through the shared `formatAmount(value, currency)` helper instead of raw `toLocaleString`, so they follow the app locale and magnitude-based decimal precision like the Income and Dividends tables.

## [0.18.0] — 2026-08-28

### Added

- **Per-buy drill-down on Portfolio Assets**: rows with an open position gain a chevron (▶/▼) that expands a nested table — date, broker, category, remaining quantity, unit price, total, currency — showing how the position splits across brokers. Fully consumed buys do not appear. EN/ES localization.

## [0.17.0] — 2026-08-27

### Changed

- **Cash flow expandable detail rows**: the cash-flow page now renders three levels of expandable rows — Inflows/Outflows totals → periods (most recent first, each with its own subtotal) → component types (INCOME, INVESTMENT_SELL / MONEY_OUT, INVESTMENT_BUY) with per-currency totals → individual transactions (lazy-loaded inline table with link to /transactions). The stacked bar chart uses grouped stacks to show type breakdown while preserving the inflow/outflow distinction. `StackedBarChart` gains an optional `stack` prop for grouped stacking.

### Fixed

- **Dates now follow the selected app locale**: all date rendering (period labels, transaction/dividend/income tables, rate and price warnings, chart axis dates) used the browser language via `toLocaleDateString(undefined, ...)`. A new shared formatter (`$lib/utils/format.svelte`) passes the app locale (`en-US` / `es-ES`) so dates render in the user-selected language (e.g. "enero de 2025" in Spanish).

## [0.16.0] — 2026-08-27

### Added

- **Sortable "Dividends by Asset" table**: all four columns (Asset, Currency, Total, Payments) are clickable to sort ascending/descending (▲/▼ indicator), matching the existing sortable tables — numeric columns sort descending on first click, text columns ascending; defaults to highest total dividends first. 4 new tests.
- **Currency selector on the Dividends page**: a display-currency selector (like the Performance page) now sits in the header; it writes the global display-currency preference and affects the top cards **and** the "Dividends by Asset" section — the "Total Dividends" card, the distribution chart, and the table's "Amount" column all use per-payment-date converted sums, while a new "Original Amount" column keeps each asset's native-currency total (replacing the removed "Currency" column). 4 new tests.

### Changed

- **Shared table-sort helper**: the sortable-table logic (previously duplicated in Performance and Portfolio Assets) is extracted into a reusable `createTableSort` rune helper (`$lib/utils/tableSort.svelte.js`) plus a `SortableTh` header component; all three tables now use it. Behavior unchanged.

## [0.15.0] — 2026-08-23

### Added

- **Dividends & Interest on the Performance page**: new compact cards in an "Investment Income" group — all-time dividends (with a compact "▲ X% all-time" yield sub-line) and all-time interest, both converted at each payment date's rate via the new backend summary fields.
- **Metric groups**: the performance cards are now visually grouped by bordered sections with a colored limit line and tab label — Portfolio (blue) shares the first row with Total (amber, weighted 3:2), with Unrealized (light blue), Realized · Trading (green) and Investment Income (purple) side-by-side below. New reusable `MetricGroup` component and a `compact` variant of `MetricCard` (performance page only; other pages unchanged). 6 new tests.

### Changed

- **Performance page grouped into two realized/unrealized bands**: the metric groups now render as two full-width rows — a **Portfolio** band wrapping the Unrealized sub-group, and a **Realized** band (renamed from "Total", green line) wrapping the Realized · Trading (now amber) and Investment Income sub-groups inline. All cards of a band share one visual row; `MetricGroup` accepts an optional `class` for such layouts.
- **Total Return is realized-only**: the Total Return card (%) plus the amount card show realized trading P&L + dividends over invested historic — unrealized P&L no longer enters the sum (tracked separately in the Portfolio band). Realized P&L cards are relabeled "(Trading)" to make clear dividends are not part of them.
- **Realized Gains table relabeled**: the section title is now "Trading Realized Gains (FIFO)" to match the trading-only card relabels; content unchanged.
- **Inline rate-fallback warning**: the "closest available rate" notice moved out of the page body into a small amber chip inside the header line (between the title and the currency selector), listing the affected currencies with their earliest missing date (e.g. ": USD (11/3/2024), GBP (1/10/2025)") — freeing a full banner row of vertical space while pinpointing which rates to add.
- **Metric group spacing cleanup**: removed all `margin-top` from `MetricGroup` (base rule plus the performance band overrides) — inter-group spacing now comes solely from layout gaps, so groups sit flush with their row.
- **Card height & vertical alignment**: metric cards no longer stretch to the tallest sibling — each card collapses to its natural content height (e.g. Portfolio Value stays compact next to the 3-line Dividends card) and is vertically centered within its row; the bordered sub-group frames keep filling the row so their outlines stay aligned, and stretched frames pass their full height to the inner card grid so centering applies across the whole row.

## [0.14.0] — 2026-08-21

### Added

- **Performance page `Realized P&L %` card**: new metric card next to Total Return showing realized P&L as a percentage of the cost basis of sold shares (FIFO), mirroring the Unrealized P&L % card. Backed by the new `realized_pl_pct` field from `GET /analytics/performance`; green/red variant and tooltip included, EN/ES locales and tutorial mock updated.
- **Sortable Realized Gains table**: all columns of the Performance page's realized gains table are now clickable to sort ascending/descending (▲/▼ indicator), matching the Portfolio Assets table behavior — numeric columns sort descending on first click, others ascending; defaults to newest sell first. 3 new tests.

## [0.13.1] — 2026-08-20

### Changed

- **Sidebar menu compact sizing**: width uses `clamp(180px, 12vw, 240px)`, nav items use smaller padding and tighter gaps with relative units.

### Fixed

- **Sidebar menu scrollable**: added `overflow-y: auto` so the menu scrolls when content exceeds viewport height.
- **Income chart hides projected series without schedules**: the "Income by type" chart no longer renders projected datasets for categories without active schedules, eliminating zero-value projected series for dividends, interest, and cashback.
- **Portfolio Assets JPY decimals**: current value column now shows no decimal places when the display currency is JPY.
- **Portfolio Assets asset name column**: reduced max-width from 360px to 310px and applied smaller font-size (0.75rem) to better handle long asset names.
- **Tax page dividend asset name**: expanded dividend items now display the asset/entity name instead of the raw transaction ID.

## [0.13.0] — 2026-08-20

### Added

- **`cashback` income category**: new `cashback` option available in all income transaction and schedule modals, with its own i18n label and category badge hue.

### Changed

- **Income Sources page groups by category**: rows now split per `entity + currency + category` (instead of `entity + currency`), each showing a single category badge.

### Fixed

- **Portfolio Assets page refreshes after Sync Prices** (carried from 0.12.1): the "Sync Prices" button reloads the full portfolio asset list after the market API responds, so the table reflects updated prices without a manual browser refresh.

## [0.12.0] — 2026-08-20

### Changed

- **Tax page uses extended endpoint**: switched from `/analytics/taxable-pnl` to `/analytics/taxable-pnl-extended` for richer per-category tax breakdown.
- **Performance page sends the active locale**: `/performance` now passes the user's locale to `GET /analytics/performance` so the backend can infer the default fiscal rule (`es` → Spain, `ja` → Japan, else default).
- **Updated P&L tooltips**: `hintRealizedPL` and `hintTotalInvestedHistoric` now explain that realized P&L is converted at each sale date's rate and invested historic at each purchase date's rate (no fiscal rule).
- **Performance P&L cards show direction on the value**: Unrealized P&L %, Unrealized P&L, Total Return, and Realized P&L cards now render an up/down arrow in front of the main value and color it green/red (the delta styling previously reserved for the dashboard's comparison subtitle), since this page has no period-based comparison subtitle. `MetricCard` gained a `valueVariant` prop for this.

### Added

- **Tax page**: a new `/tax` route (sidebar "Tax" entry) shows taxable P&L per fiscal year — realized gains and dividends — with a ruleset and display-currency selector. Rate-fallback warnings reuse the existing callout pattern. New EN/ES keys under `tax.*` + `sidebar.tax`.
- **Tax Rates in Settings**: a new "Tax Rates" CRUD section lets the user create, edit, and delete progressive or flat tax rates per ruleset and category. A "Default Ruleset" selector sets the profile's default fiscal rule (locale-inferred or explicit). Backend `profiles` model gains `default_fiscal_rule` column; `tax_rates` table seeded with Spain progressive and Japan flat defaults. 30+ new EN/ES i18n keys.
- **Extended taxable P&L on Tax page**: fiscal year rows are now expandable, showing per-line-item detail (quantity, proceeds, cost basis, P&L, tax owed) with confirmed-vs-computed source badges. Tax owed is broken down per category (e.g. capital_gains, dividends).
- **Fiscal rules in Settings**: a new "Fiscal Rules" section lets the user assign a rule (`Spain` / `Japan` / `Default` / `Legacy` / `No rule`) to a date range. Periods can be added, edited, and removed; the backend resolves each sell's rule from the period covering its sell date and freezes it onto the transaction. New EN/ES keys under `fiscalRules.*`.
- **Rate-fallback warning on the Performance page**: when the backend reports `rate_fallbacks`, the page shows a warning callout (matching the portfolio-assets stale-data banner) telling the user the closest available rate was used. New EN/ES keys `performance.rateFallbackTitle` / `performance.rateFallbackMsg`.
- **Performance page currency selector**: a currency dropdown sits at the top of `/performance` (same pattern as the dashboard and cash-flow pages). The summary cards now render values with the selected currency symbol and the selector drives a `display_currency` request to the backend, so all card amounts are converted and explicitly labeled.

### Fixed

- **Accessibility audit — icon buttons and form labels**: added `aria-label` attributes to all icon-only buttons across modals and pages (Add/Edit Transaction modals, Detail Transaction modal, Balance Snapshots, Income schedule actions, ReplayButton). Added `for`/`id` label-control associations on the Transfer form fields.
- **Detail modal label semantics**: replaced `<label>` elements with `<span class="detail-label">` in read-only key-value detail fields to eliminate false-positive a11y warnings.
- **Scoped CSS selectors**: used `:global()` where Svelte component scoping prevented CSS from matching child elements (Detail Transaction modal action buttons, Transactions filter controls).
- **Dead CSS cleanup**: removed unused `.page-actions`, `.card-default`, `.num.total`, and `.detail-table th.num` selectors across dividends, entities, schedules, settings, transfers, and Card components.
- **Cross-browser input styling**: added `appearance: textfield` alongside `-moz-appearance` in `NumberInput` for consistent spin-button removal.
- **Profile store test alignment**: updated assertions to include `default_fiscal_rule` matching the new profile model shape.
- **jsconfig.json type resolution**: suppressed `Cannot find type definition file for 'node'` warning by overriding SvelteKit's auto-generated `types` config.

## [0.11.0] — 2026-08-14

### Fixed

- **Transactions table Category column shows the right value per type**: `INCOME` rows now display their `income_category` (`salary`/`other`/`dividends`/`interest`) instead of an empty cell, investment rows display `investment_transaction_category` (`NORMAL`/`DCA`/`REBALANCE`), and everything else shows `-`. The `dividend_type` sub-classification is not shown in this column.
- **Detail modal income-category gap**: the transaction detail view now shows `income_category` in General Information for all `INCOME` types (previously only dividend rows revealed it).

### Added

- **Dividends page parity**: the transactions table on `/dividends` gained a `dividend_type` column (`-` when unset) plus per-row Edit and Delete buttons wired to the existing `EditTransactionModal` and `ConfirmDeleteModal` (delete calls `crud.transactions.remove` and reloads). No row-click detail view.
- Tutorial mock data updated to the renamed `investment_transaction_category` field.

## [0.10.0] — 2026-08-14

### Added

- **Update availability badge**: the app now checks for newer backend/frontend releases and shows a dismissible warning badge (linking to the GitHub release) beneath the header ribbon. `stores/updates.svelte.ts` polls `GET /api/v1/updates?frontend_version=<baked>` once on load and hourly; the frontend's own version is baked from `package.json` at build time (`__APP_VERSION__` in `vite.config.js`). `UpdateBadge.svelte` renders a per-side badge; fail-open — no badge when nothing is outdated, disabled, or unknown. 3 EN + 3 ES i18n keys. 11 new tests.

## [0.9.0] — 2026-08-13

### Changed

- **Income chart classified by category**: the "Income by Source" chart on the Income page is now "Income by Type". Bars are stacked and colored by income category — Salary, Other income, Dividends, Interest — each category with a solid Realized and pastel Projected dataset pair and a fixed hue. The Income Sources table gained a Category column with color-coded badges. Categories come from the new `income_category` field; rows without one fall back to a type/entity derivation server-side. Tutorial mock data now carries the `type` dimension and a salary (EMPLOYER) entity. 4 new i18n keys per locale (EN + ES).
- **Category picker in modals**: the Add Income modal gained a required Category dropdown (`salary`, `other`, `dividends`, `interest`); the Add/Edit Schedule modals show an optional Category dropdown when the transaction type is Income. Selections are sent as `income_category` to the API. The Add/Edit Transaction modals collapse the income types (`MONEY_IN`, `DIVIDEND`, `INTEREST`) into a single Income type whose Category selection reveals the dividend field group when set to dividends.

## [0.8.2] — 2026-08-12

### Added

- **Invested amount & value in price-history chart**: when a market-tracked asset is selected, the price-history widget now shows three series: price (left Y axis), cumulative invested amount, and current investment value (right Y axis). No transactions → those series are absent; buys/sells alter the running figures over time. 2 new i18n keys added per locale.

### Changed

- **Incremental, paced price sync**: the "Sync Prices" button now calls `POST /market/sync-prices?full=false&pace=2&max_age_hours=1`, skipping symbols refreshed within the last hour. Opening the Portfolio Assets or Market Assets page also fires a background auto-sync (fire-and-forget): the page paints immediately, the button is disabled while a sync runs, and on completion it re-enables and refreshes the content. Sync failures are silent (the table is never replaced by an error).

## [0.8.1] — 2026-08-12

### Added

- **Sortable Portfolio Assets table**: click any column header to sort the table; the active column shows an asc/desc arrow. Text columns sort ascending first; numeric columns (P&L %, Desired %, Current Value) sort descending first. Nulls always sort last. 3 new component tests.
- **Localized asset type**: the Type column now renders through i18n instead of the raw English enum — e.g. `Acción`/`Fondo indexado` in ES, `Stock`/`Index Fund` in EN. 8 new `assetType.*` keys per locale.

### Changed

- **Table density**: horizontal cell padding reduced (16px → 12px) and the freed space given to the asset name column, which widened from 160px to 360px (min 180px) with ellipsis.
- **P&L % heat styling**: the P&L % cell now uses a 7-bucket heat scale (deep red → red → orange → muted → light green → green → deep green) with a ▲/▼ gain/loss arrow (only beyond ±1%). Thresholds: ≤-20 / -5 / -1 / +1 / +5 / +20. 2 new component tests; suite now 100.
- **Cleaner chart tooltips**: the StackedAreaChart tooltip (Holdings Value Over Time, currencies) now hides entries with no value (0/null) at the hovered point, so the tooltip is shorter and easier to read.

## [0.8.0] — 2026-08-12

### Added

- **Manual valuation history (UC-45)**: Manual-tracked assets on Portfolio Assets now show a **Valuations** list in the asset detail area instead of a price chart. Each row shows effective date, value, and notes with edit/delete actions, plus an "Add Valuation" button. Editing an existing valuation on the same date replaces it (UPSERT); changing the date moves the snapshot. The Add/Edit asset modals now include an "Effective Date" picker for manual assets (default today), and the edit modal seeds the manual value from the latest ledger snapshot instead of the legacy column. New component `ManualValueModal.svelte`; `manual-values` API methods added to `analytics.js`. EN/ES i18n keys added. 3 new component tests.

## [0.7.1] — 2026-08-12

### Fixed

- **Layer badges on Portfolio Assets**: Core, Reserve, and Satellite now all render as badges with their own colors. Satellite and Reserve previously appeared as plain colored text because `--color-warning-light`, `--color-info-light`, `--color-success-light`, and `--color-danger-light` were referenced but never defined — only `--color-primary-light` existed. The missing semantic `-light` variables were added to `app.css` (also fixing the status and error badge backgrounds). Layer values are now case-normalized for badge lookup and display.

## [0.7.0] — 2026-08-11

### Added

- **Market API outage UX**: Global health badges appear between the header and page content when authenticated. A freshness badge always shows "Market data from {date}" (timezone-aware) or "No market data yet". When the Market API is down, a dismissible "Market API not available" badge appears. Driven by a new Svelte 5 runes store (`$lib/stores/health.svelte.ts`) that polls `/health` every 60s with debounced failure detection (2 consecutive fails).
- **Sync open-circuit warnings**: Portfolio Assets and Currencies pages now detect when the circuit breaker is open (`circuit_open: true` in the sync response) and render a warning callout — "Market data is temporarily unavailable. Nothing was synced — using cached data." — instead of silently pretending the sync succeeded.
- **i18n**: 6 new keys added to EN + ES locales: `portfolioAssets.syncUnavailable`, `currencies.syncUnavailable`, `health.marketDataTitle`, `health.marketDataNone`, `health.marketApiUnavailable`, `health.dismiss`.
- **Stale-price callout on Portfolio Assets**: when holdings are valued from their last known purchase price (`transaction-fallback`), the page shows a warning callout — *"Prices from {date} — market data unavailable"* with the oldest fallback date — and *"No price data"* when a holding has no market price at all. Mirrors the income/cash-flow rate-warning pattern. EN/ES i18n keys added; implemented with Svelte 5 runes (`$derived` only).
- **Component tests**: 5 tests in `src/lib/tests/portfolio-assets.test.js` covering stale, oldest-date, no-price, no-callout, and inactive-asset cases. 2 additional client tests for the profile guard. Suite now 87 tests.

### Fixed

- **API client profile guard**: Requests to profile-scoped endpoints are now blocked client-side when no active profile is set, preventing HTTP 401 errors on `/analytics/projected-income` and other analytics calls that may fire during edge-case timings.
- **E2E auth flakiness**: Reverted `beforeAll` to `beforeEach` (same browser context shares `sessionStorage`). Auth runs once per suite — first test authenticates, subsequent tests skip via `isVisible('.app-shell')` guard. Dashboard test no longer reloads the page (already at `/` after auth). Replaced `waitFor('.app-shell')` + `networkidle` with `expect(h1).toContainText()` auto-retry, removing health-polling timeout bottlenecks.

## [0.6.1] — 2026-08-07

### Fixed

- **Button debouncing**: Date preset buttons now disabled during data loading on all 5 pages with charts (Dashboard, Currencies, Portfolio Assets, Cash Flow, Income). Balance snapshot modal cancel buttons disabled during submission. Transfer form date input disabled while creating.

## [0.6.0] — 2026-08-07

### Added

- **Timezone preference**: Selector in Settings page with common IANA timezones. On first visit, auto-detects browser timezone via `Intl.DateTimeFormat` and suggests it. Timestamps are converted from UTC to the selected timezone for display. Defaults to UTC.
- **Shared date utility**: `$lib/preferences/timezone.svelte.ts` with `formatTimestamp()` for consistent timezone-aware rendering everywhere. 9 unit tests covering null, unparseable, date-only, time-only, seconds, and timezone conversion.

## [0.5.0] — 2026-08-07

### Added

- **Frontend tests**: Vitest + Testing Library. 23 component tests across MetricCard, InfoTip, and Button. `bun run test` / `make test-frontend`.
- **E2E tests**: Playwright smoke tests verify all 14 pages load. `bun run test:e2e` / `make test-e2e`.
- **Vite proxy**: Made configurable via `VITE_API_TARGET` env var. Defaults to `backend:8000` (Docker), E2E uses `localhost:8000`.

### Changed

- **Dev tooling**: `make test-frontend` / `make lint-frontend` targets. `scripts/changelog-check.py` validates changelog headers. Pre-commit `commit-msg` hook enforces conventional commits. CI creates git tags + GitHub Releases on version bumps.

## [0.4.0] — 2026-08-04

### Added

- **Performance page — redesigned cards**: Split into two rows with 7 cards total. Row 1: Portfolio Value, Total Invested Now, Unrealized P&L %, Unrealized P&L. Row 2: Total Invested Historic, Total Return, Realized P&L. New fields `unrealized_pl_pct` (unrealized % relative to current cost basis) and `total_invested_now`/`total_invested_historic` (current FIFO cost basis vs. all-time invested). Total Return percentage now uses all-time invested as denominator — no longer skewed by sold positions.

- **Tutorial system — 14 pages**: Step-by-step tutorials using `driver.js` with mock data, i18n keys (EN + ES), and cross-page navigation chains. Full chain: Dashboard → Entities → Currencies → Market Assets → Portfolio Assets → Transactions → Transfer → Income → Schedules → Dividends → Performance → Cash Flow → Balance Snapshots → Fiscal Exemptions. Settings page excluded from tutorial.
- **Tutorial polish**: Settings toggle to disable all tutorials (persisted to localStorage). Skip confirmation dialog prevents accidental closes from the driver.js popover. Unexpected navigation shows a pause toast without marking the page as seen.
- **Tutorial mock intercept fix**: Switched from dynamic imports to static imports for the API intercept module. Dynamic imports created separate chunks where the `api` singleton wasn't shared, silently skipping mock data injection.
- **ReplayButton redesign**: Icon-only button (`#89CFF0` baby blue) at 32×32px, placed left of page titles via `.page-title-row` on all pages. Central color variable `--color-baby-blue` in `app.css`.
- **Startup log**: Vite plugin prints `SvelteKit dev server running on http://localhost:5173` on dev server start, matching backend's Uvicorn log pattern.
- **Browser language detection**: On first visit (before any setting is saved), the UI auto-detects the user's browser language (`navigator.language`). Spanish-speaking browsers get `es-ES`, all others default to `en-US`.
- **Manual asset valuations**: Manual-tracked assets now record historical values via backend `manual_values` table. Timestamped audit trail, appears in portfolio charts and holdings.
- **Metric explanations — Dashboard, Performance, Income, Cash Flow & Currencies pages**: Each metric card now shows a small question-mark icon next to its title with a hover/focus tooltip explaining how the value is calculated. Reusable `InfoTip` component; texts localized (EN + ES).

### Changed

- **Transfer types**: Transactions now display `TRANSFER_IN`/`TRANSFER_OUT` with localized labels and neutral badges (Transactions page filter group, Transaction detail modal, Schedules type labels). Editing a transfer leg locks its type (managed via the Transfers flow). Tutorial mocks updated: the sample transfer is now `TRANSFER_OUT` and the sample schedule uses `TRANSFER_OUT` instead of the reserved `TRANSFER`. Cash Flow chart/detail table already treat transfer legs as neutral.
- **EditScheduleModal**: Full rewrite — now supports all transaction types (Investment Buy/Sell, Dividends, etc.) with conditional portfolio asset selector, full periodicity options, and `portfolio_asset_id` field, matching AddScheduleModal capabilities.
- **MetricCard fix**: Negative change text now renders red — was using undefined `--color-error` variable, corrected to `--color-danger`.
- **Income page**: INVESTMENT_BUY transactions no longer appear in the recent income list — only actual income types (INCOME) are shown.
- **Console logging demoted to debug**: Mock and tutorial diagnostic logs (in `client.js`, `TutorialStore`, `TutorialOverlay`) are now routed through a leveled `logger.js` module and demoted to `debug` level. Default level is `info` — debug messages are suppressed. Set `window.__FINHUB_LOG_LEVEL = 'debug'` in the browser console to re-enable them.

### Fixed

- **Edit transaction — fees/taxes now persist**: The edit modal previously reset fees and taxes to empty, never loading existing data or sending it back. It now fetches the full transaction (`GET /{id}/full`), displays existing fee/tax rows, and sends them via the new `PUT /{id}/full` endpoint.

- **InfoTip overflow**: Tooltips near the right viewport edge now flip to `right: 0` alignment, preventing them from being clipped off-screen. Switched from pure-CSS `:hover` visibility to JS-driven positioning with `getBoundingClientRect()` overflow detection.
- **Performance — Total Return card NaN**: The card passed a pre-formatted string (e.g. `"-1.02%"`) into `MetricCard`, whose `fmt()` coerced it with `Math.abs()` → `NaN`. `MetricCard` now renders pre-formatted strings verbatim instead of re-formatting them.
- **Tutorial mock data on all 14 pages**: Tutorial `start()` moved from `onMount` to module scope so mocks register before page data loading, and each page now re-fetches via a `$effect` when the tutorial becomes active. Fixes Replay path where the mock store was enabled after data had already been fetched with the real (empty) API, leaving pages permanently empty.
- **Tutorial mock shapes aligned to backend API contracts**: Rewrote mocks that returned objects in place of arrays or used page-mismatched field names. Dividends now return a `DividendLine`-shaped array (was `{by_asset}` — caused a `reduce is not a function` crash); schedules use `description`/`periodicity_type`/`total_value`/`start_date`/`end_date`; income uses dynamic month periods plus `income-by-source`/`projected-income` `.data` arrays and `rate_info.rates`; currencies return `{latest_raw, series, dates}` and `{labels, datasets}` objects; portfolio-assets/market-assets use `asset_type`/`currency_code` fields and `/prices/value-chart` returns `{data: {market_code: [{date, value, estimated}]}}`; dashboard/entities holdings-by-entity renamed `currency_code` → `currency`.
- **Mock routing in `client.js`**: Mock lookup strips query strings (so `/analytics/dividends?…` hits the `/analytics/dividends` mock), passes the full path to function mocks (restores `dimension=entity`/`asset_class` branching in the dashboard allocation mock), and adds a prefix fallback so dynamic endpoints like `/prices/chart/{market_code}` reach their handlers.
- **TutorialStore**: Added `isActiveFor(page)` helper backing the re-fetch-on-activation effect.
- **Dashboard / Portfolio Assets — data recovery after tutorial cancel/skip**: TutorialOverlay `onfinish` now re-runs the full page load chain. Dashboard reloads both `loadAll()` and `loadHistorical()` (previously only `loadAll()`, leaving the Historical Portfolio Value chart on stale mock data); Portfolio Assets reloads prices too.

## [0.3.0] — 2026-07-29

### Added

- **StackedAreaChart estimated segments**: Backend carries forward earliest price for dates before first price record. Chart renders estimated periods as dotted/dashed lines. Tooltips reflect `value` field correctly.
- **Dashboard — Portfolio Change card**: Shows total portfolio delta over selected chart period, reactive to time presets.
- **Portfolio Assets — Current Value column**: Replaces TER, shows latest market value with unified currency and 2 decimals.
- **Portfolio Assets — Currency selector**: Converts all asset values to a unified display currency.
- **Portfolio Assets — Holdings chart loading indicator**: CSS spinner on date presets while data loads.
- **Portfolio Assets — Stock split banner & modal**: Notification banner above chart when flagged splits are detected. Confirm modal shows buy date, prices, and inferred ratio. POST on confirm registers the split.
- **Transaction filter bar**: Single-row horizontal layout with separator borders.
- **Pre-commit hooks**: Added `validate-i18n`, `svelte check`, and `pytest`. Switched from Docker to local `uv run` / `bun x`.

### Changed

- **Dashboard**: Investment Return split into Unrealized P&L + Realized P&L cards. MetricCard passes signed values (no `Math.abs`), sign before currency symbol. All values 2 decimals.
- **MetricCard**: Defaults to `null` (not 0), formats with abbreviation (k/M), JPY 0 decimals, tooltip matches card formatting.
- **Portfolio Assets**: P&L % column with 2 decimal rounding. Carry-forward price estimates on the holdings chart.
- **Income**: 3M/1Y time presets centered on current month.
- **Sidebar**: All labels via i18n. Settings entry with gear icon.
- **Changelogs**: Average-cost terminology corrected throughout.

## [0.2.0] — 2026-06-14

### Added

- **i18n / Localization**: Vanilla Svelte 5 rune-based i18n module. 400+ translation keys in `en-US` and `es-ES`. New Settings page with language selector. All pages, modals, sidebar, header, and pagination fully localized.
- **Default Currency setting**: Shared currency preference module (`$lib/preferences/currency.svelte.ts`) with `localStorage` persistence. Currency selector added to Settings page. All pages now use the shared store instead of duplicated `displayCurrency`/`CURRENCY_SYMBOLS` boilerplate.
- **Settings page** (`/settings`): Language (English / Español) and default currency preferences.
- **Dashboard — Unrealized & Realized P&L cards**: Total Return split into Unrealized P&L (open positions) and Realized P&L (closed, average-cost), both relative to total invested.
- **Dashboard — Portfolio Change card**: Shows total portfolio change from the start of the selected time period, reactive to chart presets.
- **Dashboard — Metric cards**: Font reduced and grid tightened so 6 cards fit in one row.
- **MetricCard — Smart number formatting**: Values ≥10M abbreviated as `X.XXM`, ≥10K as `X.Xk`. JPY uses 0 decimals. Hover tooltip shows full unrounded number.
- **Portfolio Assets — Performance columns**: Distribution and TER columns replaced with P&L % (unrealized) and Current Value (with currency conversion).
- **Portfolio Assets — Currency selector**: Dropdown to convert all asset values to a unified display currency, same as the dashboard.
- **Validation script**: `bun run validate-i18n` scans all `.svelte` files for `t()` calls and verifies keys exist in both dictionaries.
- **CHANGELOG.md**: Both frontend and backend now have changelogs.

### Changed

- **Dashboard**: "Total Return" card split into Unrealized P&L and Realized P&L. All values rounded to 2 decimals.
- **MetricCard**: Now accepts raw numbers and formats internally (abbreviation, JPY truncation, tooltip). All 5 pages using MetricCard updated to pass raw values.
- **Transactions**: Filter bar now single horizontal row (time presets | type | entity | currency) instead of stacked columns. Separator borders between filter groups.
- **Sidebar**: All labels moved to i18n. Settings entry added at bottom with gear icon.
- **GroupedTable**: Column headers (Entity, Asset Class, Original Amount, Unified Amount) now localized.
- **Pagination**: Replaced hardcoded Spanish text with i18n calls.
- **Portfolio Assets**: Currency symbol inline ternary replaced with shared `getSymbolFor()`. Added currency selector. Distribution/TER columns replaced with P&L % and Current Value.
- **Income page**: 3M and 1Y time presets now centered around current month ([-1, +2] and [-6, +6]), matching the symmetry of the 6M preset.
- **Portfolio Assets — Holdings chart loading indicator**: CSS spinner appears next to date presets while chart data loads (especially useful for custom ranges and "All").
- **Portfolio Assets — Holdings chart data fix**: Chart now includes historically held assets even if later deactivated/sold. Backend auto-detects and adjusts for stock splits so pre-split holding values show correctly.
- **README.md**: Removed completed roadmap, updated features and defaults.

## [0.1.0] — 2026-06-01

### Framework

- Svelte 5 SPA with SvelteKit and static adapter
- Vite 6 build tooling
- Chart.js 4 for all visualizations
- Responsive sidebar + header layout with mobile hamburger menu

### Pages

| Page | Features |
|---|---|
| **Dashboard** | Portfolio value, cash balance, invested, total return metrics. Historical value chart with investment value overlay, date presets (3M/6M/1Y/All/Custom). Asset allocation doughnut/pie charts with segment labels. Asset Class × Entity grouped table. Currency selector. |
| **Transactions** | Full transaction list with type/entity/currency/date filters and pagination. Asset name column. Detail modal with all fields. Inline edit and delete. |
| **Transfer** | Two-entity transfer form with amount, currency, date, and notes. |
| **Income** | Monthly realized/projected metrics. Income by source stacked bar chart. Income sources table with schedule management. Recent income transactions list. Currency selector. |
| **Portfolio Assets** | Holdings value over time stacked area chart with date presets. Asset table with layer/status filter, search. Per-asset price history chart. One-click price sync button. |
| **Dividends** | Total dividends, assets with dividends, payments count metrics. Distribution doughnut chart. Per-asset and per-transaction tables. |
| **Performance** | Portfolio value, invested, return, unrealized/realized P&L metrics. Realized gains average-cost table. |
| **Cash Flow** | Inflows/outflows/net metrics. Cash flow by period stacked bar chart with date presets. Detail table. Currency selector. |
| **Entities** | Entity CRUD with type/country/liquidity. Historical value chart per entity. Dependency-aware delete. |
| **Market Assets** | Market asset CRUD with type filter and search. Stock, ETF, ETC, fund, index fund, crypto support. |
| **Currencies** | Holdings by currency and exchange rate charts with date presets. Rate history view. Currency and base selector. One-click FX rate sync. |
| **Schedules** | Schedule CRUD with type and periodicity filters. Active/ended status display. |
| **Balance Snapshots** | Balance snapshot CRUD with entity filter and pagination. |
| **Fiscal Exemptions** | Exemption CRUD with type, rate, and rate limit fields. |
| **Settings** | Language selector (English / Español). Default currency preference. Both persisted to localStorage. |

### Charts

- **LineChart** — time series with multiple datasets
- **DoughnutChart / PieChart** — allocation breakdown with segment labels plugin (abbreviated values + percentages)
- **StackedAreaChart** — cumulative area with multiple layers
- **StackedBarChart** — period-based bar comparison
- Y-axis forced to 0 on all charts

### Shared Components

- **Sidebar** — sectioned navigation with SVG icons, mobile slide-out, active state highlighting
- **Header** — app title, mobile menu toggle
- **Modal** — reusable modal shell with backdrop
- **DataTable** — sortable columns, responsive scroll
- **MetricCard** — labeled value with optional currency symbol and change indicator
- **ChartCard** — titled container for charts
- **Select** — styled dropdown with placeholder
- **TextInput** — styled input with paste handler for date inputs (DD/MM/YYYY, ISO, compact)
- **Button** — primary, outline, and danger variants
- **LoadingSpinner, EmptyState** — loading and empty state components
- **Pagination** — page navigation with first/prev/select/next/last
- **CrossTabTable, GroupedTable** — tabular data display components

### Modals (19)

- Full CRUD modals for: Transactions, Entities, Market Assets, Portfolio Assets, Schedules, Balance Snapshots, Fiscal Exemptions, Income, Assets, Currencies
- ConfirmDeleteModal — reusable delete confirmation with soft-delete awareness

### i18n / Localization

- Vanilla Svelte 5 rune-based i18n module (zero dependencies)
- 400+ translation keys in both `en-US` and `es-ES`
- `localStorage` persistence for language and currency preferences
- Validation script (`bun run validate-i18n`) to detect missing keys
- All pages, modals, sidebar, header, pagination fully localized

### Development

- Validation script: `bun run validate-i18n` — scans all `.svelte` files for `t()` calls and checks both dictionaries
