# Plan — Investment Strategy (Target Allocation)

**Status**: implemented (BE 0.35.0 / FE 0.39.0)
**Source**: `backend/services/strategy_svc.py`, `backend/routes/strategy.py`, `frontend/src/routes/strategy/+page.svelte`
**Depends on**: nothing. UC-55 (portfolio rebalancing) stays a separate flow.

## Purpose

Let a profile define a target allocation as a **policy that changes over time**, and compare the current portfolio against the target in effect today.

A Bogle-style example: 30% bonds, 15% cash, 55% equities. Next year the same user may want 32% bonds. Both targets must exist at the same time, each with its start date.

**Non-goals**

- No investment advice and no automatic trading.
- No tax or fee optimisation.
- No rewrite of past targets when a new set is added.
- No change to asset classes, the asset-class dropdown, or `portfolio_assets.desired_weight`.

## Policy buckets

The strategy uses five fixed buckets. The mapping is code, not configuration, so target and actual always use the same grouping.

| Bucket | Key | Asset classes |
|---|---|---|
| Equities | `equities` | `VI` |
| Bonds | `bonds` | `FI`, `corp FI`, `Sovereign FI`, `mix FI` |
| Cash | `cash` | `CASH`, `Monetary` |
| Real estate | `real_estate` | `REIT` |
| Gold | `gold` | `Gold` |

Two mappings need a note:

- **`Monetary` → Cash.** Money-market funds behave like cash in allocation terms.
- **`REIT` keeps its own bucket.** It is equity-like, but the app already treats it as a top-level class. Folding it into Equities would silently reclassify holdings. A user who follows a strict Bogle model sets Real estate to 0.

### Definition time vs representation time

- **Definition time** has exactly five buckets. A target set assigns a percentage to each, zeros included.
- **Representation time** may show a sixth row, **Unassigned**, for holdings whose class maps to no bucket (`null`, `UNSPECIFIED`, unknown strings). Unassigned is not a bucket: it cannot be targeted and never appears in the editor.

## Target sets

Each set is a full policy snapshot with a start date. Sets are ordered in time; the latest set that started on or before a date is the target for that date (a step function, not interpolation).

Planned table (not implemented):

```sql
CREATE TABLE strategy_targets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_id INTEGER NOT NULL REFERENCES profiles(id),
  effective_from TEXT NOT NULL,        -- profile-timezone calendar date
  bucket TEXT NOT NULL,                -- equities | bonds | cash | real_estate | gold
  target_pct REAL NOT NULL CHECK (target_pct BETWEEN 0 AND 100),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (profile_id, effective_from, bucket)
);
```

Rules:

- One set per `effective_from`. Replacing a set deletes and re-inserts its five rows in one transaction.
- All five buckets are stored, including zeros, so a set is always complete.
- The sum must be **100 ± 0.01**. The server rejects anything else.
- A date before the first set has no target. The UI must say so; it must not invent one.
- Future sets are valid and inert until their date. No scheduler is involved.
- Backdated sets are allowed, to correct history.
- Past sets remain editable as a correction. The UI warns once that historical comparisons change.
- Dates are profile-timezone calendar dates, like fiscal periods.

## Calculations

Computed by `GET /strategy/drift`; the client formats the result and does not aggregate.

All values use the display currency at the top of the page.

- `bucket_value` = sum of the converted values of all holdings in the bucket's classes, cash included.
- `total` = sum of the five bucket values **plus unassigned holdings**. The target is a share of the whole portfolio, not of a mapped subtotal.
- `actual_share` = `bucket_value / total`.
- `target_amount` = `target_pct / 100 × total`.
- `drift_pp` = `actual_share × 100 − target_pct`.
- `amount_to_move` = `target_amount − bucket_value`. Positive means add, negative means trim.
- Drift amounts sum to the unassigned value, which reads correctly as "move unassigned money into buckets".

Display rules:

- Highlight rows where `|drift_pp|` exceeds **5 percentage points**. The band is fixed and not stored.
- Show amounts masked when privacy mode is active; keep percentages and drift in points visible.
- Show negative cash as a negative bucket value. Do not clamp it at zero.
- When a holding had no FX rate, its converted value is approximate. Use the same flag as the dashboard matrix.

## API

All routes are profile-scoped (`X-Profile-ID`).

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/strategy` | All sets, sorted by `effective_from` |
| `POST` | `/strategy` | Create a set |
| `PUT` | `/strategy/{effective_from}` | Replace a set |
| `DELETE` | `/strategy/{effective_from}` | Delete a set |
| `GET` | `/strategy/drift` | Current bucket values and drift against the set in effect today |
| `GET` | `/strategy/history` | Per-date bucket shares and the target in effect at each date |

Validation: known bucket keys only, `0–100`, five rows per set, sum `100 ± 0.01`, no duplicate date.

### Drift endpoint

`GET /strategy/drift?display_currency=EUR`

The backend owns the class → bucket mapping, so the client never duplicates it.

```json
{
  "effective_from": "2026-01-01",
  "as_of": "2026-11-21",
  "total": 30700.0,
  "rate_missing": true,
  "buckets": [
    {
      "bucket": "equities",
      "target_pct": 55,
      "value": 19034,
      "share_pct": 62.0,
      "drift_pp": 7.0,
      "amount_to_move": -2151,
      "rate_missing": false
    }
  ],
  "unassigned": { "value": 1228, "share_pct": 4.0, "rate_missing": false }
}
```

Rules:

- `as_of` is today in the **profile timezone**. There is no date parameter on this endpoint: a past target date combined with current values would be misleading. Time travel belongs to `/strategy/history`.
- Values come from `get_holdings_by_entity(display_currency)` aggregated into the five buckets, plus the unassigned residual, so currency conversion and `rate_missing` reuse the existing path.
- No set is effective today → `200` with `effective_from: null` and `buckets: []`. The UI shows “no target defined”.
- `rate_missing` is true when any row that feeds the result had no FX rate; the per-bucket flag marks the affected rows.
- `buckets` always contains the five keys in a fixed order; the client sorts by target for display.

## UI

### `/strategy` page

Placed under **Investments** in the sidebar.

```text
Investment strategy                                  [+ Add target set]

