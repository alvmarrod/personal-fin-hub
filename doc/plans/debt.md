# Plan — Debt (Payable and Receivable)

**Status**: design only, not implemented.
**Source**: planned `backend/services/debt_svc.py`, `backend/routes/debt.py`, `frontend/src/routes/debt/+page.svelte`.
**Depends on**: `transactions`, `schedules`, `entities` (cash pockets), `currencies`. UC-58.

## Purpose

Track money that is owed in both directions and the payments that move it:

- **Payable** — the profile owes money (loan, mortgage, family loan).
- **Receivable** — money is owed to the profile (a loan given to someone).

A debt can carry interest or not. Payments are real transactions, recurring payments
run through a schedule, and a debt can be settled early in one operation.

**Non-goals**

- No bank connection, no automatic statement import.
- No investment advice, no credit scoring, no refinancing or novation.
- No changes to `portfolio_assets`, asset classes, the investment strategy or the
  portfolio value. Debt is kept outside the investment portfolio.
- Not included in net worth in this stage (see Decisions log #24).

## Terms

| Term | Meaning |
|---|---|
| Principal | The original amount of the debt |
| Outstanding | Principal minus the principal parts already paid |
| Accrued interest | Interest built up since the last payment, not yet paid |
| Payment | One cash movement: principal + interest + fees + insurance + other |
| Plan | The expected amortisation table, usually the bank's own |
| Settlement | Paying all that remains to close the debt early |
| Cancel | Closing the debt without payment (written off or forgiven) |

Only the **principal** part reduces the outstanding balance. Interest is the cost of
the money. Fees, insurance and other charges do not touch either.

## Data model

Planned migration `034_debt`; all tables are profile-scoped.

```text
debts
  id                 INTEGER PK
  profile_id         INTEGER REFERENCES profiles(id)
  direction          TEXT CHECK IN ('payable', 'receivable')
  counterparty_name  TEXT NOT NULL
  description        TEXT
  currency           TEXT NOT NULL REFERENCES currencies(code)
  principal          REAL NOT NULL
  start_date         DATE NOT NULL
  term_months        INTEGER NULL
  maturity_date      DATE NULL
  installment_mode   TEXT CHECK IN ('equal_payment', 'equal_principal', 'interest_only', 'manual')
  installment_amount REAL NULL            -- equal_payment
  principal_per_installment REAL NULL      -- equal_principal
  day_count          TEXT CHECK IN ('monthly', 'actual_365', 'actual_360', 'thirty_360')
  rate_reset_mode    TEXT CHECK IN ('recalculate_installment', 'keep_installment')
  review_period_months INTEGER NULL       -- 1 | 3 | 6 | 12 for variable rates
  disbursement_mode  TEXT CHECK IN ('pocket', 'none')
  disbursement_entity_id INTEGER NULL REFERENCES entities(id)
  disbursement_date  DATE NULL
  status             TEXT CHECK IN ('active', 'settled', 'cancelled')
  settled_at         DATE NULL
  settled_amount     REAL NULL
  settlement_adjustment REAL NULL
  notes              TEXT
  created_at, updated_at

debt_rates
  id, profile_id, debt_id
  effective_from     DATE NOT NULL
  annual_rate        REAL NOT NULL CHECK (annual_rate BETWEEN 0 AND 100)
  created_at
  UNIQUE (debt_id, effective_from)

debt_plan_entries
  id, profile_id, debt_id
  period_no          INTEGER NOT NULL
  due_date           DATE NOT NULL
  payment_amount     REAL NOT NULL
  principal_amount   REAL NOT NULL
  interest_amount    REAL NOT NULL
  fees_amount        REAL NOT NULL DEFAULT 0
  insurance_amount   REAL NOT NULL DEFAULT 0
  other_amount       REAL NOT NULL DEFAULT 0
  imported_at        DATETIME NOT NULL
  UNIQUE (debt_id, due_date)

debt_payments
  id, profile_id, debt_id
  paid_at            DATE NOT NULL
  amount             REAL NOT NULL
  principal_amount   REAL NOT NULL DEFAULT 0
  interest_amount    REAL NOT NULL DEFAULT 0
  fees_amount        REAL NOT NULL DEFAULT 0
  insurance_amount   REAL NOT NULL DEFAULT 0
  other_amount       REAL NOT NULL DEFAULT 0
  kind               TEXT CHECK IN ('regular', 'extra', 'settlement')
  transaction_id     INTEGER NULL REFERENCES transactions(id)
  plan_entry_id      INTEGER NULL REFERENCES debt_plan_entries(id)
  notes              TEXT
  created_at

schedules.debt_id     INTEGER NULL REFERENCES debts(id)
```

**Derived, never stored** (calculated on request):

- outstanding principal = `principal − Σ debt_payments.principal_amount`
- accrued interest = interest from `debt_rates` over the unpaid period
- projected payoff date and interest total
- progress = principal paid / principal

A debt always has at least one `debt_rates` row. The create form takes the initial
annual rate and writes that first row; `0%` is valid.

## Interest model

### Rate schedule

Rates are effective-dated. A rate applies from its `effective_from` until the next
entry. A fixed-rate debt has one entry. A variable-rate debt adds entries when the
rate changes. The rate in effect on a date is the newest entry on or before it.

### Day count

Selectable per debt, because banks differ. The default is `monthly`.

| Day count | Interest for a period |
|---|---|
| `monthly` | `outstanding × rate/100 / 12` for a full month; a partial month uses `days_elapsed / days_in_month` |
| `actual_365` | `outstanding × rate/100 × actual_days / 365` |
| `actual_360` | `outstanding × rate/100 × actual_days / 360` |
| `thirty_360` | Every month counts 30 days, every year 360 |

For accrual across a rate change, split the period at each `effective_from` and add
the segments. Interest is simple, never compounded.

### Installment modes

| Mode | Amount per period |
|---|---|
| `equal_payment` | Fixed annuity: `A = P × m / (1 − (1+m)^−n)` with `m = rate/100/12` and `n` months left |
| `equal_principal` | Principal fixed (`principal_per_installment`); interest is added, so the payment falls over time |
| `interest_only` | Payment equals accrued interest; principal is repaid at maturity or by extra payments |
| `manual` | The user enters every payment amount |

The forecast is a projection. The actual payments are facts and always win.

### Rate resets

`review_period_months` (1, 3, 6, 12) marks when the rate is expected to be reviewed.
On a reset the user adds a new `debt_rates` entry, then:

- **`recalculate_installment`** (default): recompute the installment from the current
  outstanding and the remaining months, keeping `maturity_date`.
- **`keep_installment`**: keep the amount; a higher rate reduces the principal part
  and extends the payoff date. Rejected if the payment would not cover accrued
  interest (negative amortisation).

Future schedule and plan amounts are updated; past transactions and payments never
change.

### Payment allocation

1. Compute accrued interest to the payment date.
2. If the payment carries an explicit split, use it as given.
3. Otherwise, a principal-only payment sets interest, fees, insurance and other to 0.
4. Otherwise, interest is paid first, then the remainder goes to principal.

Validation:

- The components must add up to `amount`.
- `principal_amount` cannot exceed the outstanding principal.
- A regular payment smaller than accrued interest is rejected unless it is explicitly
  marked interest-only or partial.
- A payment that would close the debt is treated as a settlement.

## Plan table and import

`debt_plan_entries` mirrors the lender's amortisation table. It is optional.

- Import by pasting a table (date, payment, interest, principal, fees, insurance,
  other) or a CSV file.
- The next plan entry pre-fills the payment modal and supplies the amount when the
  schedule fires.
- After a rate reset, replace the future entries from a chosen date; keep the past
  for reference.
- The plan is reference data. Outstanding still comes from actual payments.
- With no plan, the preset mode computes the amounts and the projection.

## Cash movement at creation

The debt start can move cash, like a balance adjustment:

| `disbursement_mode` | Transaction |
|---|---|
| `pocket` | One transaction on the chosen entity: payable → cash in (`DEBT_IN`); receivable → cash out (`DEBT_OUT`) |
| `none` | No transaction; the money is outside tracked pockets or already recorded |

No pocket-to-pocket transfers. The counterparty is a name, not an entity pocket.

## Transactions and schedules

Two new transaction types:

| Type | Cash sign | Used for |
|---|---|---|
| `DEBT_IN` | + | Borrowed money received; repayment received on a receivable |
| `DEBT_OUT` | − | Money lent; repayment paid on a payable |

- They count in cash balances and cash flow, but not as income or expenses.
- Each payment creates one transaction in the debt currency and links it from
  `debt_payments.transaction_id`.
- Deleting a payment deletes its transaction when the app created it.

Schedules:

- Each debt owns one schedule (`schedules.debt_id`) that carries the cadence and the
  next due date.
- At fire time the debt supplies the amount and split, from the next plan entry when
  one exists, otherwise from the installment mode.
- The schedule stops when the debt is settled, cancelled, or reaches maturity.
- Manual extra payments do not edit the schedule; the next fire recalculates from
  the lower outstanding.

### Editable transactions

Debt-linked transactions are ordinary transactions and stay editable in the
generic transaction view. The tool provides, it does not force:

- An amount or date edit re-derives the payment split (interest first) and the
  outstanding balance.
- Deleting the transaction deletes its `debt_payments` row and re-derives the debt.
- Deleting a settlement payment reopens a settled debt (`settled → active`) and
  resyncs the schedule.
- Changing the type away from `DEBT_IN` / `DEBT_OUT`, or changing the currency,
  unlinks the payment; the user can add it again from `/debt`.
- The plan is a reference: the debt detail shows plan vs actual and flags a
  deviation, but never blocks a payment.

## Settlement

`POST /debt/{id}/settle` with a date:

1. Payoff = outstanding principal + accrued interest to that date.
2. The user may enter the actual amount paid (lender quote, penalty, discount).
3. Store the settlement payment (`kind = settlement`) and, when it differs,
   `settlement_adjustment = paid − (principal + interest)`. Positive is a cost,
   negative a discount.
4. Set `status = settled`, `settled_at`, `settled_amount`.
5. Stop the schedule.

`POST /debt/{id}/cancel` closes the debt with no payment. Unpaid accrued interest is
discarded with it.

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/debt` | List, filter by direction and status |
| `POST` | `/debt` | Create |
| `GET` | `/debt/{id}` | Terms, rates, payments, plan, derived values |
| `PUT` | `/debt/{id}` | Edit terms |
| `DELETE` | `/debt/{id}` | Delete the debt and its payments |
| `POST` | `/debt/{id}/payments` | Record a payment (with optional split) |
| `DELETE` | `/debt/{id}/payments/{payment_id}` | Undo a payment |
| `POST` | `/debt/{id}/rates` | Add a rate entry (effective date, rate) |
| `POST` | `/debt/{id}/settle` | Early payoff |
| `POST` | `/debt/{id}/cancel` | Write-off |
| `GET` | `/debt/{id}/plan` | Plan entries and projection |
| `PUT` | `/debt/{id}/plan` | Import or replace future plan entries |
| `GET` | `/debt/summary` | Totals by direction, next payments |
| `GET` | `/debt/counterparties` | Distinct names for autocomplete |

Money values in the payload are in the debt currency.

## Views

### `/debt`

Page name **Debt**, under a new sidebar section.

```text
Debt                                            [+ Add debt]

[ I owe: 142,300 € ]  [ Owed to me: 4,500 € ]

[ All ] [ I owe ] [ Owed to me ]        Status: [Active ▾]

Counterparty   Direction   Outstanding   Rate    Next payment   Progress   Status
Bank X         I owe       138,000 €     3.5%    01/12/2026     42%        Active
Ana            Owed to me    4,500 €     0%       —             60%        Active
```

- Summary tiles for both directions, converted to the display currency.
- Direction tabs and a status filter; active by default.
- Row opens a detail panel: terms, rate history, outstanding, accrued interest,
  projected payoff, payments table with the five-part split and the linked
  transaction, and the plan.
- Actions: Add payment, Change rate, Settle, Cancel, Edit, Delete.
- The generic Schedules page lists debt schedules with a link to `/debt`; the debt
  supplies the amount at fire time.

Modals:

- **Create/edit**: direction, counterparty with autocomplete, description, currency,
  principal, start date, rate (0 allowed), term/maturity, installment mode, day count,
  review period, payment cadence, cash movement (`pocket` + entity, or `none`).
- **Payment**: date, amount, optional split (principal, interest, fees, insurance,
  other), principal-only toggle, notes.
- **Change rate**: effective date, new rate, and whether to recalculate installments.
- **Settle**: date, computed payoff, optional actual amount, adjustment preview.
- **Cancel**: confirmation.

### Dashboard

Two separate cards, not one, and not part of net worth:

| Card | Content |
|---|---|
| **Debt I owe** | Outstanding total, interest accrued, active count, next payment |
| **Owed to me** | Outstanding total, active count, next expected payment |

- Converted at the latest rate, like the other dashboard cards; native amounts in the
  tooltip.
- Each card navigates to `/debt?direction=payable|receivable`.
- Empty state with an **Add debt** button.
- Privacy mode masks amounts and keeps rates and dates visible.

### Sidebar

```text
Overview      Dashboard
Activity      Transactions, Transfer
Tracking      Income, Debt
Investments   Portfolio assets, Dividends, Performance, Strategy
Analysis      Market cycle, Tax, Cash flow
Setup         ...
System        ...
```

## Cross-cutting

- **Profiles**: new tables in `PROFILE_TABLES` and the profile-delete order; one
  profile never sees another profile's debts.
- **Privacy**: amounts are masked, rates and dates stay visible.
- **i18n**: en-US, es-ES, ja-JP keys for the page, modals and sidebar section.
- **Currency**: one currency per debt. Aggregate totals convert at the latest rate;
  a historical series, when added, converts at each date's rate.
- **Time zones**: `start_date`, payment dates and plan dates are profile-tz calendar
  dates.
- **Backups**: the new tables are part of the profile data and the backup/restore
  cycle.

## Edge cases

| Case | Behaviour |
|---|---|
| 0% interest | Every payment is principal |
| Payment below accrued interest | Rejected unless marked interest-only/partial |
| Payment above outstanding + accrued | Rejected; use Settle to close |
| Rate change on the same date as a payment | New rate applies from that date onward |
| Several rate entries on one day | Rejected; one rate per effective date |
| Plan missing | Installment mode supplies the amounts |
| Plan covers past dates | Ignored for previous payments; kept for reference |
| Schedule fires after settlement | Impossible; the schedule is stopped |
| Debt with no maturity | `keep_installment`; payoff date floats |
| Counterparty renamed | Free text; edit the debt |
| Foreign-currency debt | Allowed; totals converted for aggregates |
| Delete a debt | Payments and transactions created by the app are removed |
| Cancel with unpaid interest | Interest discarded; debt closed |

## Test plan

- Interest: each day count, across rate changes, partial periods and 0%.
- Allocation: computed split, explicit split, principal-only, rejection cases.
- Installments: annuity, equal principal, interest-only, manual.
- Resets: recalculate with fixed maturity; keep installment; negative-amortisation guard.
- Plan: import, replace future entries, prefill, drive a scheduled payment.
- Cash movement: `pocket` creates the right transaction and sign; `none` creates none.
- Settlement: computed payoff, override and adjustment; schedule stopped.
- Transactions: debt types excluded from income/expense, included in cash.
- Profile isolation, privacy, empty states, locale keys.

## Delivery

1. Docs (this file, UC-58, roadmap).
2. Backend: migration `034_debt`, models, queries, `debt_svc`, routes, schedule hook,
   tests.
3. Frontend: `/debt` page and modals, dashboard cards, sidebar Tracking section,
   i18n, tutorial, tests.
4. Docs: view spec, API endpoints, database, UI, changelogs; version bump per
   component.

## Future extensions

- Debt interest in the Income page and tax reports.
- Net worth including debt, if the product direction changes (decision #24 defers it).
- Automatic rate index (EURIBOR and similar).
- CSV statement import that matches debt payments (ties into UC-42).
- Collateral, refinancing and novation.

## Decisions log

| # | Decision | Choice |
|---|---|---|
| 1 | Scope | Both directions: payable and receivable |
| 2 | Counterparty | Free text, with autocomplete from previous names |
| 3 | Interest | Always present; `0%` is the no-interest case |
| 4 | Rates | Effective-dated schedule; fixed is one entry |
| 5 | Day count | Selectable; `monthly` default |
| 6 | Installment modes | Equal payment, equal principal, interest-only, manual |
| 7 | Rate reset | Recalculate installment with fixed maturity by default; keep-installment optional with a negative-amortisation guard |
| 8 | Payment components | Principal, interest, fees, insurance, other |
| 9 | Split | Computed by default; explicit split overrides; principal-only option |
| 10 | Allocation order | Interest first, then principal |
| 11 | Plan table | Included; paste/CSV import; drives scheduled amounts; future entries replaceable |
| 12 | Cash movement | `pocket` or `none`; no pocket-to-pocket transfer |
| 13 | Transaction types | New `DEBT_IN` and `DEBT_OUT`; not income or expenses |
| 14 | Schedules | One per debt, owned by the debt |
| 15 | Settlement | Computed payoff, optional override stored as `settlement_adjustment` |
| 16 | Cancel | Close without payment, discarding unpaid interest |
| 17 | Dashboard | Two separate cards; debt stays out of net worth |
| 18 | Placement | New Tracking section; Income moves into it |
| 19 | Page | Name “Debt”, route `/debt` |
| 20 | Privacy | Amounts masked; rates and dates visible |
| 21 | Currency | One currency per debt; aggregates converted at the latest rate |
| 22 | Balances | Calculated on demand, never stored |
| 23 | Interest analytics | Debt page only in this stage |
| 24 | Net worth | Not included in this stage |
| 25 | Linked transactions | Editable; amount/date edits re-derive the split, deletion re-derives, settlement deletion reopens |
| 26 | Plan drift | Shown as plan vs actual; never blocks a payment |
