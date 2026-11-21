# View: Investment Strategy (`/strategy`)

**Source**: `frontend/src/routes/strategy/+page.svelte`, `lib/components/modals/StrategySetModal.svelte`

## Layout

```text
Investment strategy                                  [+ Add target set]

┌─────────────────────────────────────────────────────────────────────┐
│ Target sets                                                          │
│ 01/01/2026   [Current]   Equities 55% · Bonds 30% · Cash 15%  [edit] [delete]
│ 01/01/2027   [Planned]   Equities 53% · Bonds 32% · Cash 15%  [edit] [delete]
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ Current drift · Target of 01/01/2026        Values in EUR            │
│ Bucket     Target   Actual   Drift    Amount to move                │
│ Equities     55%      62%    +7.0 pp        -2.149 €                │
│ Bonds        30%      24%    -6.0 pp        +1.842 €                │
│ Cash         15%      10%    -5.0 pp        +1.535 €                │
│ Unassigned     —       4%         —               —                 │
│ Rows beyond ±5 percentage points are highlighted.                    │
└─────────────────────────────────────────────────────────────────────┘
```

## Data

- `GET /strategy` — target sets, sorted by `effective_from`.
- `GET /strategy/drift?display_currency=…` — current bucket values, targets, shares,
  drift in percentage points, amount to move, `as_of`, and the unassigned residual.
  The backend owns the asset-class → bucket mapping.
- `GET /strategy/history?start_date=…&end_date=…&interval=…&display_currency=…` —
  one point per bucket and sample date with `value`, `share_pct` and the
  `target_pct` in effect at that date (null before the first set).
- The page has no display-currency selector; it follows the global preference and
  shows it next to the drift table.

## Historical comparison

Below the drift card, five small multiples (one per bucket). Each has two series
over the same date axis:

- **Actual** (solid): the bucket share of the whole portfolio at each sampled date.
- **Target** (dashed, `stepped: 'before'`): the set in effect at that date. The
  target changes only at an `effective_from`; it is never interpolated. It is
  `null` before the first set, so the dashed line starts where the policy starts.

Presets: 3M / 6M / 1Y / All. The interval is `week` for 3M/6M and `month` for
1Y/All; All starts at 2020-01-01. The five charts share a 0–100% scale, so the
shapes are comparable. Percentages stay visible in privacy mode.

Unassigned holdings are not a series; a note shows their latest share. A second
note states that historical values are converted at the latest FX rate, so the
shape is approximate.

## Behaviour

- **Badges**: the set resolved by the server (`drift.effective_from`) is *Current*;
  dates after `as_of` are *Planned*; earlier sets are *Past*.
- **Editor** (modal): five number inputs, a live total, Save disabled until the
  total is 100 ± 0.01. The effective date is editable only when creating; the
  date identifies the set.
- **Delete** asks for confirmation. Deleting the only set returns to the empty
  state.
- **Drift rows** sort by target, descending. *Unassigned* appears only when
  non-zero and is not targetable.
- **Band**: rows where `|drift| > 5 pp` get the warning background. The threshold
  is fixed.
- **Privacy mode** masks amounts; shares, targets and drift points stay visible.
- **No set effective today**: the drift card shows *No target defined for today*
  and the date of the first set when one exists.
- **No sets at all**: empty state with the explanation.
- **Missing FX rate**: an asterisk on the affected bucket and a note below the
  table; the weight is approximate.

## Out of scope

- Dashboard card: implemented separately, see [dashboard.md](dashboard.md).
- Historical target-vs-actual chart (phase 2, see `doc/plans/investment_strategy.md`).
- Automatic rebalancing (UC-55).
- Custom buckets or custom mapping.
