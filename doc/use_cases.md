# Use Cases

## Purpose

This document is the **source of truth** for how real-world operations map to the data model. It resolves modeling ambiguity: when the same user intent could be represented in multiple ways in the database, the use case defines which representation is correct and why.

If code diverges from use cases, **code gets fixed**.

## Scope

Covers all implemented and planned operations. Each use case describes:

- What the user or system does
- What data is created, modified, or read
- Why this modeling over alternatives
- Currency considerations (which fields, auto-fill behavior, constraints)

## Conventions

### Identification

- Format: `UC-XX` where XX is a zero-padded number
- Ordered by complexity (simple → complex)

### Branching Logic

- `IF condition THEN ... ELSE ...` for modeling that depends on context
- Each branch specifies what changes in the data model

### Currency Notation

- `currency` = asset's native denomination (what the asset is priced in)
- `payment_currency` = what the user actually pays/receives (may differ from currency). Informally called "account currency" in user-facing descriptions.
- `fx_rate` = broker-applied conversion rate (1 currency = X payment_currency)
- `display_currency` = user-selected currency for analytics aggregation
- `base_currency` = reference currency for the exchange rate chart (e.g., USD). Distinct from `display_currency`.
- Market reference rate = stored in `currencies` table, used for valuation

### Status Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Implemented and tested |
| 🔜 | Partially implemented (backend done, frontend pending) |
| 📋 | Planned but not implemented |

---

## Master Table

### Tier 1 — Foundation CRUD

[→ uc_1_foundation_crud.md](uc_1_foundation_crud.md)

| UC | Title | Status |
|----|-------|--------|
| UC-01 | Manage Entity | ✅ |
| UC-02 | Manage Market Asset | ✅ |
| UC-03 | Manage Portfolio Asset | ✅ |
| UC-04 | Record Price | ✅ |
| UC-05 | Manage Fiscal Exemption | ✅ |
| UC-45 | Record Manual Valuation | 🔜 |

### Tier 2 — Core Transactions

[→ uc_2_core_transactions.md](uc_2_core_transactions.md)

| UC | Title | Status |
|----|-------|--------|
| UC-06 | Record Income | ✅ |
| UC-07 | Record Money Out | ✅ |
| UC-08 | Record Investment Buy | ✅ |
| UC-09 | Record Investment Sell | ✅ |
| UC-10 | Record Dividend | ✅ |

### Tier 3 — Composite Transactions

[→ uc_3_composite_transactions.md](uc_3_composite_transactions.md)

| UC | Title | Status |
|----|-------|--------|
| UC-11 | Record Full Transaction | ✅ |
| UC-12 | Transfer Between Entities | ✅ |
| UC-13 | Batch Import Transactions | ✅ |

### Tier 4 — Schedules

[→ uc_4_schedules.md](uc_4_schedules.md)

| UC | Title | Status |
|----|-------|--------|
| UC-14 | Create Recurring Schedule | ✅ |
| UC-15 | Edit Schedule | ✅ |
| UC-16 | Delete Schedule | ✅ |
| UC-17 | Project Future Occurrences | ✅ |

### Tier 5 — Snapshots & Balance

[→ uc_5_snapshots_balance.md](uc_5_snapshots_balance.md)

| UC | Title | Status |
|----|-------|--------|
| UC-18 | Create Balance Snapshot | ✅ |
| UC-19 | Delete Balance Snapshot | ✅ |
| UC-20 | View Cash Balance | ✅ |

### Tier 6 — Currency

[→ uc_6_currency.md](uc_6_currency.md)

| UC | Title | Status |
|----|-------|--------|
| UC-21 | Sync Exchange Rates | ✅ |
| UC-22 | View Holdings by Currency | ✅ |
| UC-23 | View Exchange Rate History | ✅ |

### Tier 7 — Analytics Reads

[→ uc_7_analytics_reads.md](uc_7_analytics_reads.md)

| UC | Title | Status |
|----|-------|--------|
| UC-24 | View Dashboard Summary | ✅ |
| UC-25 | View Holdings with P&L | ✅ |
| UC-26 | View Asset Allocation | ✅ |
| UC-27 | View Cash Flow | ✅ |
| UC-28 | View Income by Source | ✅ |
| UC-29 | View Projected Income | ✅ |
| UC-30 | View Dividends | ✅ |
| UC-31 | View Fees & Taxes | ✅ |
| UC-32 | View Realized Gains (FIFO) | ✅ |
| UC-33 | View Historical Portfolio Value | ✅ |
| UC-34 | View Performance Summary | ✅ |
| UC-35 | View Transaction List | ✅ |
| UC-36 | List Income Transactions | ✅ |
| UC-37 | List Dividends | ✅ |

### Tier 8 — System-Initiated

[→ uc_8_system_initiated.md](uc_8_system_initiated.md)

| UC | Title | Status |
|----|-------|--------|
| UC-38 | Scheduler Fires Schedule | ✅ |
| UC-39 | Auto-Create Balance Adjustment | ✅ |
| UC-40 | Scheduler Startup Re-Registration | ✅ |
| UC-41 | Catch Up Missed Fires | ✅ |
| UC-46 | Scheduled Price Sync | ✅ |

### Tier 9 — Planned

[→ uc_9_planned.md](uc_9_planned.md)

| UC | Title | Status |
|----|-------|--------|
| UC-41 | Portfolio Rebalancing | 📋 |
| UC-42 | CSV Import | 📋 |
| UC-47 | Manage Fiscal Rules & Periods | ✅ |
| UC-48 | View Taxable P&L (Tax Page) | ✅ |
| UC-49 | Manage Tax Rates | ✅ |
| UC-50 | View Tax Owed (per fiscal year) | ✅ |
| UC-51 | Set Profile Default Ruleset | ✅ |
