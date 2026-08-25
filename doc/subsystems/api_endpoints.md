# Subsystem: API Endpoints

## Resources Overview

| Resource | Endpoints | Notes |
|----------|-----------|-------|
| **Market Assets** | GET, POST, PUT, DELETE `/market-assets` | Market data from external API |
| **Portfolio Assets** | GET, POST, PUT, DELETE `/portfolio-assets` | User portfolio positions |
| **Portfolio Manual Values** | GET, POST `/portfolio-assets/{id}/manual-values`, DELETE `/portfolio-assets/{id}/manual-values/{value_id}` | Snapshot ledger for manual-tracked assets (UC-45). `PUT /portfolio-assets/{id}` with a manual value also upserts into this ledger |
| **Transactions** | GET, POST, PUT, DELETE `/transactions` | Core resource |
| `/transactions/full` | POST | Create transaction with fees and taxes |
| `/transactions/{id}/full` | GET | Get transaction with fees and taxes |
| `/transactions/batch` | POST | Bulk create transactions |
| **Transaction Fees** | GET, POST, PUT, DELETE `/transaction-fees` | 1:N with transactions |
| **Transaction Taxes** | GET, POST, PUT, DELETE `/transaction-taxes` | 1:N with transactions (including withholding) |
| **Entities** | GET, POST, PUT, DELETE `/entities` | Brokers, exchanges, counterparties |
| **Fiscal Exemptions** | GET, POST, PUT, DELETE `/fiscal-exemptions` | Tax exemption types |
| **Fiscal Periods** | GET, POST, PUT, DELETE `/fiscal-periods` | Rule-per-date-range assignment (UC-47); rejects overlapping periods |
| **Tax Rates** | GET, POST, PUT, DELETE `/tax-rates` | Per-ruleset/category/year bracket CRUD (UC-49); supports flat and progressive rates |
| **Currencies** | GET `/currencies`, GET `/currencies/rates`, GET `/currencies/rates/{code}/{base_code}`, GET `/currencies/rates/{code}/{base_code}/history`, POST `/currencies/sync`, GET `/currencies/holdings`, GET `/currencies/rate-chart` | Read-only + sync. No CRUD UI exposed. |
| **Prices** | GET, POST, PUT, DELETE `/prices` | Daily/timestamped market prices |
| **Market Sync** | POST `/market/sync-prices` | Bulk price fetch from external API (paced + freshness skip) |
| **Schedules** | GET, POST, PUT, DELETE `/schedules` | Recurring transactions |
| **Balance Snapshots** | GET, POST, PUT, DELETE `/balance-snapshots` | Cash balance anchor for (entity, currency) pairs |
| **Profiles** | GET, POST `/profiles`, GET, PATCH, DELETE `/profiles/{id}`, POST `/profiles/{id}/unlock` | Multitenancy; the active profile id is sent via the `X-Profile-ID` header on every other request |
| **Updates** | GET `/updates` | Public update-availability check against GitHub Releases (no profile required) |

## Profiles Endpoints

Profile endpoints are public — they never require the `X-Profile-ID` header. All other `/api/v1` endpoints require the active profile id via the `X-Profile-ID` request header; a request without it (or with an unknown id) is rejected with `401`/`404`. Profile-scoping applies to every route→service→query chain over the 10 ownership tables.

### 1. List Profiles

`GET /profiles`

Returns all profiles without password hashes.

### 2. Create Profile

`POST /profiles`

**Payload:**

```json
{
  "name": "Family",
  "password": null
}
```

- `name` — required, unique (`409` on duplicate or empty).
- `password` — optional; hashed with stdlib `pbkdf2_hmac`. `null` = passwordless profile.

### 3. Get Profile

`GET /profiles/{profile_id}`

Returns a single profile (404 if unknown).

### 4. Rename Profile

`PATCH /profiles/{profile_id}`

**Payload:**

```json
{ "name": "Household" }
```

404 if unknown; 409 on duplicate/empty name.

### 5. Unlock Profile

`POST /profiles/{profile_id}/unlock`

**Payload:**

```json
{ "password": "secret" }
```

Verifies the password server-side. 404 if unknown; 401 on wrong password. Passwordless profiles accept any (or no) password. On success returns the profile. This is identification/unlock UX only — **not** an API-level auth barrier (see architecture_overview).

### 6. Delete Profile

`DELETE /profiles/{profile_id}`

