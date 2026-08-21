# View: Performance (`/performance`)

> Combined performance indicators (unrealized + realized P&L + investment income) and the per-sale Realized Gains ledger. Component/design conventions live in `doc/subsystems/UI.md`; calculation semantics in `doc/calculations.md` §6, §10–§12, §14.3 and §16; use cases UC-32/UC-34.

## Layout

```text
+----------------------------------------------------------+
| [☰]  Performance                        [USD ▾] [⟳ Tut.] |  ← Display currency + tutorial replay
+------------+---------------------------------------------+
|            |  ⚠ Rate fallback warning (conditional)       |
|            |  ┌─ Portfolio ─────────────────────────┐     |
| Performance|  │ │Portfolio│Invested │Invested │      |     |  ← MetricGroup, blue line
|            |  │ │Value    │Now      │Historic │      |
|            |  └─────────────────────────────────────┘     |
|            |  ┌ Unrealized ┐┌ Realized·Trading ┐┌ Income┐|
|            |  │ │Un.P&L %│ │ │Real.% │Real.P&L│ │Div.  ││   ← three groups in a row
|            |  │ │Un.P&L  │ │ │(Trading cards) │ │Int.  ││
|            |  └───────────┘└──────────────────┘└──────┘|
|            |  ┌─ Total ─────────────────────────────┐     |
|            |  │ │Total Return %│Total Return (Amt)│       |  ← MetricGroup, amber line
|            |  └─────────────────────────────────────┘     |
|            |  Realized Gains (FIFO)                       |
|            |  ┌──────────────────────────────┐            |
|            |  │ Sortable table, one row per  │            |  ← 9 columns, ▲/▼ sorting
|            |  │ sell transaction             │            |
|            |  └──────────────────────────────┘            |
+------------+---------------------------------------------+
```

All cards on this page use the **compact** `MetricCard` variant; cards are grouped inside `MetricGroup` sections — transparent containers with a solid colored limit line and a small tab label sitting on the border. Group tones: Portfolio = blue (`--color-primary`), Unrealized = light blue (`--color-baby-blue`), Realized · Trading = green (`--color-success`), Investment Income = purple (`#845ef7`), Total = amber (`--color-warning`). The Unrealized / Trading / Income trio sits side-by-side in one responsive grid row.

## Data Loading

- `analytics.performance(displayCurrency, locale)` and `analytics.realizedGains()` load in parallel on mount; the display-currency selector reloads both.
- `currenciesApi.getList()` populates the currency selector (hidden while empty).
- The active **locale** is sent so the backend can infer the default fiscal rule for period-less sells (`es` → `spain`, `ja` → `japan`, else `default`).

## Metric Cards

Compact `MetricCard`s grouped by theme. Percentage and P&L cards render a ▲/▼ direction arrow colored green/red via the `valueVariant` prop (`positive`/`negative`) — this page has no period-comparison subtitle, so direction lives on the value itself.

| Group | Card | Value source | Tooltip base |
|-------|------|--------------|--------------|
| Portfolio | Portfolio Value | `total_portfolio_value` | current holdings + cash, display currency |
| Portfolio | Invested Now | `total_invested_now` | FIFO cost basis of held shares |
| Portfolio | Invested Historic | `total_invested_historic` | Σ buys at each purchase-date rate |
| Unrealized | Unrealized P&L % | `unrealized_pl_pct` | ÷ current cost basis |
| Unrealized | Unrealized P&L | `total_unrealized_pl` | holdings value − cost basis, latest rates |
| Realized · Trading | Realized P&L % (Trading) | `realized_pl_pct` | ÷ cost basis of **sold** lots (FIFO), frozen fiscal-rule conversion; excludes dividends |
| Realized · Trading | Realized P&L (Trading) | `total_realized_pl` | Σ per-sale gains under each sell's frozen rule; dividends counted separately |
| Investment Income | Dividends | `total_dividends` + sub-line `dividend_yield_pct` | Σ payments at each payment-date rate; yield = ÷ invested historic |
| Investment Income | Interest | `total_interest` | Σ payments at each payment-date rate; shown separately (cash-derived) |
| Total | Total Return | `total_return_pct` | (unrealized + realized trading + dividends) ÷ invested historic |
| Total | Total Return (Amount) | `total_return` | same numerator as the % card, absolute display-currency amount |

> The Dividends card uses the `MetricCard` `change`/`changeLabel` sub-line to show `dividend_yield_pct` ("of all-time invested"). The Realized P&L % denominator (sold lots only) intentionally differs from the dashboard card's total-invested base — see `views/dashboard.md`.

## Rate-Fallback Warning

When the response's `rate_fallbacks` array is non-empty (closest-in-time rate used, or no rate at all — §16.4), a warning callout renders above the cards (`performance.rateFallbackTitle` / `rateFallbackMsg`), matching the portfolio-assets stale-data banner pattern.

## Realized Gains Table

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
| `GET /analytics/realized-gains` | Realized Gains table rows |
| `GET /currencies` | Display-currency selector options |

## Tutorial

Interactive walkthrough registered under page key `performance` (mock data includes the income fields); replayable via the header ReplayButton.
