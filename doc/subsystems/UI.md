# Subsystem: UI (Frontend)

## Technology Stack

| Layer | Choice |
|-------|--------|
| Framework | SvelteKit (adapter-static, SPA mode) |
| Language | JavaScript (JS, no TypeScript) |
| Bundler | Vite (via SvelteKit) |
| Charts | Chart.js |
| CSS | Pure CSS with custom properties (no framework) |
| Package Manager | bun (via Docker) |

## Project Structure

```text
frontend/src/
├── routes/
│   ├── +layout.svelte          # Main layout (sidebar + header)
│   ├── +page.svelte            # Dashboard (root route)
│   ├── entities/               # Entities CRUD
│   ├── market-assets/          # Market assets CRUD
│   ├── portfolio-assets/       # Portfolio assets CRUD
│   ├── transactions/           # Transactions list + create/edit
│   ├── transfers/              # Entity transfers
│   ├── cash-flow/              # Cash flow analysis
│   ├── dividends/              # Dividend income
│   ├── income/                 # Income summary & sources
│   ├── performance/            # Performance summary
│   ├── tax/                    # Taxable P&L per fiscal year
│   ├── schedules/              # Recurring operations
│   ├── currencies/             # Currency management
│   ├── balance-snapshots/      # Balances (cash + snapshot anchors)
│   └── fiscal-exemptions/      # Fiscal exemptions
├── lib/
│   ├── api/
│   │   ├── client.js           # Base HTTP client
│   │   ├── crud.js             # Generic CRUD functions
│   │   └── analytics.js        # Analytics endpoint functions
│   ├── components/             # Reusable UI components ("ladrillos")
│   │   ├── Button.svelte
│   │   ├── Card.svelte
│   │   ├── Modal.svelte
│   │   ├── DataTable.svelte
│   │   ├── FormField.svelte
│   │   ├── Select.svelte
│   │   ├── TextInput.svelte
│   │   ├── NumberInput.svelte
│   │   ├── DateInput.svelte
│   │   ├── Badge.svelte
│   │   ├── LoadingSpinner.svelte
│   │   ├── EmptyState.svelte
│   │   ├── MetricCard.svelte
│   │   ├── PageHeader.svelte      # shared page title + actions
│   │   ├── ChartCard.svelte
│   │   └── charts/
│   │       ├── LineChart.svelte
│   │       ├── StackedBarChart.svelte
│   │       ├── StackedAreaChart.svelte
│   │       └── ArcChart.svelte
│   ├── i18n/
│   │   ├── index.svelte.ts       # t(), locale(), setLocale()
│   │   └── locales/
│   │       ├── en.ts
│   │       └── es.ts
│   ├── preferences/
│   │   └── currency.svelte.ts    # display currency store + symbols
│   ├── utils/
│   │   ├── format.svelte.ts      # formatDate / formatAmount
│   │   └── tableSort.svelte.js
│   └── stores/
│       └── ui.js                 # UI state (sidebar, modals, etc.)
├── app.html                    # SvelteKit HTML shell
└── app.css                     # Global styles + CSS variables
```text

## Design System

### Color Palette

```css
:root {
  /* Surfaces */
  --color-bg: #f8f9fa;
  --color-surface: #ffffff;
  --color-surface-hover: #f1f3f5;
  --color-border: #dee2e6;

  /* Text */
  --color-text-primary: #212529;
  --color-text-secondary: #6c757d;
  --color-text-muted: #adb5bd;

  /* Brand / Accent */
  --color-primary: #4263eb;
  --color-primary-hover: #3b5bdb;
  --color-primary-light: #dbe4ff;

  /* Semantic */
  --color-success: #2f9e44;
  --color-warning: #f08c00;
  --color-danger: #e03131;
  --color-info: #1971c2;

  /* Charts */
  --chart-colors: #4263eb #2f9e44 #f08c00 #e03131 #845ef7 #20c997 #ff6b6b #339af0 #94d82d #f06595;
}
```text

### Typography

```css
--font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
--font-mono: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
--font-size-xs: 0.75rem;
--font-size-sm: 0.875rem;
--font-size-base: 1rem;
--font-size-lg: 1.25rem;
--font-size-xl: 1.5rem;
--font-size-2xl: 2rem;
```text

