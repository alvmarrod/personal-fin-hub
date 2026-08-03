# Changelog

All notable changes to the frontend service.

## [0.4.0] — In development

### Added

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
- **Income page**: INVESTMENT_BUY transactions no longer appear in the recent income list — only actual income types (MONEY_IN, INTEREST, DIVIDEND) are shown.
- **Console logging demoted to debug**: Mock and tutorial diagnostic logs (in `client.js`, `TutorialStore`, `TutorialOverlay`) are now routed through a leveled `logger.js` module and demoted to `debug` level. Default level is `info` — debug messages are suppressed. Set `window.__FINHUB_LOG_LEVEL = 'debug'` in the browser console to re-enable them.

### Fixed

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

## [0.2.0] — i18n & localization

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

## [0.1.0] — Initial release

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
