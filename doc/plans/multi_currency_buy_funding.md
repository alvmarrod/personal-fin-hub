# Multi-currency buy-side funding — accepted limitation

<!-- issue: multi-currency-buy-funding / status: accepted-limitation / area: currency, transactions, UC-08 -->

This document records a known simplification in how `INVESTMENT_BUY` is modeled for
multi-currency-capable brokers (`entities.supports_multi_currency = TRUE`). It is not a
bug and not scheduled for a fix — it is logged here so the reasoning behind the
simplification survives, and so it can be revisited later if it ever stops being good
enough.

## 1. The real-world behavior

On a broker WITHOUT multi-currency support (e.g. Trade Republic):

1. The broker converts and pays for the purchase out of the account's single home
   currency. One conversion, one payment. Done.

On a broker WITH multi-currency support (e.g. IBKR):

1. The broker prices the purchase in the asset's native currency.
2. If the account already holds a balance in that currency, it is used first.
3. If the existing balance in that currency is insufficient, the broker converts the
   remaining amount from another currency (typically the account's main/base currency)
   to cover the shortfall.

Worked example: account is JPY-denominated, buying $3,000 of a USD asset, account
already holds $2,000. The broker uses the existing $2,000 and converts the remaining
$1,000 from JPY. **A single buy transaction can therefore be funded from two different
currency pockets at once.**

## 2. Why this doesn't fit the current transaction model

`transactions.payment_currency` / `fx_rate` (the fields `INVESTMENT_BUY`, `INVESTMENT_SELL`,
and the unified dividend model all use for cross-currency handling — see UC-08/UC-09/UC-10
and the `entities.supports_multi_currency` design) can only express "this whole
transaction was paid in currency X." There is no field, or set of fields, that
represents a SPLIT: part of the payment drawn from an existing balance in the asset's
currency, part drawn via a fresh conversion from another currency.

Representing the split precisely would require:

- A new child table (something like "buy funding sources": one row per pocket used,
  each with its own currency and amount, summing to the transaction total), analogous
  to `transaction_fees` / `transaction_taxes` but for funding sources instead of costs.
- The user (or an import pipeline) knowing and entering exactly how much of each buy
  came from existing balance vs. fresh conversion — a breakdown most brokers don't even
  surface clearly in their own statements.

## 3. Why we are not modeling it precisely

- **The Tier 5 Reconciliation Model already exists for exactly this kind of drift.**
  `balance_snapshots` periodically anchor the true balance per `(entity, currency)`
  pocket, and `BALANCE_ADJUSTMENT` silently absorbs any accumulated discrepancy between
  snapshots (`calculations.md` §8, Tier 5). No individual transaction between two
  snapshots is expected to be perfectly cash-accurate — that is precisely the problem
  the snapshot/adjustment mechanism was built to solve.
- **Cost/benefit is lopsided.** A funding-sources child table, plus the UI/UX to enter
  it, plus the accounting logic to apply it across two pockets, is a non-trivial
  addition for a discrepancy that self-corrects at the next snapshot regardless.
- **The data usually isn't cleanly available.** Most broker statements don't break out
  "this much came from existing balance, this much was converted" per trade, so
  precise modeling would often mean the user guessing/estimating anyway.

## 4. Accepted simplification

`INVESTMENT_BUY` uses the same entity-driven default as `INVESTMENT_SELL` /
dividends, with no split-funding awareness:

| `entities.supports_multi_currency` | Default applied to the buy |
|---|---|
| `TRUE` | `payment_currency` defaults to `NULL` — the buy is treated as if fully funded from the asset-currency pocket, even when in reality part of it was converted. The next balance snapshot absorbs the resulting drift on both pockets involved. |
| `FALSE` | `payment_currency` defaults to `entities.main_currency`, `fx_rate` auto-filled — matches reality exactly (single conversion, single payment), no simplification needed here. |
| `NULL` (unclassified) | No default applied — today's fully manual behavior. |

The user can still override `payment_currency`/`fx_rate` manually on a specific buy
(e.g. to reflect a purchase they know was entirely funded by a fresh conversion), the
same override capability that already exists for sells.

## 5. Scope

- Affects `INVESTMENT_BUY` (UC-08) only. `INVESTMENT_SELL` (UC-09) and dividends
  (UC-10, after the payment_currency/fx_rate field unification) have no equivalent
  split-funding scenario — proceeds are a single inflow into a single pocket, not a
  payment potentially drawn from several.
- No schema change beyond what the `supports_multi_currency` / `main_currency` design
  already introduces for entities. No funding-sources child table is created.

## 6. Revisit triggers

Worth revisiting only if one of these becomes true:

- A user relies heavily on partial-balance-funded buys and the resulting snapshot
  drift becomes large or frequent enough to be noticeable/confusing.
- A broker import/statement source is added that DOES cleanly expose the per-pocket
  funding split, making precise modeling cheap instead of speculative.

Until then, this is an accepted limitation, not an open task.