### Spacing Scale

```css
--space-1: 0.25rem;
--space-2: 0.5rem;
--space-3: 0.75rem;
--space-4: 1rem;
--space-5: 1.25rem;
--space-6: 1.5rem;
--space-8: 2rem;
--space-10: 2.5rem;
--space-12: 3rem;
```text

### Border Radius

```css
--radius-sm: 4px;
--radius-md: 8px;
--radius-lg: 12px;
--radius-full: 9999px;
```text

### Shadows

```css
--shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
--shadow-md: 0 4px 6px rgba(0,0,0,0.07);
--shadow-lg: 0 10px 15px rgba(0,0,0,0.1);
```text

## Localization & Number Formatting

Shared across all views. Localization state and formatting helpers live under
`frontend/src/lib/` (`i18n/` and `utils/`) and are imported by every page.

### Localization

- Source of truth: `$lib/i18n/index.svelte.ts`. Three dictionaries: `en-US`,
  `es-ES` and `ja-JP` (`locales/en.ts`, `es.ts`, `ja.ts`).
- API: `t(key, params)` translates; `locale()` returns the active locale;
  `setLocale(code)` persists it to `localStorage`. On first visit the locale is
  detected from the browser language (`es*` → `es-ES`, `ja*` → `ja-JP`, else
  `en-US`). A key missing from the active dictionary falls back to English.
- The root layout keeps `<html lang>` in sync with the active locale.
- Key parity across all dictionaries is enforced by `bun run validate-i18n`
  (CI gate). Every new key must be added to every locale file.

### Number Formatting

Amounts are rendered through `formatAmount(value)` (`$lib/utils/format.svelte.ts`).
Storage never changes: the backend returns full precision and the format is
display-only.

- The separators come from the user's **Number format** setting
  (`$lib/preferences/numberFormat.svelte.ts`), not from the language locale:
  - `1,234.56` — comma thousands, dot decimals (`comma-dot`)
  - `1.234,56` — dot thousands, comma decimals (`dot-comma`, default)
- Grouping is always shown, for every magnitude (`8.340`, not `8340`).
- No trailing zeros: `minimumFractionDigits: 0`, so integers render without a
  decimal part.
- Two decimals is the maximum for every currency and magnitude (`0.523` renders
  `0,52`; `12345.678` renders `12.345,68`). There is no JPY special case.
- The same rules apply to chart axes/tooltips, metric cards and every table cell
  that renders a currency amount. Symbols are still composed by each view.
- FX rates use the same separators with their existing 2-or-4 decimals
  (`formatRate`).

Percentages use `formatPercent(value)` and deliberately **ignore** the number
format setting: the decimal point is always `.` and thousands take an ISO
space (`1 234.5%`). Precision follows the magnitude, classified on the value
rounded to two decimals:

- under `1` → two fixed decimals (`0.40%`, `0.00%`)
- `1` to `10` → one fixed decimal (`5.0%`, `9.9%`)
- `10` and above → up to two, trailing zeros trimmed (`12%`, `13.15%`)

`{ sign: true }` prefixes a `+` for positive deltas. This applies to tables,
metric cards, chart tooltips/segments and the market-cycle formulas.

Dates use the same locale discipline via `formatDate` / `formatDateTime` in the
same module. Their order comes from the user's date-format setting (Settings),
not from the language. Values from the API are UTC instants without an offset;
`formatDate` parses them as UTC (`parseUtc`) and renders them in the profile
timezone, so the browser's own zone never leaks into the result.

### Date & Time Inputs

- Clock pickers (`datetime-local`: add/edit balance snapshot, transfer) show the
  **profile-timezone wall clock** and label the field with the zone and its
  current offset, e.g. `Time in Europe/Madrid · GMT+1`. The offset follows the
  selected date, so a summer date shows `GMT+2`.
- On submit the wall clock is converted back to a UTC instant
  (`fromZonedInput`), matching the API contract.
- Date-only inputs (transaction date, schedule dates, fiscal periods, manual
  value date, settlement/record/payment dates) are timezone-free calendar dates;
  they are not labelled with a zone.

## Component Conventions (Svelte 5)

### Runes API

All components use Svelte 5 runes (`$state`, `$derived`, `$effect`, `$props`) instead of the legacy `export let` / `$:` syntax.

