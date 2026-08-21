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
| `CrossTabTable` | New | `/analytics/holdings-by-entity` | 2 |
| `AddAssetModal` | New | POST `/portfolio-assets` + POST `/transactions/full` | 2 |
| `AddIncomeModal` | New | POST `/transactions/full` | 2 |

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

## Balance Snapshot Constraint

When creating or editing a transaction or schedule, if a `balance_snapshot` exists for the selected `(entity_id, currency)` pair, the form SHALL display a warning if the chosen `timestamp` / `start_date` is less than or equal to the snapshot's `timestamp`. The backend returns 409 in this case, but the UI should proactively surface the snapshot date as a constraint to the user before submission.

## Realized P&L card percentage

The dashboard's **Realized P&L** card shows a client-side percentage: `realized_pl / total_invested × 100` ("all time"), i.e. relative to the cost basis of currently held positions. This intentionally differs from the Performance page's **Realized P&L %** card, which divides by the cost basis of *sold* lots only (see `views/performance.md`). Each card's tooltip documents its own base.
