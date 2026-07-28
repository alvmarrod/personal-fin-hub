# Tier 6 — Currency

Exchange rate management and multi-currency views. These operations support the currency conversion that permeates the entire system.

---

## UC-21: Sync Exchange Rates

**Trigger**: User clicks "Sync Rates" to fetch latest exchange rates from the external market API

**Modeling decision**:

- Fetches OHLCV data for all currency pair combinations present in the `currencies` table
- Upserts `Close` values into the `currencies` table
- The `currencies` table stores market reference rates (mid-market), NOT broker-applied rates

**Algorithm**:

1. Fetch all distinct currency codes from `currencies` table
2. Generate all unique pair combinations: for N codes, N×(N-1)/2 pairs
3. For each pair, construct Market API symbol: `{CODE}{BASE}=X` (e.g., `EURUSD=X`)
4. Call Market API to fetch OHLCV history
5. For each date in history, extract `Close` value and upsert into `currencies` table
6. Return summary with rates added per pair and any errors

**Currency model**:

- Each rate row: `(code, base_code, rate, timestamp)`
- Rates are bidirectional: if only `USD/JPY` is stored, `JPY/USD` is computed as `1/rate`
- Self-rate: `(code, code, 1.0, timestamp)` is stored for each code
- These rates are used by analytics for portfolio valuation, NOT for transaction recording

**Rejected alternatives**:

- Storing only the latest rate → rejected: historical analytics need rates at past dates. Time-series storage enables historical portfolio valuation
- Using broker-applied rates → rejected: brokers don't publish continuous rate feeds. Market rates are the only reliable source for historical data
- Fetching on every page load → rejected: rates change infrequently. Manual sync is sufficient and avoids API rate limiting

**Entities affected**: `currencies` (write — upsert)

**UI pages**: Currencies page (`/currencies`) — Sync Rates button

**Constraints**:

- Market API must be available (partial failures reported per-pair)
- Rates are idempotent: re-syncing overwrites existing values
- Dynamic pair generation: adding a new currency code automatically includes it in future syncs

---

## UC-22: View Holdings by Currency

**Trigger**: User views portfolio holdings broken down by currency

**Modeling decision**:

- Shows the total value of holdings (cash + investments) per currency over time
- Answers: "How much of my portfolio is in JPY, USD, EUR?"

**Currency model**:

- **Raw values**: For each currency, sum cash balance + investment value (in native currency)
- **Converted values**: When `display_currency` is provided, convert all non-display currencies using exchange rates from `currencies` table as of each date
- **Time series**: For each date in range, compute per-currency totals and convert
- **Latest raw**: Most recent date's per-currency totals in native currencies (used by metric cards)

**Data sources**:

- Investment values: `GET /analytics/holdings` → per-asset value in asset's native currency
- Cash values: `GET /analytics/cash-flow` or snapshot-aware queries → per-entity, per-currency cash balance
- Exchange rates: `currencies` table → historical rates for conversion

**Rejected alternatives**:

- Using transaction fx_rate for conversion → rejected: that's the broker-applied rate, not the market rate. Portfolio valuation should use market rates
- Converting everything to a single currency at storage time → rejected: loses the native currency breakdown. Users need to see how much they hold in each currency

**Entities affected**: `currencies` (read), `transactions` (read), `balance_snapshots` (read), `market_assets` / `prices` (read)

**UI pages**: Currencies page (`/currencies`)

**Constraints**:

- If no rate exists for a currency pair on a given date, the value is included as-is (no conversion)
- Stacked area chart shows all currencies as separate layers

---

## UC-23: View Exchange Rate History

**Trigger**: User views historical exchange rate trends

**Modeling decision**:

- Displays historical rates from the `currencies` table as line charts
- Informational only — not used in any portfolio calculation
- Supports dual Y-axis for JPY pairs (readability)

**Currency model**:

- Base currency is user-selected (e.g., USD)
- For each other currency, fetch rate history from `currencies` table
- **JPY special handling**: JPY pairs use right Y-axis and inverted values
  - If `code == "JPY"`: label as `JPY/{base}`, invert rate (1/rate), assign to right axis
  - If `base_currency == "JPY"`: label as `JPY/{code}`, use rate as-is, assign to right axis
  - Otherwise: use left axis
- Rationale: JPY/USD ≈ 160 vs EUR/USD ≈ 1.1. Same axis would make EUR invisible

**Rejected alternatives**:

- Single Y-axis → rejected: JPY and EUR values differ by 100x, making one invisible
- Using broker rates → rejected: market rates are the standard reference

**Entities affected**: `currencies` (read)

**UI pages**: Currencies page (`/currencies`)

**Constraints**:

- Date range filtering applied if start_date/end_date provided
- Only currencies present in the `currencies` table are shown