### Props Pattern

```svelte
<script>
  let { label, value, onAction } = $props();
</script>
```text

### Component Slots

Use Svelte 5 `{@render children()}` pattern for content projection where possible. Fall back to slots for multiple named content areas.

### Event Handling

Use callback props (`onXxx`) instead of `createEventDispatcher`. Parent passes `onclick`, `onsubmit`, etc.

```svelte
<!-- Button.svelte -->
<script>
  let { label, onclick, variant = 'primary', disabled = false } = $props();
</script>
<button {onclick} {disabled} class="btn btn-{variant}">{label}</button>
```text

### CSS Scoping

Styles are scoped per component. Global styles go in `app.css`. Theme-dependent values use CSS custom properties.

### Sortable Table Pattern

Used by the Portfolio Assets and Performance pages for client-side column sorting:

- Column config array `{ key, labelKey, align, accessor? }`; `accessor` derives the sort value when the displayed text is composed (e.g. Asset = `ticker || market_code`).
- `<th class="sortable-th" class:num class:sort-active onclick>` with a `.sort-indicator` span rendering ▲/▼ for the active column only.
- Numeric columns (declared in a `NUMERIC_SORT_KEYS` set) sort **descending** on first click; other columns ascending. Clicking the active column toggles direction.
- Null-safe comparator: numbers compare by subtraction, strings via `localeCompare(..., { numeric: true })`, nulls always last.
- Each page owns its config/logic inline (no shared component yet); tests mirror `portfolio-assets.test.js` → sorting describe blocks.

### MetricCard Direction Variant

`MetricCard` accepts a `valueVariant` prop (`positive`/`negative`) that renders a ▲/▼ arrow before the value, colored green/red. Used on pages without a period-comparison subtitle (Performance) to show direction directly on the card value.

### MetricCard Compact Variant

`MetricCard` accepts a `compact` prop that renders a smaller card (reduced padding, smaller label/value typography, no shadow). Used on dense dashboards; currently only the Performance page.

### MetricGroup Sectioning

`MetricGroup` wraps a grid of metric cards in a transparent section with a solid colored **limit line** border and a small tab label sitting on the top border, giving related cards visual grouping. Props: `label`, `tone` — `market` (blue), `unrealized` (light blue), `realized` (green), `income` (purple), `total` (amber). Currently used by the Performance page (see `views/performance.md`).

### Income Category Badges

Income categories (`salary`, `other`, `dividends`, `interest`, `cashback`) render as localized badges; each category has its own label key and badge hue (`cashback` added alongside the Income Sources grouping).

### Layout Component

```svelte
+layout.svelte
├── Header ribbon (navigation + actions)
├── Sidebar (collapsible on mobile)
└── <slot/> (page content)
```text

## Navigation Architecture

### Routes

| Route | Page | Status |
|-------|------|--------|
| `/` | Dashboard | Phase 2 |
| `/entities` | Entities | Phase 3 |
| `/market-assets` | Market Assets | Phase 4 |
| `/portfolio-assets` | Portfolio Assets | Phase 5 |
| `/transactions` | Transactions List | Phase 6 |
| `/transactions/new` | New Transaction | Phase 6 |
| `/transactions/[id]` | Transaction Detail | Phase 6 |
| `/transfers/new` | New Transfer (currency only) | Phase 6 |
| `/cash-flow` | Cash Flow | Phase 7 |
| `/dividends` | Dividends | Phase 7 |
| `/income` | Income summary & sources | Income |
| `/performance` | Performance | Phase 7 |
| `/strategy` | Investment strategy (timeline, current drift) | Strategy |
| `/debt` | Debt (payable and receivable) | Debt |
| `/investment-market-cycle` | Investment Market Cycle | Market Cycle |
| `/tax` | Tax (taxable P&L per fiscal year) | Tax & Fiscal |
| `/schedules` | Schedules | Phase 8 |
| `/balance-snapshots` | Balances | Phase 8 |
| `/currencies` | Currencies | Phase 8 |
| `/fiscal-exemptions` | Fiscal Exemptions | Phase 8 |
| `/profiles` | Profile picker (shown when no active profile) | Profiles |
| `/backups` | Backups (list, download, create, restore) | System |
| `/settings` | Settings incl. profile management | Profiles |

