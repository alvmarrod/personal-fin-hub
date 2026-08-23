# View: Performance (`/performance`)

> Combined performance indicators (unrealized + realized P&L + investment income) and the per-sale Realized Gains ledger. Component/design conventions live in `doc/subsystems/UI.md`; calculation semantics in `doc/calculations.md` §6, §10–§12, §14.3 and §16; use cases UC-32/UC-34.

## Layout

```text
+------------------------------------------------------------------------+
| [☰] Performance  [⚠ Some values use the closest available rate ...]     |
|                  [USD ▾]                                    [⟳ Tut.]   |  ← warning chip inline in the header line
+------------+-----------------------------------------------------------+
|            |  ┌─ Portfolio ──────────────┐┌─ Total ────────┐          |
| Performance| │ │Portfolio│Invested │Inv.││ │Total Ret. %  │          |  ← row 1: Portfolio 3fr + Total 2fr
|            | │ │Value    │Now      │Hist││ │Total (Amt)   │          |
|            |  └──────────────────────────┘└────────────────┘          |
|            |  ┌ Unrealized ┐┌ Realized·Trading ┐┌ Income ┐           |
|            |  │ │Un.P&L %│ │ │Real.% │Real.P&L│ │Div.+yield│         ← row 2: three groups side-by-side
|            |  │ │Un.P&L  │ │ │(Trading cards) │ │Int.    │          |
|            |  └───────────┘└──────────────────┘└────────┘           |
|            |  Trading Realized Gains (FIFO)                           |
|            |  ┌──────────────────────────────┐                        |
|            |  │ Sortable table, one row per  │                        |  ← 9 columns, ▲/▼ sorting
|            |  │ sell transaction             │                        |
|            |  └──────────────────────────────┘                        |
+------------+-----------------------------------------------------------+
```

All cards on this page use the **compact** `MetricCard` variant; cards are grouped inside `MetricGroup` sections — transparent containers with a solid colored limit line and a small tab label sitting on the border. Group tones: Portfolio = blue (`--color-primary`), Total = amber (`--color-warning`), Unrealized = light blue (`--color-baby-blue`), Realized · Trading = green (`--color-success`), Investment Income = purple (`#845ef7`). Row 1 is a weighted `3fr/2fr` grid (Portfolio holds 3 cards, Total 2); row 2 places the Unrealized / Trading / Income trio side-by-side; both rows stack to a single column below 900px.

## Data Loading

- `analytics.performance(displayCurrency, locale)` and `analytics.realizedGains()` load in parallel on mount; the display-currency selector reloads both.
- `currenciesApi.getList()` populates the currency selector (hidden while empty).
- The active **locale** is sent so the backend can infer the default fiscal rule for period-less sells (`es` → `spain`, `ja` → `japan`, else `default`).

## Metric Cards

Compact `MetricCard`s grouped by theme. Percentage and P&L cards render a ▲/▼ direction arrow colored green/red via the `valueVariant` prop (`positive`/`negative`) — this page has no period-comparison subtitle, so direction lives on the value itself.

The page renders **two full-width group bands**, each a single visual row: free cards and nested `MetricGroup`s share the same grid line, with nested groups drawn as bordered sub-sections (own colored tab line) inside the parent border. The **Portfolio** band (primary-blue line) wraps the **Unrealized** sub-group (baby-blue); the **Realized** band (green line) wraps the **Realized · Trading** (amber) and **Investment Income** (purple) sub-groups. Below 1100px each band collapses to two columns; below 900px the header chip hides separately (see above).