Deletes the profile and its own rows across the 10 ownership tables (child-first for FK order). Shared market reference data (`currencies`, `market_assets`, `prices`, `stock_splits`, `scheduler_state`) and other profiles' rows are never touched. 404 if unknown; **409 if it is the last remaining profile**.

## Update Availability Endpoint

### 1. Check for Updates

`GET /updates`

Public endpoint (no `X-Profile-ID` required). Reports whether a newer release exists for the backend and/or frontend in the public GitHub repository (`update_check.repo`, default `alvmarrod/personal-fin-hub`). Releases are listed and filtered by `tag_name` prefix (`backend/` vs `frontend/`); the greatest semantic version per prefix is the "latest". The GitHub global `releases/latest` endpoint is intentionally not used — it points to a single release and cannot represent both independently-versioned components.

**Query:**

| Param | Type | Meaning |
|---|---|---|
| `frontend_version` | string, optional | The frontend's own version, self-reported by the UI (baked from `package.json` at build time). Omitted → the `frontend` field is `null`. |

**Response (200):**

```json
{
  "enabled": true,
  "backend":  { "current": "0.12.0", "latest": "0.12.0", "outdated": false, "url": "https://github.com/alvmarrod/personal-fin-hub/releases/tag/backend/v0.12.0" },
  "frontend": { "current": "0.10.0", "latest": "0.10.0", "outdated": false, "url": "https://github.com/alvmarrod/personal-fin-hub/releases/tag/frontend/v0.10.0" },
  "checked_at": "2026-08-14T00:00:00+00:00"
}
```

**Behaviour:**

- `backend.current` is read from `pyproject.toml` (`project.version`).
- `outdated` is `true` only when the latest release is strictly greater than the current version.
- Results are cached server-side for `update_check.cache_seconds` (default 3600); repeat calls within the TTL do not hit GitHub.
- **Fail-open**: on a GitHub transport/HTTP error the endpoint returns `{ "enabled": true, "error": "unavailable", "backend": null, "frontend": null, "checked_at": ... }` — never a false `outdated`.
- When `update_check.enabled` is false: `{ "enabled": false }`.

## Transactional Endpoints

### 1. Create Full Transaction

`POST /transactions/full`

Creates transaction with fees and taxes atomically.