### Header Ribbon

- **Left**: the brand (`Personal Fin Hub`), a light-grey `|`, and the market-data
  freshness pill (`Market data from …` or `No market data yet`). The separator and
  pill hide below 900px.
- **Right**: the privacy toggle and the profile menu.
- A market-API outage banner (`HealthBadges`) renders below the header **only**
  while the API is unavailable. A healthy API leaves no health row, so the header
  does not reserve vertical space for it.

### Sidebar

- Grouped menu (Activity / Tracking / Investments / Analysis / Setup / System) driven by the routes table above. Dashboard sits directly under the brand, without a group header. **Tracking** holds Income and Debt. **System** holds Backups and Settings.
- Each group header is a toggle. Groups start collapsed except the one that contains the current page; the choice is stored in `localStorage` (`sidebar_collapsed_v1`). Navigating into a collapsed group opens it. A collapsed header that contains the active page keeps the accent colour.
- During a tutorial, only the group that holds the current step's sidebar target opens; the other groups are forced closed so the target stays reachable without scrolling. The user's stored state returns when the tutorial ends.
- Compact sizing: width uses `clamp(180px, 12vw, 240px)` with tighter paddings/gaps in relative units; the menu is scrollable (`overflow-y: auto`) when entries exceed the viewport height.
- **Footer**: two muted lines showing `Frontend: <version>` and `Backend: <version>`. The frontend version is the build-time `__APP_VERSION__` (`src/lib/version.js`, baked from `package.json`); the backend version comes from `GET /api/v1/version` on mount, so it reflects the running backend instead of a copy. The backend line reads `—` when the call fails.

### Backups Page

`/backups` is the user-facing view of the backup service
(`doc/subsystems/backups.md`):

- **Top row** — two half-width cards, stacked below 900px. Left: the policy
  card (automatic backups enabled/disabled, `BACKUP_CRON` and `BACKUP_TIMEZONE`,
  the retention count and the next scheduler run). Right: an explanation that
  a backup is the internal SQLite 3 database of the whole installation, not a
  per-profile export.
- **List** — filename, creation time, origin badge (manual, automatic,
  startup, before/after migration, before a restore), backend version and
  size. The badge has two tones: **Manual** for `manual` and **Automatic** for
  everything else; a file without manifest metadata is shown as *Automatic*
  rather than *Unknown*. The newest file is marked. Each row offers a download (a plain link to
  `/api/v1/backups/{name}`, so the browser saves the file) and a restore.
- **Create now** — creates and prunes immediately. When the retention limit is
  reached, a modal lists the files that will be deleted and requires
  confirmation; otherwise the backup is created directly.
- **Import** — uploads a `.bak`, `.db` or `.sqlite` file. The modal inspects
  it, waits while `/backups/activity` reports background writers (Continue
  disabled, Cancel enabled, re-checked every two seconds), lists the schema
  migrations that will run (single Continue, no dismiss), and restores. The
  page clears the active profile and reloads afterwards.

The modal tells the user not to use the app in any window during a restore.
Backups are not profile-scoped: every file contains all profiles. Downloads
are full SQLite databases, not a per-profile export.

## Update Availability Badge

The app notifies the user when a newer release exists upstream. Backend and frontend are versioned and released independently, so both are checked.

- `src/lib/stores/updates.svelte.ts` (rune-based) polls `GET /api/v1/updates?frontend_version=<baked>` once on load and every hour (the backend caches GitHub for 1h). The frontend's own version is baked into the bundle at build time from `package.json` (`__APP_VERSION__`).
- `UpdateBadge.svelte` renders a dismissible warning badge per outdated side (backend / frontend), linking to the GitHub release URL. It mirrors `HealthBadges.svelte` and is rendered by `+layout.svelte` directly beneath the header ribbon (only when authenticated).
- Fail-open: no badge is shown when nothing is outdated, the check is disabled, or the result is unknown (GitHub unreachable) — never a false "update available".

## Profiles UI (Multitenancy)

The frontend gates the whole app behind an active profile. State lives in `src/lib/stores/profile.svelte.js` (rune-based), persisted to `sessionStorage`; the API client attaches the active id as `X-Profile-ID` on every request.

### Profile Picker (`/profiles`)

