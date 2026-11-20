# View: Dashboard (`/`)

> Extracted from `doc/subsystems/UI.md`. Component/design conventions live there.

## Layout

```text
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

## Components Needed

| Component | Type | API | Phase |
|-----------|------|-----|-------|
| `MetricCard` | Existing (enhance) | `/analytics/dashboard` | 2 |
| `HistoricalChart` | New | `/analytics/historical` | 2 |
| `DoughnutChart` | New | `/analytics/allocation?dimension=entity` | 2 |
| `PieChart` | New | `/analytics/allocation?dimension=asset_class` | 2 |
| `GroupedTable` (Asset Class × Entity matrix) | Existing (rewritten) | `/analytics/holdings-by-entity` | 2 |
| `AddAssetModal` | New | POST `/portfolio-assets` + POST `/transactions/full` | 2 |
| `AddIncomeModal` | New | POST `/transactions/full` | 2 |

## Asset Class × Entity matrix

The summary table is a cross-tab rendered by `GroupedTable.svelte`.

- Rows are asset classes, columns are entities, both sorted by total
  (descending). Cash appears as its own class; unclassified holdings get an
  **Unclassified** row instead of disappearing.
- Every amount is the display-currency value. The share is
  `cell / grand total` with both sides converted first; native amounts only
  appear in the cell tooltip. The grand total ties out to the **Portfolio
  Value** card (cash included).
- Each cell shows the amount, and below it the share of the portfolio in a
  smaller font. The same rounded share picks one of five fixed tints:
  `<1%`, `1–5%`, `5–15%`, `15–30%`, `≥30%` (primary colour mixed over the
  surface). A legend under the table repeats the bins.
- Row and column totals repeat the amount and share; the total column is
  hidden when there is only one entity.
- A cell whose currency has no FX pair to the display currency is marked `*`
  and a note below the table names the currencies. Its weight is approximate;
  the numeric value is still the native amount, as before.
- Privacy mode removes the tint and masks both the amount and the share.
- Asset-class labels are localized (`FI` → Fixed Income, `CASH` → Cash, …);
  unknown custom values pass through unchanged. The *By Asset Class* pie uses
  the same labels.

## API Dependencies

- `GET /analytics/dashboard` — 4 metric cards
- `GET /analytics/historical?start_date=...&end_date=...&interval=month` — Line chart
- `GET /analytics/allocation?dimension=entity` — Doughnut chart by entity
- `GET /analytics/allocation?dimension=asset_class` — Pie chart by asset class
- `GET /analytics/holdings-by-entity` — Cross-tabulation table
- `POST /transactions/full` — Add Asset / Add Income quick actions

## Quick Actions

Two header buttons that open modals:

1. **+Add Asset**: Form to record current holdings (portfolio_asset + initial buy transaction)
2. **+Add Income**: Form to record recurring income (INCOME transaction with an income category)

Both use `POST /transactions/full` with appropriate type and data.

## Balance Reconciliation

Transactions and schedules are **not** restricted to dates after the latest snapshot. When recording a **spend** (`INVESTMENT_BUY`, `MONEY_OUT`, `TRANSFER_OUT`), the form offers an inject/debit choice (defaulted per operation) — *inject* inferred cash before the spend, or *debit* the balance (letting it go negative if that reflects reality). Fees, taxes, and notes are balance-neutral and can be edited on any transaction regardless of snapshot dates. See the Tier 5 Reconciliation Model (`uc_5_snapshots_balance.md`).

## Realized P&L card percentage

The dashboard's **Realized P&L** card shows a client-side percentage: `realized_pl / total_invested × 100` ("all time"), i.e. relative to the cost basis of currently held positions. This intentionally differs from the Performance page's **Realized P&L %** card, which divides by the cost basis of *sold* lots only (see `views/performance.md`). Each card's tooltip documents its own base.