> **Reconciliation:** a transaction may be dated at any point in time, including before the latest snapshot for its `(entity_id, currency)` pair. Cash-impacting changes are reconciled via the Tier 5 Reconciliation Model (a later snapshot's `BALANCE_ADJUSTMENT` is refreshed; a spend may inject inferred cash — the inject/debit choice is persisted as `cash_handling`, and created injections attach to the spend via `balance_adjustment_links`). Fees and taxes are balance-neutral and require no reconciliation.

**Payload:**

```json
{
  "transaction": {
    "portfolio_asset_id": 1,
    "quantity": 10,
    "unit_price": 100.5,
    "currency": "USD",
    "timestamp": "2025-09-17T09:00:00Z",
    "type": "INVESTMENT_BUY",
    "payment_currency": "JPY",
    "fx_rate": 150.5
  },
  "fees": [
    {
      "fee_type": "BROKER",
      "nature": "PERCENTAGE",
      "fixed_amount": 0,
      "percentage": 0.05,
      "currency": "USD"
    }
  ],
  "taxes": [
    {
      "tax_type": "STAMP_DUTY",
      "tax_rate": 0.1,
      "tax_amount": 1.0,
      "currency": "USD"
    }
  ]
}
```text

### 2. Create Dividend Transaction

`POST /transactions/full`

Withholding taxes linked to dividend transaction.

**Payload:**

```json
{
  "transaction": {
    "portfolio_asset_id": 1,
    "quantity": 100,
    "unit_price": 0.25,
    "currency": "USD",
    "timestamp": "2025-09-17T09:00:00Z",
    "type": "INCOME",
    "income_category": "dividends",
    "dividend_type": "regular",
    "record_date": "2025-09-01",
    "payment_date": "2025-09-15",
    "gross_amount": 25.00,
    "dividend_currency": "USD",
    "dividend_payment_currency": "JPY",
    "dividend_fx_rate": 150.5
  },
  "taxes": [
    {
      "tax_type": "WITHHOLDING",
      "tax_rate": 15,
      "tax_amount": 3.75,
      "currency": "USD"
    }
  ]
}
```text

### 3. Transfer Between Entities

`POST /transfers`

**Payload:**

```json
{
  "from_entity_id": 1,
  "to_entity_id": 2,
  "amount": 1000,
  "currency": "EUR",
  "timestamp": "2025-09-17T10:00:00Z",
  "fees": [...]
}
```text

**Response (201):**

```json
{
  "from_transaction": { "id": 101, "type": "TRANSFER_OUT", "total_value": 1000.0, ... },
  "to_transaction": { "id": 102, "type": "TRANSFER_IN", "total_value": 1000.0, ... },
  "fees": [{ "id": 1, "fee_type": "BROKER", "fixed_amount": 5.0, ... }]
}
```text

> **Note:** Cross-currency transfers (different currencies for OUT and IN legs) are documented in UC-12 but not yet implemented. The current implementation uses a single `currency` for both legs.

### 4. Batch Import

`POST /transactions/batch`

Creates multiple transactions atomically. All succeed or all roll back.

**Payload:**

```json
{
  "transactions": [
    {
      "timestamp": "2025-09-17T10:00:00Z",
      "type": "INCOME",
      "entity_id": 1,
      "currency": "EUR",
      "total_value": 1000.0
    },
    {
      "timestamp": "2025-09-17T10:00:00Z",
      "type": "INVESTMENT_BUY",
      "entity_id": 1,
      "portfolio_asset_id": 5,
      "currency": "EUR",
      "quantity": 10,
      "unit_price": 50.0
    }
  ]
}
```text

**Response (201):**

```json
{
  "transactions": [
    { "id": 101, "total_value": 1000.0, ... },
    { "id": 102, "total_value": 500.0, ... }
  ]
}
```text

### 5. Schedule with Initial Transaction

`POST /schedules/full`

Creates a schedule atomically. The schedule is self-contained: it embeds `total_value`, `currency`, `entity_id`, `type`, and `notes` directly. When the APScheduler runtime fires, it builds a new transaction from these embedded fields.

> **Reconciliation:** a schedule's `start_date` may precede existing snapshots; when it fires, the materialized transaction follows the Tier 5 Reconciliation Model.

**Payload:**

```json
{
  "schedule": {
    "description": "Monthly DCA",
    "start_date": "2025-01-01",
    "periodicity_type": "MONTHLY",
    "entity_id": 1,
    "currency": "USD",
    "type": "INVESTMENT_BUY",
    "total_value": 500.0,
    "income_category": null,
    "notes": "Monthly investment"
  }
}
```text

**Response (201):**

```json
{
  "schedule": {
    "id": 1,
    "description": "Monthly DCA",
    "start_date": "2025-01-01",
    "end_date": null,
    "periodicity_type": "MONTHLY",
    "custom_cron": null,
    "entity_id": 1,
    "currency": "USD",
    "type": "INVESTMENT_BUY",
    "total_value": 500.0,
    "notes": "Monthly investment"
  },
  "transaction": {
    "id": 101,
    "timestamp": "2025-01-01T00:00:00Z",
    "type": "INVESTMENT_BUY",
    "entity_id": 1,
    "currency": "USD",
    "total_value": 500.0,
    "notes": "Monthly investment",
    ...
  }
}
```text

> **Note:** `transaction` is only returned if `start_date` is today. Otherwise it is `null`.

### 6. Create Balance Snapshot

`POST /balance-snapshots`

Creates a balance snapshot that anchors the cash balance of an `(entity_id, currency)` pair to a known absolute value at a point in time. The snapshot's `amount` is the target balance; the system reconciles it with a signed `BALANCE_ADJUSTMENT` (Tier 5 Reconciliation Model), including for the first snapshot of a pair. All transactions with `timestamp > snapshot.timestamp` accumulate on top of this base.

**Payload:**

```json
{
  "entity_id": 1,
  "currency": "EUR",
  "amount": 5000.0,
  "timestamp": "2025-01-01T00:00:00Z",
  "notes": "Initial balance at account opening"
}
```text

**Pre-checks**

- `entity_id` must exist (not soft-deleted).
- `currency` must exist.
- No existing transaction for the same pair may have `timestamp >= snapshot.timestamp` (409 if violated).
- No existing schedule for the same pair may have `start_date <= snapshot.timestamp` (409 if violated).

**Response (201):**

```json
{
  "id": 1,
  "entity_id": 1,
  "currency": "EUR",
  "amount": 5000.0,
  "timestamp": "2025-01-01T00:00:00Z",
  "notes": "Initial balance at account opening"
}
```text

### 7. Entity Endpoints

`GET /entities` — List all non-deleted entities
`GET /entities/{entity_id}` — Get single entity by ID
`GET /entities/{entity_id}/dependents` — Check if entity has dependent records

**Entity Model:**

```json
{
  "id": "integer",
  "name": "string",
  "entity_type": "enum [BROKER, BANK, EMPLOYER, EXCHANGE, OTHER]",
  "country": "string | null",
  "description": "string | null"
}
```text

**Dependents Response:**

```json
{
  "has_transactions": "boolean",
  "has_balance_snapshots": "boolean",
  "has_schedules": "boolean"
}
```text

**Notes:**

- All entity queries exclude soft-deleted rows (`deleted_at IS NULL`).
- The `dependents` endpoint is used by the UI to show a warning icon when delete should be blocked.
- Entity soft-delete (DELETE `/entities/{id}`) blocks if any of these flags is true (returns 409).

---

### 8. Market Sync

`POST /market/sync-prices`

Fetches current prices and OHLCV history for active auto-tracked portfolio assets from the external Market API and stores them in `prices`. Query parameters control pacing and freshness:

| Param | Type | Default | Meaning |
|---|---|---|---|
| `full` | bool | `false` | `true` = fetch every auto-tracked symbol; `false` = skip symbols fetched < `max_age_hours` ago |
| `pace` | float | `2` | Seconds to sleep between symbol requests (avoid provider throttling) |
| `max_age_hours` | float | `1` | Freshness skip window (interactive syncs only) |

Behaviour:

- `tracking_mode = manual` assets are always skipped.
- `last_synced_at` (per `market_assets`) is updated only on success; failed symbols are retried next run.
- **Single-flight**: at most one sync runs at a time; concurrent callers are rejected/short-circuited.
- On an open circuit it returns `{ "synced": 0, "circuit_open": true, "skipped": [...] }` without contacting the API.

Response: `{ "synced": <count>, "results": [{ "market_code", "price" | "error" }] }`.

---

## Models

### Profile

```json
{
  "id": "integer",
  "name": "string",
  "has_password": "boolean",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

`password_hash` is never returned by the API.

### MarketAsset

```json
{
  "market_code": "string",
  "ticker": "string | null",
  "asset_type": "enum [STOCK, ETF, ETC, FUND, INDEX FUND, CURRENCY, CRYPTO, OTHER]",
  "asset_class": "enum [FI, VI, corp FI, Sovereign FI, mix FI, REIT, Gold, Monetary] | null",
  "currency_code": "string",
  "name": "string",
  "description": "string | null",
  "exchange": "string | null"
}
```text

### PortfolioAsset

```json
{
  "id": "integer",
  "market_code": "string",
  "distribution_type": "enum [accumulation, distribution, N/A] | null",
  "dca_status": "enum [ongoing, paused, closed] | null",
  "layer": "enum [core, reserve, satellite] | null",
  "tactic": "boolean",
  "desired_weight": "decimal | null",
  "ter": "decimal | null",
  "tracking_mode": "enum [auto, manual]",
  "current_value_manual": "decimal | null",
  "is_active": "boolean",
  "closing_date": "date | null",
  "notes": "string | null"
}
```text

> **Manual-tracked assets** (`tracking_mode = manual`): `current_value_manual` writes are transparently upserted into the `manual_values` ledger (UC-45). `current_value_manual` in responses reflects the latest ledger entry for manual assets; the raw legacy column remains a fallback only.

### ManualValue

```json
{
  "id": "integer",
  "portfolio_asset_id": "integer",
  "value": "decimal",
  "effective_date": "date",
  "recorded_at": "datetime",
  "notes": "string | null"
}
```text

### Transaction

```json
{
  "id": "integer",
  "portfolio_asset_id": "integer | null",
  "entity_id": "integer",
  "timestamp": "datetime",
  "type": "enum [INCOME, MONEY_OUT, INVESTMENT_BUY, INVESTMENT_SELL, TRANSFER, TRANSFER_IN, TRANSFER_OUT, BALANCE_ADJUSTMENT]",
  "investment_transaction_category": "enum [NORMAL, DCA, REBALANCE] | null",
  "income_category": "enum [salary, other, dividends, interest, cashback] | null",
  "quantity": "decimal | null",
  "unit_price": "decimal | null",
  "currency": "string",
  "total_value": "decimal",
  "gross_amount": "decimal | null",
  "net_amount": "decimal | null",
  "payment_currency": "string | null",
  "fx_rate": "decimal | null",
  "settlement_date": "date | null",
  "fiscal_exemption_id": "integer | null",
  "dividend_type": "enum [regular, special, qualified] | null",
  "record_date": "date | null",
  "payment_date": "date | null",
  "dividend_currency": "string | null",
  "dividend_payment_currency": "string | null",
  "dividend_fx_rate": "decimal | null",
  "notes": "string | null",
  "balance_snapshot_id": "integer | null",
  "cash_handling": "enum [inject, debit] | null",
  "cash_handling_effective": "enum [inject, debit] | null (spends only: explicit value, else Auto resolved against anchoring)",
  "attached_transaction_ids": "integer[] | null"
}
```text

### TransactionFee

```json
{
  "id": "integer",
  "transaction_id": "integer",
  "fee_type": "enum [BROKER, FX, PLATFORM, OTHER]",
  "nature": "enum [FIXED, PERCENTAGE, BOTH, MIN]",
  "fixed_amount": "decimal",
  "percentage": "decimal",
  "currency": "string"
}
```text

### TransactionTax

```json
{
  "id": "integer",
  "transaction_id": "integer",
  "tax_type": "string (e.g., WITHHOLDING, STAMP_DUTY, VAT, CAPITAL_GAINS)",
  "tax_rate": "decimal | null",
  "tax_amount": "decimal",
  "currency": "string"
}
```text

### Entity

```json
{
  "id": "integer",
  "name": "string",
  "entity_type": "enum [BROKER, BANK, EMPLOYER, EXCHANGE, OTHER]",
  "country": "string | null",
  "description": "string | null"
}
```text

### FiscalExemption

```json
{
  "id": "integer",
  "exemption_type": "string (e.g., NISA, ISA, 401k, Pension)",
  "description": "string | null",
  "exemption_amount": "decimal",
  "exemption_rate": "decimal (100 = 100%)",
  "exemption_rate_limit": "decimal | null"
}
```text

### TaxRate

```json
{
  "id": "integer",
  "ruleset_key": "string (spain, japan, default, latest, none)",
  "category": "string (capital_gains, dividends)",
  "from_amount": "decimal (lower bound of bracket, default 0)",
  "to_amount": "decimal | null (null = unbounded top bracket)",
  "rate": "decimal (fraction, e.g. 0.19 = 19%)",
  "year_start": "integer | null (null = default/fallback for all years)"
}
```

### TaxablePnlItem

```json
{
  "kind": "string (sell, dividend)",
  "transaction_id": "integer",
  "instrument": "string | null (ticker/name)",
  "date": "date",
  "taxable_amount": "decimal (post-exemption, display currency)",
  "rule": "string (frozen fiscal_rule for sells; resolved ruleset for dividends)",
  "tax_owed": "decimal | null (computed from brackets)",
  "confirmed_tax": "decimal | null (from transaction_taxes)",
  "source": "string (computed, confirmed)"
}
```

### Schedule

```json
{
  "id": "integer",
  "description": "string",
  "start_date": "date",
  "end_date": "date | null",
  "periodicity_type": "enum [ONE_OFF, DAILY, WEEKLY, MONTHLY, QUARTERLY, ANNUALLY, CUSTOM]",
  "custom_cron": "string | null",
  "linked_transaction_id": "integer | null",
  "entity_id": "integer | null",
  "currency": "string | null",
  "type": "enum [INCOME, MONEY_OUT, INVESTMENT_BUY, INVESTMENT_SELL, TRANSFER, TRANSFER_IN, TRANSFER_OUT, BALANCE_ADJUSTMENT] | null",
  "income_category": "enum [salary, other, dividends, interest, cashback] | null",
  "total_value": "number | null",
  "notes": "string | null"
}
```text

### BalanceSnapshot

```json
{
  "id": "integer",
  "entity_id": "integer",
  "currency": "string",
  "amount": "number",
  "timestamp": "datetime",
  "notes": "string | null"
}
```text

## Implementation Status

- **Profiles** — `GET/POST /profiles`, `GET/PATCH/DELETE /profiles/{id}`, `POST /profiles/{id}/unlock` — **implemented** (110 tests across `test_profiles.py` + `test_profile_scoping.py` + `test_profile_isolation.py`); profile scoping via `X-Profile-ID` applies to all ownership endpoints
- **All CRUD endpoints** under `/api/v1` (entities, market_assets, portfolio_assets, fiscal_exemptions, fiscal_periods, tax_rates, transactions, transaction_fees, transaction_taxes, prices, schedules, balance_snapshots) — **implemented**
- **Portfolio manual valuations** — `GET/POST /portfolio-assets/{id}/manual-values`, `DELETE /portfolio-assets/{id}/manual-values/{value_id}` — backend **implemented**; frontend history UI **pending** (UC-45)
- **Currencies**: Read-only + sync endpoints (no CRUD UI) — **implemented**
- **Composite endpoints:**
  - `POST /transactions/full` — implemented (7 tests)
  - `POST /transfers` — implemented (15 tests)
  - `POST /transactions/batch` — implemented (7 tests)
  - `POST /schedules/full` — implemented (6 tests)
- **Scheduler (APScheduler):** implemented (18 tests) — background job runner at app startup, auto-sync on schedule CRUD, materializes transactions from schedule embedded fields

### Analytics Endpoints

- `GET /analytics/dashboard` — Dashboard summary
- `GET /analytics/holdings` — Holdings with P&L
- `GET /analytics/allocation?dimension=layer|asset_type|currency|asset_class|entity` — Allocation grouped by dimension
- `GET /analytics/cash-flow?group_by=&start_date=&end_date=` — Cash flow analysis
- `GET /analytics/dividends?start_date=&end_date=&display_currency=` — Dividend income grouped by asset. Lines carry native-currency totals plus `count`; when `display_currency` is provided, each line additionally carries `total_dividends_display` (per-asset sum converted at each payment's transaction-date rate, §16.4), which powers the Dividends page's "Total Dividends" card, distribution chart, and table "Amount" column.
- `GET /analytics/fees-taxes?start_date=&end_date=` — Fee and tax totals
- `GET /analytics/performance?display_currency=&locale=` — Performance summary (all amounts converted to `display_currency` when provided; defaults to `USD`). Realized P&L is converted per sell via its frozen `fiscal_rule` snapshot (period-based); `locale` (e.g. `es-ES`) drives the fallback rule for period-less sells (`es` → `spain`, `ja` → `japan`, else `default`). Response includes `rule_key`, `rate_fallbacks` (closest-in-time / no-rate fallback flags, §16.4), and `realized_pl_pct` — realized P&L as a percentage of the display-currency cost basis of the sold lots, converted per sale under its frozen rule via `ConvertedSale.cost_basis_display` (§11.3; `0.0` when nothing sold). Also returns investment income: `total_dividends`, `dividend_yield_pct` (§14.3, ÷ invested historic) and `total_interest`, each payment converted at its own transaction-date rate (fallback scopes `dividends`/`interest`). `total_return` = unrealized + realized trading + dividends (interest excluded); see §6 performance variant.
- `GET /analytics/realized-gains` — Per-asset realized gains (native FIFO, no conversion). Includes buys/sells of deactivated portfolio assets.
- `GET /analytics/taxable-pnl-extended?display_currency=&locale=&ruleset=` — Extended taxable P&L: same fiscal-year grouping as `/analytics/taxable-pnl` plus per-line-item detail (`items[]` with quantity, proceeds, cost basis, native/display amounts, per-item tax) and a per-category tax breakdown per year. Powers the Tax page's expandable rows.
- `GET /analytics/taxable-pnl?display_currency=&locale=&ruleset=` — Taxable P&L grouped per fiscal year (realized gains + dividends, exemptions applied). `ruleset` defaults to the locale-derived rule and also drives the fiscal-year start (§17). Extended response includes `tax_owed` (computed from ruleset brackets, §17.9), `confirmed_tax` (from `transaction_taxes`, §17.10), `combined_base` (non-null when categories share a progressive bracket), `items[]` (per-item detail with kind, instrument, date, taxable_amount, rule, tax_owed, confirmed_tax, source), and `default_ruleset` (locale-inferred or profile override).
- `GET /analytics/historical?start_date=&end_date=&interval=` — Historical portfolio value
- `GET /analytics/holdings-by-entity` — Cross-tabulation entity × asset_class

All analytics endpoints implemented and tested (141 tests in `test_analytics.py`, plus taxable-P&L suites).

### Currency Analytics Endpoints

- `GET /currencies/holdings?start_date=&end_date=&display_currency=` — Historical holdings by currency, converted to display currency. Returns time series with per-currency breakdown and latest raw values.
- `GET /currencies/rate-chart?base_currency=&start_date=&end_date=` — Exchange rate datasets for charting. Applies JPY special handling (right Y-axis, inverted values).

Both endpoints implemented and tested (10 tests).