- Rendered by `+layout.svelte` whenever there is no active profile (the layout redirects there when unauthenticated, and away from it once a profile is activated).
- `ProfilePicker.svelte` lists profiles as cards (password-protected ones show a lock); clicking a passwordless profile activates it, a password-protected one opens `UnlockProfileModal`.
- Footer button opens `CreateProfileModal` (name + optional password). The created profile is activated immediately.

### Header Profile Menu

- `Header.svelte` shows the active profile's initial + name in the top-right `.profile-btn`.
- The dropdown offers **Switch profile** and **Log out**, both clearing the session (→ picker).

### Settings Profile Management (`/settings`)

- A **Profiles** group lists all profiles; the active one is marked **Current**.
- **Create profile** opens `CreateProfileModal`.
- **Rename** opens `RenameProfileModal`.
- **Timezone** selector sets the profile timezone (IANA identifier, e.g. `Asia/Tokyo`). This determines how user-entered dates are interpreted and how stored UTC timestamps are displayed. See `doc/timezone_model.md`.
- **Date format** selector sets the display order of calendar dates across the app: `DD/MM/YYYY` (default), `MM/DD/YYYY` or `YYYY-MM-DD` (ISO). It is independent of the language locale, stored in `localStorage` (`dateFormat`) like the timezone and display currency, and shown with a live example. Month names (`January 2025`) keep their locale form. Known limits: native `<input type="date">` / `datetime-local` pickers still follow the browser locale, and the dashboard, entities, portfolio-assets and income charts keep the raw API labels they always had.
- **Delete** is a two-stage flow: `ConfirmDeleteModal` first, then `DeleteProfileModal` which requires typing the localized word for "delete" (`DELETE` / `BORRAR` per active language) to enable the destructive button. A 409 from the backend surfaces "cannot delete the last profile". Deleting the active profile logs the user out.

## API Integration

### Client Configuration

- Base URL: `/api/v1` (proxied via Vite/SvelteKit in dev, same-origin in production)
- All requests include `Content-Type: application/json`
- Error responses parsed into consistent error objects
- Network errors caught and surfaced through UI store

### API Module Structure

```text
lib/api/
├── client.js          # fetch wrapper (get, post, put, del)
├── crud.js            # Generic CRUD: getList, getOne, create, update, remove
├── analytics.js       # analytics endpoints: getDashboard, getHoldings, etc.
└── snapshots.js       # balance-snapshots: create, list, update, delete
```text

## Responsive Breakpoints

```css
--bp-sm: 640px;
--bp-md: 768px;
--bp-lg: 1024px;
--bp-xl: 1280px;
```text

- Mobile: sidebar collapses to hamburger menu
- Tablet: sidebar icons only (collapsed)
- Desktop: full sidebar with labels

## View Specifications

Full per-view specifications live in `doc/subsystems/views/`, one file per view:

| File | View |
|------|------|
| [views/dashboard.md](views/dashboard.md) | Dashboard (`/`) — metric cards, charts, quick actions, balance reconciliation |
| [views/currencies.md](views/currencies.md) | Currencies (`/currencies`) — holdings/rates charts, sync behavior, price-sync trigger rules |
| [views/performance.md](views/performance.md) | Performance (`/performance`) — P&L cards, currency selector, sortable gains table |
| [views/strategy.md](views/strategy.md) | Investment strategy (`/strategy`) — target-set timeline, editor, current drift |
| [views/debt.md](views/debt.md) | Debt (`/debt`) — payable and receivable debts, rates, payments, plan, settlement |
| [views/investment_market_cycle.md](views/investment_market_cycle.md) | Investment Market Cycle (`/investment-market-cycle`) — circular state-machine diagram, scope selector, metric panel, entry signals |
| [views/tax.md](views/tax.md) | Tax (`/tax`) + fiscal Settings sections — fiscal-year table, tax rates & rules CRUD |

Other views are documented via their use cases (`doc/uc_*.md`); they can be promoted to their own `views/*.md` file when they need full-spec treatment.

## Manual Valuations UI (UC-45)

Manual-tracked assets (`tracking_mode = manual`) cannot be priced from market data, so their value is a user-stated **total position value** recorded as point-in-time snapshots in the `manual_values` ledger. The UI keeps this transparent: no mode-specific read endpoints — the backend resolves the ledger for holdings/charts automatically.

