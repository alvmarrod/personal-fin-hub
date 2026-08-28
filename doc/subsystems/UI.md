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
│   ├── balance-snapshots/      # Balance snapshots
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
│   │   ├── ChartCard.svelte
│   │   └── charts/
│   │       ├── LineChart.svelte
│   │       ├── StackedBarChart.svelte
│   │       ├── StackedAreaChart.svelte
│   │       ├── PieChart.svelte
│   │       └── DoughnutChart.svelte
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

- Source of truth: `$lib/i18n/index.svelte.ts`. Two dictionaries, `en-US` and
  `es-ES` (`locales/en.ts` / `locales/es.ts`).
- API: `t(key, params)` translates; `locale()` returns the active locale;
  `setLocale(code)` persists it to `localStorage`. On first visit the locale is
  detected from the browser language (`es*` → `es-ES`, else `en-US`).
- Key parity between the two dictionaries is enforced by `bun run validate-i18n`
  (CI gate). Every new key must be added to both `en.ts` and `es.ts`.

### Number Formatting

Amounts are rendered through `formatAmount(value, currency)`
(`$lib/utils/format.svelte.ts`). Storage never changes: the backend returns
full precision and the format is display-only.

- Locale: formatting uses the app `locale()` (`en-US` / `es-ES`). Separators and
  decimal symbols follow the selected language (`es-ES`: `1.234,56`;
  `en-US`: `1,234.56`).
- Grouping: the thousands separator is always shown, for every magnitude
  (`es-ES` `8.340`, not `8340`), regardless of the locale's default grouping
  rule.
- No trailing zeros: `minimumFractionDigits: 0`, so integers render without a
  decimal part.
- Decimal precision adapts to magnitude:

| Abs value             | EUR / USD / others | JPY |
|-----------------------|--------------------|-----|
| ≥ 1,000 (JPY ≥ 10,000)| 0 decimals         | 0   |
| ≥ 1                   | 2 decimals         | 2   |
| < 1                   | 3 decimals         | 3   |

Example: `14.53` EUR → `14,53`; `1.234.567` EUR → `1.234.567`;
JPY `9.802,45` keeps 2 decimals, `678.841` renders whole.

Dates use the same locale discipline via `formatDate` / `formatDateTime` in the
same module.

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
| `/transfers/new` | New Transfer | Phase 6 |
| `/cash-flow` | Cash Flow | Phase 7 |
| `/dividends` | Dividends | Phase 7 |
| `/income` | Income summary & sources | Income |
| `/performance` | Performance | Phase 7 |
| `/tax` | Tax (taxable P&L per fiscal year) | Tax & Fiscal |
| `/schedules` | Schedules | Phase 8 |
| `/balance-snapshots` | Balance Snapshots | Phase 8 |
| `/currencies` | Currencies | Phase 8 |
| `/fiscal-exemptions` | Fiscal Exemptions | Phase 8 |
| `/profiles` | Profile picker (shown when no active profile) | Profiles |
| `/settings` | Settings incl. profile management | Profiles |

### Header Ribbon

- Navigation items (initially only Dashboard)
- Quick action buttons (initially "Add Asset", "Add Income")
- Breadcrumb for sub-routes

### Sidebar

- Grouped menu (Overview / Activity / Investments / Analysis / Setup) driven by the routes table above.
- Compact sizing: width uses `clamp(180px, 12vw, 240px)` with tighter paddings/gaps in relative units; the menu is scrollable (`overflow-y: auto`) when entries exceed the viewport height.

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
