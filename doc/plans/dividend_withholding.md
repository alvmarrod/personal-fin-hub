# Dividend withholding and gross/net triangulation — assessment

<!-- issue: dividend-tax-model / status: assessment / area: fiscal, reporting, transaction forms -->

This document captures an issue found while reviewing the modernized dividend UI.
It records the current model, the constraints the product wants, and where the two
conflict. It does **not** propose a solution. It is the shared baseline for the
follow-up design decision(s).

## 1. How this surfaced

The modern dividend UX (UC-10: two-leg dividend with `gross`, `net`,
`dividend_currency`, `dividend_payment_currency`, dividend FX, and exemptions) gave the
form four amount inputs and three currency inputs with no defined relationship between
them:

- Amount (required)
- Gross Amount (optional)
- Net Amount (optional)
- plus Dividend Currency / Payment Currency / FX Rate

A user who must record a dividend the way a broker states it — a declared gross, a
withholding, a received net — cannot tell what "Amount" means, or how "Amount" relates
to "Gross" and "Net". Cross-currency dividends make the ambiguity worse: the reports,
yield, and tax pages all read only one field, and none of the other three participates.

## 2. The problem in one sentence

For dividends, **Amount** (`total_value`) is the only field that any report reads, but
its gross/net/tax meaning is nowhere defined, and the fields that *would* define it
(`gross_amount`, `net_amount`, and the `WITHHOLDING` tax rows) are persisted but never
read by the reports.

## 3. Current model (verified against source)

### 3.1 The one authoritative number: `total_value`

`total_value` is:

- the required "Amount" field, mapped from the form's `Amount` input
  (`AddTransactionModal.svelte:421`, `EditTransactionModal.svelte`; model candidate in
  `TransactionCreate.total_value`, `backend/models/models.py:253`);
- the **only** amount consumed by reports:
  - Dashboard `total_dividends` — `doc/calculations.md` §16.6
    (`backend/services/analytics_svc.py` `get_dashboard` → `total_dividends += total_value`)
  - Dividend yield — §16.6 (as % of all-time invested)
  - Performance summary `total_dividends`, converted at payment-date rate — §16.6
  - Dividends report "Amount" column
  - Tax page — §17.3 `dividend_taxable = total_value × rate(currency → display, payment_date)`
    (`backend/services/pnl_rules.py` `dividend_taxable`)

So `total_value` is simultaneously the **gross dividend base** for the tax page and the
**dividend received** for the yield/performance/dashboard cards. The app has no second
number to separate "declared/gross" from "received/net".

### 3.2 The amount fields that do nothing today

- `gross_amount` — optional, dividend path. Read by nothing.
- `net_amount` — optional, dividend path. Read by nothing.
- `transaction_taxes` rows (`tax_type='WITHHOLDING'`) — never written by the dividend
  form. The form's multi-row Taxes editor is gated to investments only
  (`AddTransactionModal.svelte`, `isInvestmentType` gate at the Fees/Taxes sections;
  same in `EditTransactionModal.svelte` and `EditTransactionModal.svelte`), so a
  dividend never emits a `WITHHOLDING` row.

### 3.3 What the tax page expects but never receives

§17.4 (`doc/calculations.md`) defines an exemption/credit path that reduces a taxable
base. For a dividend with foreign withholding (e.g. Japan 20.315%, a US 15% treaty
rate), the withheld amount is exactly the value the tax page would credit — but the UI
never records it, because the withholding editor is not shown for dividends.

### 3.4 Currency model (UC-2)

- `currency` = the dividend's declared/account currency. `total_value` is in it.
- `dividend_payment_currency` = what actually landed in the account (e.g. JPY).
- `dividend_currency` = the currency the company declared the dividend in
  (e.g. USD — for foreign dividends, typically different from `currency`).
- `dividend_fx_rate` = `dividend_currency → dividend_payment_currency` rate.

Same-currency dividends collapse everything into one number; cross-currency dividends
split "declared" from "received" and need FX conversion, which is where the
gross/net/tax relationship stops being self-evident.

### 3.5 Fiscal rules are already policy-driven

`backend/services/pnl_rules.py` already branches by fiscal rule (`japan`, `spain`,
`default`), and `doc/calculations.md` §17.7-17.8 makes the tax model per-rule:

- `japan` — flat withholding-style rate (e.g. 20.315%) on gross dividends; FX-aware
  conversion to JPY.