### Portfolio Assets page (`/portfolio-assets`)

**Editing the current value** (existing Edit modal, unchanged flow):

- The modal's "Manual Value" field initializes from the **latest ledger entry** (the value the analytics actually use), not the legacy column.
- Saving `PUT /portfolio-assets/{id}` with a manual value transparently upserts a new ledger snapshot. `effective_date` defaults to today; the modal offers a date picker to backdate a correction.

**Valuation history (asset detail area):**

- Clicking a manual-tracked asset row opens its detail area (where the price chart shows for auto assets). For manual assets this area renders a **Valuations** list instead of the price chart.
- Each row: `effective_date` · `value` · `notes` · delete action.
- Header action: **Add Valuation** (value + effective date, default today).
- Revaluing on a date that already has a snapshot replaces that date's entry (UPSERT) — shown inline as an edit on the existing row rather than a duplicate.

| Component | Type | API |
|-----------|------|-----|
| `ManualValuationList` | New | `GET /portfolio-assets/{id}/manual-values` |
| `AddManualValueModal` | New | `POST /portfolio-assets/{id}/manual-values` |
| Edit inline | New | `POST /portfolio-assets/{id}/manual-values` (UPSERT) |
| Delete action | New | `DELETE /portfolio-assets/{id}/manual-values/{value_id}` |

## Expandable Per-Buy Detail (Portfolio Assets)

Each portfolio-assets row aggregates the buys of one asset. A chevron (▶/▼) in the first cell expands the row into a nested sub-table that lists the buys that make up the open position, one row per buy:

- Columns: date · broker (entity) · category (NORMAL/DCA/REBALANCE) · quantity · unit price · total · currency.
- The broker column shows how the position is split across entities: an asset held at more than one broker lists one row per broker buy.
- Each row shows the buy's **remaining** shares (per FIFO) and its cost basis, not the original purchase amount. A buy whose shares are all consumed by sells leaves no row. Example: buy 500 + buy 300, then sell 550 leaves one row of 250 shares from the second buy.
- Only assets with an open position show the chevron (`asset.transactions` non-empty). Fully sold assets show no chevron.
- Clicking elsewhere on the row keeps the existing behavior: it opens the price chart (auto assets) or the Valuations list (manual assets) below the table.

| Component | Type | API |
|-----------|------|-----|
| Asset row chevron + nested buy table | New | data from `GET /portfolio-assets` (`transactions` field) |

## Entities Page

The Entities page (`/entities`) shows one row per entity with columns Name · Type · Country · Cash · Others · Actions. "Cash" sums the entities' CASH asset class and "Others" sums all non-cash classes; both are converted to the display currency.

- A currency selector in the page header (same pattern as Tax and Portfolio Assets) refetches holdings in the selected currency.
- Each entity row carries a chevron (▶/▼) that expands the entity into a nested sub-table with one row per currency and the entity's asset classes as columns, shown in **native currency** (no conversion).
- Below the per-currency sub-table, a historical chart shows one series per asset class (CASH included; manual-tracked assets sit in their market class) over the selected range. It reads `GET /analytics/historical-by-asset-class` with `entity_id` and `display_currency`, and offers the same 3M/6M/1Y/All/Custom presets as the dashboard.

## Implementation Phases

| Phase | What | Status |
|-------|------|--------|
| 0 | Foundation: SvelteKit migration, layout, API client, base components, UI.md | ✅ Done |
| 1 | Backend: entity + asset_class analytics endpoints | ✅ Done |
| 2 | Dashboard: summary cards, charts (historical, entity, asset_class), cross-tab table, quick actions | ✅ Done |
| 3 | Entities CRUD | ✅ Done |
| 4 | Market Assets CRUD | ✅ Done |
| 5 | Portfolio Assets CRUD | ✅ Done |
| 6 | Transactions + Transfers | ✅ Done |
| 7 | Analytics: Cash Flow, Dividends, Performance | ✅ Done |
| 8 | Schedules + Admin: Currencies, Balance Snapshots, Fiscal Exemptions, Prices | ✅ Done |

Post-phase feature tracks (Income page, Tax page, fiscal rules engine, profiles) are tracked via their use cases and `doc/plans/`.
