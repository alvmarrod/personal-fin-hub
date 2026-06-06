# Subsystem: UI (Frontend)

## Technology Stack

| Layer | Choice |
|-------|--------|
| Framework | SvelteKit (adapter-static, SPA mode) |
| Language | JavaScript (JS, no TypeScript) |
| Bundler | Vite (via SvelteKit) |
| Charts | Chart.js |
| CSS | Pure CSS with custom properties (no framework) |
| Package Manager | npm (via Docker) |

## Project Structure

```
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
│   ├── performance/            # Performance summary
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
│   │   └── MetricCard.svelte
│   └── stores/
│       └── ui.js               # UI state (sidebar, modals, etc.)
├── app.html                    # SvelteKit HTML shell
└── app.css                     # Global styles + CSS variables
```

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
```

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
```

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
```

### Border Radius

```css
--radius-sm: 4px;
--radius-md: 8px;
--radius-lg: 12px;
--radius-full: 9999px;
```

### Shadows

```css
--shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
--shadow-md: 0 4px 6px rgba(0,0,0,0.07);
--shadow-lg: 0 10px 15px rgba(0,0,0,0.1);
```

## Component Conventions (Svelte 5)

### Runes API
All components use Svelte 5 runes (`$state`, `$derived`, `$effect`, `$props`) instead of the legacy `export let` / `$:` syntax.

### Props Pattern
```svelte
<script>
  let { label, value, onAction } = $props();
</script>
```

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
```

### CSS Scoping
Styles are scoped per component. Global styles go in `app.css`. Theme-dependent values use CSS custom properties.

### Layout Component
```svelte
+layout.svelte
├── Header ribbon (navigation + actions)
├── Sidebar (collapsible on mobile)
└── <slot/> (page content)
```

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
| `/performance` | Performance | Phase 7 |
| `/schedules` | Schedules | Phase 8 |
| `/balance-snapshots` | Balance Snapshots | Phase 8 |
| `/currencies` | Currencies | Phase 8 (read-only + sync pending) |
| `/fiscal-exemptions` | Fiscal Exemptions | Phase 8 |

### Header Ribbon
- Navigation items (initially only Dashboard)
- Quick action buttons (initially "Add Asset", "Add Income")
- Breadcrumb for sub-routes

## API Integration

### Client Configuration
- Base URL: `/api/v1` (proxied via Vite/SvelteKit in dev, same-origin in production)
- All requests include `Content-Type: application/json`
- Error responses parsed into consistent error objects
- Network errors caught and surfaced through UI store

### API Module Structure
```
lib/api/
├── client.js          # fetch wrapper (get, post, put, del)
├── crud.js            # Generic CRUD: getList, getOne, create, update, remove
├── analytics.js       # analytics endpoints: getDashboard, getHoldings, etc.
└── snapshots.js       # balance-snapshots: create, list, update, delete
```

## Responsive Breakpoints

```css
--bp-sm: 640px;
--bp-md: 768px;
--bp-lg: 1024px;
--bp-xl: 1280px;
```

- Mobile: sidebar collapses to hamburger menu
- Tablet: sidebar icons only (collapsed)
- Desktop: full sidebar with labels

## Dashboard Specification (Phase 2)

### Layout
```
+----------------------------------------------------------+
| [☰]  Dashboard                 [+Add Asset] [+Add Income]|  ← Header ribbon
+------------+---------------------------------------------+
|            |  ┌──────┬──────┬──────┬──────┐               |
| Dashboard  |  │Total │Cash  │Invest│Return│               |  ← 4 metric cards
|            |  │Value │Bal.  │ed    │%     │               |
|            |  └──────┴──────┴──────┴──────┘               |
|            |  ┌──────────────────────────────┐            |
|            |  │ 📈 Historical Value (Line)    │            |  ← Chart.js Line chart
|            |  │                              │            |
|            |  └──────────────────────────────┘            |
|            |  ┌─────────────┐ ┌─────────────┐            |
|            |  │ 🍩 By Entity│ │ 🥧 By Asset │            |  ← Chart.js Doughnut + Pie
|            |  │ (Doughnut)  │ │ Class (Pie) │            |
|            |  └─────────────┘ └─────────────┘            |
|            |  ┌──────────────────────────────┐            |
|            |  │ Summary Table: Asset Class × │            |  ← Cross-tab table
|            |  │ Entity                       │            |
|            |  └──────────────────────────────┘            |
+------------+---------------------------------------------+
```

### Components Needed

| Component | Type | API | Phase |
|-----------|------|-----|-------|
| `MetricCard` | Existing (enhance) | `/analytics/dashboard` | 2 |
| `HistoricalChart` | New | `/analytics/historical` | 2 |
| `DoughnutChart` | New | `/analytics/allocation?dimension=entity` | 2 |
| `PieChart` | New | `/analytics/allocation?dimension=asset_class` | 2 |
| `CrossTabTable` | New | `/analytics/holdings-by-entity` | 2 |
| `AddAssetModal` | New | POST `/portfolio-assets` + POST `/transactions/full` | 2 |
| `AddIncomeModal` | New | POST `/transactions/full` | 2 |

### API Dependencies
- `GET /analytics/dashboard` — 4 metric cards
- `GET /analytics/historical?start_date=...&end_date=...&interval=month` — Line chart
- `GET /analytics/allocation?dimension=entity` — Doughnut chart by entity
- `GET /analytics/allocation?dimension=asset_class` — Pie chart by asset class
- `GET /analytics/holdings-by-entity` — Cross-tabulation table
- `POST /transactions/full` — Add Asset / Add Income quick actions

### Quick Actions
Two header buttons that open modals:
1. **+Add Asset**: Form to record current holdings (portfolio_asset + initial buy transaction)
2. **+Add Income**: Form to record recurring income (MONEY_IN transaction)

Both use `POST /transactions/full` with appropriate type and data.

### Balance Snapshot Constraint
When creating or editing a transaction or schedule, if a `balance_snapshot` exists for the selected `(entity_id, currency)` pair, the form SHALL display a warning if the chosen `timestamp` / `start_date` is less than or equal to the snapshot's `timestamp`. The backend returns 409 in this case, but the UI should proactively surface the snapshot date as a constraint to the user before submission.

## Implementation Phases

| Phase | What | Status |
|-------|------|--------|
| 0 | Foundation: SvelteKit migration, layout, API client, base components, UI.md | ✅ Done |
| 1 | Backend: entity + asset_class analytics endpoints | ✅ Done |
| 2 | Dashboard: summary cards, charts (historical, entity, asset_class), cross-tab table, quick actions | 🔜 Next |
| 3 | Entities CRUD | ⏳ |
| 4 | Market Assets CRUD | ⏳ |
| 5 | Portfolio Assets CRUD | ⏳ |
| 6 | Transactions + Transfers | ⏳ |
| 7 | Analytics: Cash Flow, Dividends, Performance | ⏳ |
| 8 | Schedules + Admin: Currencies, Balance Snapshots, Fiscal Exemptions, Prices | ⏳ |