| Band | Group | Card | Value source | Tooltip base |
|-------|------|--------------|--------------|
| Portfolio | — | Portfolio Value | `total_portfolio_value` | current holdings + cash, display currency |
| Portfolio | — | Invested Now | `total_invested_now` | FIFO cost basis of held shares |
| Portfolio | — | Invested Historic | `total_invested_historic` | Σ buys at each purchase-date rate |
| Portfolio | Unrealized | Unrealized P&L % | `unrealized_pl_pct` | ÷ current cost basis |
| Portfolio | Unrealized | Unrealized P&L | `total_unrealized_pl` | holdings value − cost basis, latest rates |
| Realized | — | Total Return | `total_return_pct` | (unrealized + realized trading + dividends) ÷ invested historic |
| Realized | — | Total Return (Amount) | `total_return` | same numerator as the % card, absolute display-currency amount |
| Realized | Realized · Trading | Realized P&L % (Trading) | `realized_pl_pct` | ÷ cost basis of **sold** lots (FIFO), frozen fiscal-rule conversion; excludes dividends |
| Realized | Realized · Trading | Realized P&L (Trading) | `total_realized_pl` | Σ per-sale gains under each sell's frozen rule; dividends counted separately |
| Realized | Investment Income | Dividends | `total_dividends` + sub-line `dividend_yield_pct` | Σ payments at each payment-date rate; yield = ÷ invested historic |
| Realized | Investment Income | Interest | `total_interest` | Σ payments at each payment-date rate; shown separately (cash-derived) |

> The Total Return cards live in the Realized band for layout purposes but their numerator includes the unrealized component (see the card tooltip). The Dividends card uses the `MetricCard` `change`/`changeLabel` sub-line to show the all-time yield (`dividend_yield_pct`, labeled "all-time"). The Realized P&L % denominator (sold lots only) intentionally differs from the dashboard card's total-invested base — see `views/dashboard.md`.

## Rate-Fallback Warning

When the response's `rate_fallbacks` array is non-empty (closest-in-time rate used, or no rate at all — §16.4; with the two-business-day staleness rule this means genuinely outdated data, never a routine weekend close), a small amber **chip** renders inline in the page-header line — between the "Performance" title and the currency selector. It shows a ⚠ icon, the bold short title and the full explanation in `--font-size-xs` text, followed by the affected currencies with each one's earliest missing date (e.g. `: USD (11/3/2024), GBP (1/10/2025)`, codes emphasized in amber). A small **Sync Rates** button inside the chip triggers the same FX sync as the Currencies page (`POST /currencies/sync`, UC-47) and reloads the data in place — once the gaps are filled the chip disappears; circuit-open failures show the standard unavailable note instead of reloading. The chip wraps to at most a couple of lines (`max-width: 640px`). It appears only once data has loaded (it is derived from the response) and is hidden below 768px, where the header is too cramped.

## Trading Realized Gains Table

One row per sell transaction, native values (no display-currency conversion). All 9 columns are sortable using the shared sortable-table pattern (see `UI.md` → Component Conventions):

| Column | Sort key | Type |
|--------|----------|------|
| Asset | `ticker \|\| market_code` (column accessor) | string |
| Sell Date | `sell_date` | string (ISO) |
| Qty | `sell_quantity` | number |
| Sell Price | `sell_price` | number |
| Sell Total | `sell_total` | number |
| Cost Basis | `cost_basis` | number |
| P&L | `realized_pl` | number |
| P&L % | `realized_pl_pct` | number |
| Currency | `currency` | string |

- Default sort: **Sell Date descending** (newest sells first).
- Numeric columns sort **descending** on first click; text columns ascending; clicking the active column toggles direction.
- Sorting is client-side over the full loaded list.
- Empty state: "No realized gains recorded yet." when the list is empty.

## API Dependencies

| Endpoint | Purpose |
|----------|---------|
| `GET /analytics/performance?display_currency=&locale=` | Summary cards (fields incl. `rule_key`, `rate_fallbacks`, `realized_pl_pct`, `total_dividends`, `dividend_yield_pct`, `total_interest`) |
| `GET /analytics/realized-gains` | Trading Realized Gains table rows |
| `GET /currencies` | Display-currency selector options |

## Tutorial

Interactive walkthrough registered under page key `performance` (mock data includes the income fields); replayable via the header ReplayButton.
