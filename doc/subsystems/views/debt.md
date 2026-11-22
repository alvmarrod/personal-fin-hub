# View: Debt (`/debt`)

**Source**: `frontend/src/routes/debt/+page.svelte`,
`lib/components/modals/Debt*Modal.svelte`.

Design record: `doc/plans/debt.md`. UC-58.

## Layout

```text
Debt                                              [+ Add debt]

[ Debt I owe: 138,000 € ]  [ Owed to me: 4,500 € ]

[ All ] [ I owe ] [ Owed to me ]          Status: [Active ▾]

Counterparty   Direction   Outstanding   Rate   Next payment   Progress   Status
Bank X         I owe       138,000 €     3.5%   01/12/2026     42%        Active
Ana            Owed to me    4,500 €     0%     —             60%        Active
```

## Data

- `GET /debt?direction=&status=` — the list, sorted by start date descending.
- `GET /debt/summary?display_currency=…` — payable and receivable totals,
  accrued interest, active counts and the next payment in each direction.
- `GET /debt/{id}` — terms, rates, payments and plan for the detail panel.
- The page follows the global display currency; each debt keeps its own currency
  and the summary converts the totals.

## Behaviour

- **Direction tabs**: All / I owe / Owed to me. The tab can be preselected with
  `/debt?direction=payable|receivable` (the dashboard links use it).
- **Status filter**: Active (default), Settled, Cancelled, All.
- **Summary tiles**: total outstanding per direction, accrued interest and the
  number of active debts. Amounts are masked in privacy mode.
- **Row**: opens the detail panel.
- **Detail panel**: terms, current rate, outstanding, accrued interest, total due,
  progress, rate history, payments with the five-part split, and the imported
  plan. Actions: Add payment, Change rate, Settle, Cancel, Import plan, Edit,
  Delete.

## Modals

- **Create/edit**: direction, counterparty (free text with autocomplete from
  previous names), description, currency, principal, start date, annual rate,
  term and maturity, installment mode (equal payment, equal principal,
  interest-only, manual), day count, rate-reset mode and review period, the
  optional cash movement at start (pocket + entity, or none), and the optional
  recurring payment (periodicity, entity, first date). Currency, principal,
  start date and rate are locked once the debt exists.
- **Payment**: date, entity pocket, amount, a principal-only toggle, and an
  optional exact split (principal, interest, fees, insurance, other). Without a
  split the server pays interest first; the split must add up to the amount.
- **Change rate**: effective date and annual rate.
- **Settle**: date, entity, the estimated payoff and an optional actual amount.
  A difference is stored as `settlement_adjustment`.
- **Cancel/delete**: a confirmation; cancel closes without a payment, delete
  removes the debt, its payments and their linked transactions.
- **Import plan**: one line per installment,
  `due_date, payment, principal, interest[, fees, insurance, other]`, separated by
  comma, semicolon or tab. The entries replace the future plan from the first date.

## Schedules

A debt may own one schedule (`schedules.debt_id`). The scheduler asks the debt
service for the amount and split at fire time, using the next plan entry when it
exists. Settling, cancelling or fully paying the debt stops the schedule. The
generic Schedules page shows the debt schedule with its labels; edit it from the
debt.

## Edge cases

| Case | Behaviour |
|---|---|
| 0% rate | Every payment is principal |
| Payment below accrued interest | Rejected; mark it principal-only or pay the interest |
| Payment above the balance | Rejected; use Settle |
| Settled debt | No new payments; the detail offers Edit and Delete |
| Delete a payment | The linked transaction is deleted; a settled debt reopens |
| Edit a debt transaction | The split and the balance are re-derived; no blocking |
| Foreign-currency debt | Allowed; totals convert at the latest rate |
| Privacy mode | Amounts masked; rates and dates visible |
| No debts | Empty state with the Add button |

## Out of scope

- Net worth: debt is kept outside the portfolio and the dashboard net position.
- Interest analytics in the Income page or tax reports.
- Automatic rate index and bank statement import.