From 2026-01-01   ● Current    Equities 55%  Bonds 30%  Cash 15%  Real estate 0%  Gold 0%  [edit]
From 2027-01-01   ○ Planned    Equities 53%  Bonds 32%  Cash 15%  Real estate 0%  Gold 0%  [edit]
```

- Timeline of sets with a Past / Current / Planned badge.
- Editor: five rows, a running total, save disabled until the total is exactly 100.
- Delete a set. Deleting the only set returns to the empty state.

### Current drift

Shown on the strategy page from `GET /strategy/drift`:

```text
Strategy · target of 2026-01-01
Equities    55% target   62% actual   +7 pp   −2.100 €
Bonds       30%           24%          −6 pp   +1.800 €
Cash        15%           10%          −5 pp     +300 €
Unassigned    —            4%           —          —
```

- Rows ordered by target, descending.
- Unassigned appears only when non-zero.
- No set effective today: show “no target defined” and, when a future set exists, its date.
- No sets at all: show a call to action that opens the editor.

### Dashboard card

The dashboard shows a **Target vs Actual** card as the third item of the exposure
row (three equal columns, two below 1100px, one below 768px):

- Scatter of target % (x) against actual % (y) for the five buckets.
- Green diagonal `y = x` = on policy; neon red vertical stem from each bubble to
  `(target, target)`, whose length is the drift in percentage points.
- Bubbles use the bucket colours, radius from the actual share; bucket names and
  signed drift labels are drawn on the chart.
- Buckets at 0% target and 0% actual are hidden and counted under the chart.
- No set effective today → a centred “Go to strategy view” button.
- Data: `GET /strategy/drift`. A failure falls back to the button; it does not
  break the dashboard.

### History

`GET /strategy/history?start_date=&end_date=&interval=&display_currency=` returns one point per bucket and sample date:

```json
{ "points": [
  { "date": "2026-06-01", "bucket": "equities", "value": 19034, "share_pct": 62.0, "target_pct": 55.0 }
] }
```

- Values reuse `get_historical_values_by_asset_class` and the same class → bucket mapping as the drift.
- `target_pct` is the set in effect at that date; `null` before the first set.
- `share_pct` uses the whole portfolio as the denominator; unassigned points have `target_pct: null`.
- The view plots five small multiples, each with the actual share (solid) and the target (dashed step).
- Known caveat: the historical endpoint converts at the latest FX rate, so the chart shows shape, not audit values.

## Edge cases

| Case | Behaviour |
|---|---|
| Date before the first set | No target for that period; the UI says so |
| Only set deleted | Back to the empty state |
| Held class mapped to no bucket | Shown as Unassigned; included in the total |
| Bucket with target but no holdings | `amount_to_move` equals the full target amount |
| Negative cash | Shown as a negative value and a share below zero |
| Missing FX rate | Converted value flagged as approximate |
| Multi-profile | One timeline per profile |
| Editing a past set | Allowed, with a warning that comparisons change |

## Relationship with `desired_weight` and UC-55

- `portfolio_assets.desired_weight` is a per-asset target used by the planned rebalance flow (UC-55).
- This plan defines a per-bucket policy above it.
- The two can disagree. The UI compares only the bucket policy and must say so.
- A later change may derive per-asset targets from the bucket target times the intra-bucket share. Do not build that now.

## Future extensions

- **User-defined buckets and mapping.** The target rows already key on bucket strings, so a mapping table can be added without migrating target values.
- **Glide interpolation** between anchor dates, instead of steps.
- **Automatic rebalancing** (UC-55).

## Test plan

- Validation: unknown bucket, six rows, missing bucket, sum below and above 100, duplicate `effective_from`.
- Resolution: date before the first set, exact date, between sets, future set.
- Replace and delete a set.
- Mapping: every class maps once; unknown class goes to Unassigned; cash included.
- Drift: shares, amounts, unassigned in the total, negative cash, missing-rate flags, fixed bucket order, no effective set.
- History: class → bucket mapping, per-date target resolution (null before the first set), unassigned points, interval forwarding.
- Profile isolation: one profile never sees another profile's sets.
- UI: total gate, badge states, empty states, privacy mode.

## Decisions log

| # | Decision | Choice |
|---|---|---|
| 1 | Bucket model | Fixed, five buckets (no user mapping) |
| 2 | Actual weights denominator | Whole portfolio, unassigned included |
| 3 | Editing past sets | Allowed as a correction, with a warning |
| 4 | Page placement | Investments |
| 5 | Rebalancing band | Fixed ±5 pp, not stored |
| 6 | Zeros | All five buckets stored per set |
| 7 | Backdated sets | Allowed |
| 8 | Negative cash | Shown as-is |
| 9 | Doc location | `doc/plans/` until implemented |
| 10 | Bucket labels | Equities / Bonds / Cash / Real estate / Gold |
| 11 | History scope | Timeline, current drift and the historical comparison chart |
| 12 | Mapping owner | Backend only, inside `/strategy/drift` |
| 13 | Drift endpoint | Dedicated `GET /strategy/drift`, no client aggregation |
| 14 | Dashboard representation | Bubble scatter, target vs actual, green diagonal and red stems |
