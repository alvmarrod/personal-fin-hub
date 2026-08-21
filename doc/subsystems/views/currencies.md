# View: Currencies (`/currencies`)

> Extracted from `doc/subsystems/UI.md`. Component/design conventions live there.

## Layout

```text
+----------------------------------------------------------+
| [☰]  Currencies                              [Sync Rates]|  ← Header + sync button
+------------+---------------------------------------------+
|            |  ┌──────┬──────┬──────┐                      |
| Currencies |  │ USD  │ EUR  │ JPY  │                      |  ← 3 metric cards (total per currency)
|            |  │$50K  │€12K  │¥600K │                      |
|            |  └──────┴──────┴──────┘                      |
|            |                                               |
|            |  Holdings by Currency                         |
|            |  [Display: USD ▾]  [3m] [6m] [1y] [All]      |  ← Display currency selector + time presets
|            |  ┌──────────────────────────────┐            |
|            |  │ 📊 Stacked Area Chart         │            |  ← Holdings converted to display currency
|            |  │ (USD + EUR→USD + JPY→USD)     │            |
|            |  └──────────────────────────────┘            |
|            |                                               |
|            |  Exchange Rates                               |
|            |  [Base: USD ▾]     [3m] [6m] [1y] [All]      |  ← Base currency selector + time presets
|            |  ┌──────────────────────────────┐            |
|            |  │ 📈 Line Chart (dual Y-axis)   │            |  ← EUR/USD (left), JPY/USD (right)
|            |  │                              │            |
|            |  └──────────────────────────────┘            |
+------------+---------------------------------------------+
```

## Components Used

| Component | Purpose | API |
|-----------|---------|-----|
| `MetricCard` | Total per currency (raw values) | `GET /currencies/holdings` (latest_raw) |
| `StackedAreaChart` | Holdings over time by currency | `GET /currencies/holdings` |
| `LineChart` | Exchange rate history (dual axis) | `GET /currencies/rate-chart` |
| `Select` | Display currency / Base currency selectors | - |
| `Button` | Sync Rates button | `POST /currencies/sync` |

## API Dependencies

| Endpoint | Purpose |
|----------|---------|
| `GET /currencies` | List available currency codes |
| `GET /currencies/holdings?start_date=&end_date=&display_currency=` | Holdings time series converted to display currency |
| `GET /currencies/rate-chart?base_currency=&start_date=&end_date=` | Exchange rate datasets with JPY special handling |
| `POST /currencies/sync` | Sync rates from Market API |

## Time Presets

| Key | Label | Range |
|-----|-------|-------|
| `3m` | 3 months | Last 3 months (default) |
| `6m` | 6 months | Last 6 months |
| `1y` | 1 year | Last 12 months |
| `all` | All | No date filter |
| `custom` | Custom | User-defined start/end dates |

## Currency Conversion Logic

**Holdings Chart:**

- Backend receives `display_currency` parameter
- For each date, calculates raw holdings per currency (cash + investments)
- Converts non-display currencies using exchange rates as of that date
- Returns series with all values in display currency

**Exchange Rates Chart:**

- Backend receives `base_currency` parameter
- Generates datasets for all other currencies vs base
- **JPY special handling:** JPY pairs use right Y-axis and inverted values (e.g., 160 JPY/USD instead of 0.00625 USD/JPY) for readability

## Sync Behavior

1. User clicks "Sync Rates" button
2. Frontend calls `POST /currencies/sync`
3. Backend generates all unique currency pair combinations from database
4. For each pair, fetches OHLCV history from Market API
5. Upserts `Close` values into `currencies` table
6. Frontend reloads holdings and rate chart data

## Price Sync Behavior (Portfolio Assets / Market Assets)

1. **Manual** — "Sync Prices" button calls `POST /market/sync-prices?full=false&pace=2&max_age_hours=1` (skips symbols fetched < 1h ago).
2. **Auto on page load** — opening either `/portfolio-assets` or `/market-assets` fires the same incremental sync **in the background** (fire-and-forget): the page paints immediately, the button is disabled (`syncing` state) while it runs, and on completion the button re-enables and the page content refreshes. A `busy` response (another sync already running) or a failure is swallowed — the table is never replaced.
3. **Scheduled** — the backend cron (00:00, 12:00 UTC) runs a full paced refresh independently of the UI (UC-46).
4. All three share one endpoint and are single-flight (never overlap); `tracking_mode = manual` assets are always skipped.
