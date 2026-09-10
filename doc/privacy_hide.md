# Privacy Hide

A frontend-only toggle that masks all monetary values in the UI, allowing the user
to share their screen or walk through portfolio data without exposing actual amounts.

## Behavior

- Toggle button (eye icon) in the top-right header, left of the profile selector.
- State persists in `localStorage` (`privacyHidden` key) across page navigations
  and browser refreshes.
- Defaults to **off** (all values visible).

## Mask contract

When enabled:

- All monetary amounts render as `********` (fixed 8 asterisks).
- Where a currency symbol applies, it remains as a hint: `********€`.
- Percentages (e.g. unrealized P/L %) and percentage-change indicators remain
  visible: `MetricCard` does not mask pre-formatted strings that contain `%`.
- Dates, entity names, asset names, currency codes, FX rates, and status
  indicators remain visible.
- The `MetricCard` tooltip title follows the same rules and does not leak an
  unmasked value while hiding is on.

## Affected pages

| Page | Masked values |
|---|---|
| Dashboard | MetricCard amounts, LineChart Y-axis + tooltip, GroupedTable original + unified amounts, Doughnut/Pie in-slice currency labels + tooltip |
| Portfolio Assets | current-value column, expanded-row quantities + amounts, LineChart + StackedAreaChart Y-axis + tooltip (Invested / Investment Value), manual valuations |
| Cash-flow | MetricCard amounts, StackedBarChart Y-axis + tooltip, period/group/type totals, per-row native + display amounts |
| Transactions | amount column |
| Entities | money values in fmtMoney/fmtNative, LineChart Y-axis + tooltip |
| Dividends | MetricCard amounts, DoughnutChart tooltip + segment labels, per-row amounts |
| Income | MetricCard amounts, StackedBarChart Y-axis + tooltip, source + recent-row amounts |
| Tax | year-card totals, foot totals, per-row native/display/taxable/tax-owed amounts |
| Performance | MetricCard amounts, gains-table amounts |
| Balance Snapshots | amount column |
| Schedules | total-value column |
| Fiscal Exemptions | amount + rate-limit columns |
| Settings | tax-rate bracket amounts |
| Detail Transaction Modal | total_value, quantity, unit_price, gross, net, fee fixed amounts, tax amounts |

## Not masked

- Percentages and percentage-change indicators
- Dates and timestamps
- Entity and asset names
- Currency codes (JPY, EUR, …)
- FX rate values (e.g. 1.2345)
- Badges and status labels
- Schedule names, notes, attachment indicators
- Category and type labels