- `spain` — dividends share the progressive savings bracket with capital gains;
  taxable base is the benefit (sell − cost), FX-rate-invariant.
- `default` — same progressive-savings shape as Spain.

So "what is taxable / how a withholding is credited" is already per-ruleset in the
engine — but the form treats Gross/Net/Taxes as a fixed single shape that does not vary
with the rule. The engine and the form do not agree on where the policy lies.

## 4. Desired behavior (the constraints)

These are the product's requirements as stated:

1. **Gross = Net + Taxes** — enforced and derivable (2-of-3), mirroring the
   triangulation the app already uses on investments (Qty/Price/Amount: fill two, the
   third is derived).
2. **Multiple taxes are allowed** — not a single inferred withholding. Reuse the
   existing multi-row Taxes editor (already built for investments): each row is a
   percentage AND/OR a fixed amount, in a currency, with a `tax_type`.
3. **Tax is policy-driven, not form-driven** — the meaning of "Amount"/"Gross"/"Net"
   and how a withholding is credited differs per fiscal rule. The form must not
   hardcode a single interpretation.

## 5. The design tension (why this is not a simple form change)

**The triangulation "Gross = Net + Taxes" is only exact within one currency.** For a
cross-currency dividend (USD declared → JPY received), Gross, Net, and the tax rows
live in different currencies, so `Gross = Net + Taxes` cannot hold numerically without
a policy-defined conversion:

- which currency is the triangle anchored in (`dividend_currency` vs `currency`)?
- which FX rate converts the missing leg (declaration-date vs payment-date)?
- does withholding *reduce the base* or act as a separate credit?

A second tension: the reports read `total_value` as both the gross base (tax page) and
the dividend received (yield/performance). If a user records a **net** into Amount,
reports silently under-report yield and the taxable base. Whichever interpretation the
form enforces, `total_value`'s meaning must stay stable and be stated, or every report
consumer must be migrated together.

## 6. What would have to change (inventory, not a design)

Nothing here is a decision — this is the surface area a later solution would touch:

- Form (`AddTransactionModal.svelte` / `EditTransactionModal.svelte`): expose the
  multi-row Taxes editor for dividends, add helper text, define the Gross/Net/Taxes
  derivation and its anchoring currency.
- Reports (`analytics_svc.py`): confirm `total_value` stays the single authoritative
  (gross) number, or migrate all consumers (yield, performance, dashboard, tax base)
  coherently.
- Tax engine (`pnl_rules.py` `dividend_taxable`, §17.3/17.4): apply withholding
  credit per fiscal rule (Spain foreign-credit vs Japan flat withholding).
- Persistence: emit `WITHHOLDING` `transaction_taxes` rows for dividends, in
  `dividend_currency`.
- i18n: `en` / `es` dividend helper strings.
- Onboarding/fiscal setup: whether the user picks the dividend tax treatment per
  rule, and which formula shape is offered.

## 7. Current-state matrix

| Capability | Investments (sell) | Dividends today |
|---|---|---|
| Triangulation 2-of-3 (Amount) | Yes (Qty/Price/Amount) | No (single required field) |
| Multiple taxes editor | Yes | No (gated to investments) |
| `WITHHOLDING` persisted | Yes | No — never written |
| Reported as gross base | Yes | Yes (only via `total_value`) |
| Fiscal-rule-driven tax shape | Yes (§17.7 ruleset) | No (hardcoded one shape) |

## 8. Open questions (deferred, not solved here)

- Which single currency anchors the Gross = Net + Taxes invariant per rule?
- Is "Amount" the gross (reports/yield/tax) or the net (cash received)? The two
  consumers today assume differently.
- How is a cross-currency withholding credited — reduce the taxable base, or a
  separate credit line, and per which fiscal rule?

These are deliberately left open. This document fixes the baseline so the follow-up
can be scoped from shared facts.

## References

- `doc/calculations.md` §16.6 (dividend yield / total dividends), §17.3-17.4
  (dividend tax base, exemption/credit), §17.7-17.8 (ruleset tax model / rates)
- `doc/uc_2_core_transactions.md` (dividend two-currency model)
- `backend/services/analytics_svc.py` (`get_dashboard`, `get_performance_summary`)
- `backend/services/pnl_rules.py` (`dividend_taxable`)
- `frontend/src/lib/components/modals/AddTransactionModal.svelte` /
  `EditTransactionModal.svelte` (dividend form, Taxes editor gate)
