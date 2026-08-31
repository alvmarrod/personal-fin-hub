# Asset Evaluation Methodology — High-Level Design (HLD)

## 1. Purpose

Define a repeatable method to evaluate individual equities against a set of Key
Performance Indicators (KPIs), producing:

1. An **immediate-good flag** — a strict, independent signal that an asset
   clears every quality bar at once.
2. A **ranking score** — a continuous, organic ordering of all evaluated
   assets, blending fundamentals, valuation, and macro context.

This document defines the **method only** (structure, formulas, scoring
logic). It does not implement the pipeline, and initial threshold values are
provisional pending real data.

## 2. Scope

- **Asset universe**: equities only (ETFs, bonds, commodities out of scope
  for this version).
- **Data source**: equity fundamentals sourced exclusively via `yfinance`.
  Any KPI whose input isn't available there is out of scope until a
  different source is integrated.
- **Markets covered**: no explicit restriction, but macro-adjustment logic
  (Section 6) currently only has local data mapped for USA, Japan, and Spain
  / Eurozone. Other markets fall back to the global aggregate.

## 3. KPI Sections

| Section | Status | Examples (illustrative, not final) |
|---|---|---|
| Fundamentals | Defined below | Revenue growth, ROE / ROIC, gross & operating margin, net debt/equity, EBIT-based interest coverage, FCF conversion |
| Valuation | Defined below | P/E, EV/EBIT, P/FCF, dividend + buyback yield |
| Qualitative | **Open / TBD** | Moat, management quality, governance — deferred pending a dedicated strategy so the KPI set doesn't bloat with low-signal, hard-to-score items |

The qualitative section is intentionally left as a placeholder in this HLD.

## 4. Per-KPI Scoring — Overview

Every KPI in Fundamentals and Valuation produces **two independent outputs**:

1. **Level band** (red / yellow / green) — used for display and for the
   immediate-good gate (Section 5).
2. **Alignment score** (0–5) — a fused signal used as the KPI's contribution
   to the ranking score (Section 6). It folds in the KPI's own trend and,
   where applicable, macro context — so it is *not* re-combined with the
   level band again downstream. Each KPI's two outputs each do one job, with
   no double-counting between them.

### 4.1 Level band

- Computed as the KPI's **percentile rank within its GICS sector** (sector
  level, not sub-industry, to keep peer groups statistically meaningful).
- Percentile bands map to red / yellow / green. Exact cut points are
  provisional starting values (e.g. bottom quartile = red, middle two
  quartiles = yellow, top quartile = green, direction-adjusted per KPI) and
  will be recalibrated once real sector-level data is pulled.

### 4.2 Trend

- Default lookback: **5 years**. If a company has less history, the window
  shortens automatically and the trend is flagged low-confidence rather than
  excluded.
- Trend is expressed as a slope (e.g. CAGR or YoY average change),
  sign-adjusted so that "favorable direction" is always positive.

### 4.3 Macro pairing

Selected KPIs are paired with a macro variable that plausibly modulates
their interpretation. Initial mapping (extendable):

| KPI category | Macro pairing | Rationale |
|---|---|---|
| Debt / leverage | Policy interest rate (level + change) | Debt is more expensive/risky in a rising-rate environment |
| Margins / profitability | M2 growth | Loose money conditions typically support pricing power and demand |
| Valuation multiples | Yield curve slope | Multiple compression is more "expected" in a flattening/inverting curve |

KPIs without an obvious macro counterpart use a **2-input alignment**
(level + trend only, reweighted — see 4.4) instead of being excluded.

### 4.4 Alignment score (0–5)

**Inputs** (4, or 2 when no macro pairing applies), each normalized to
`[-1, +1]` with +1 always meaning "favorable":

- `level_score` — KPI's sector-relative percentile, rescaled from `[0,100]`
- `trend_score` — KPI's own slope, divided by a reference scale for that
  KPI/sector, clipped to `[-1,+1]`
- `macro_level_score` — mapped macro variable's percentile vs. its own
  historical range
- `macro_trend_score` — mapped macro variable's slope, divided by its own
  reference scale, clipped to `[-1,+1]`

**Combination** (weights are named parameters, default equal):

```
alignment_raw = w1*level_score + w2*trend_score
              + w3*macro_level_score + w4*macro_trend_score

# default: w1 = w2 = w3 = w4 = 0.25
# 2-input fallback (no macro pairing): w1 = w2 = 0.5, w3 = w4 = 0
```

**Bucketing to 0–5:**

```
[-1.00, -0.67) -> 0     [-0.67, -0.33) -> 1     [-0.33, 0.00) -> 2
[ 0.00,  0.33) -> 3     [ 0.33,  0.67) -> 4     [ 0.67,  1.00] -> 5
```

**Worked example — Debt alignment:**

| Signal | Raw value | Normalized |
|---|---|---|
| Debt level | 5% (80th sector percentile) | +0.60 |
| Debt trend (5y) | -1%/y | +0.50 |
| Policy rate level | 2% (low historical percentile) | +0.70 |
| Policy rate trend | -0.25%/y | +0.50 |

`alignment_raw = 0.25*(0.60+0.50+0.70+0.50) = 0.575` → bucket **4**.

## 5. Immediate-Good Rule

**Trigger**: all KPIs, across all sections, are in the **green** level band.

> **Assumption (not yet confirmed)**: "all KPIs" means the **level bands
> only** — trend rows are excluded from this gate. Requiring trend rows too
> would make the flag very hard to trigger, and the trend dimension is
> already captured via the ranking score. Revisit if this reads
> differently than intended.

This is a strict, independent flag — it does not depend on the ranking
score, and there is no mirrored "immediate-bad" disqualifier. Assets that
fail to trigger it are simply left to the ranking (Section 6) to sort
organically; a structurally broken asset should already sink there via its
own red KPIs.

## 6. Ranking Score

- **Aggregation**: equal-weighted sum of all KPI alignment scores by
  default. Section weights and per-KPI weights are named, tunable
  parameters — not hardcoded into the model shape.
- **No hard veto**: there is no exclusion rule at the ranking stage; a weak
  KPI is expected to pull the aggregate down rather than disqualify the
  asset outright.
- **Independent from immediate-good**: an asset can rank highly without
  triggering immediate-good, or vice versa. Both outputs are reported
  side by side, not merged into one number.

## 7. Macro Exposure Basis

- Exposure is assigned by the stock's **primary listing market**
  (not revenue geography — too data-intensive to determine reliably today).

> **Assumption (not yet confirmed)**: "primary listing market" resolves
> from `yfinance`'s `info['exchange']` field, falling back to
> `info['country']` where exchange doesn't map cleanly to USA/Japan/Spain.
> Mechanical choice, not a value judgment — revisit if a cleaner field
> turns up during implementation.

- The **global aggregate** macro reading is applied as a secondary modifier
  alongside the local reading, consistent with the existing macro framework's
  USA / Japan / Spain / global-aggregate structure.
- A stock listed outside USA / Japan / Spain falls back to the global
  aggregate alone until local data is mapped for its market.

## 8. Macro Variables

| Variable | Priority | Source | Status |
|---|---|---|---|
| M2 money supply growth (YoY) | Tier 1 | Central bank / public statistical sources (not `yfinance`) | To be built |
| Policy interest rate (level + change) | Tier 1 | Central bank / public statistical sources | To be built |
| Yield curve slope | Tier 1 (added) | Public bond yield data per market | To be built |
| Corporate credit spread | Deferred | — | Out of scope for now |
| Private-sector credit growth | Deferred | — | Out of scope for now |
| Capacity utilization | Deferred | — | Out of scope for now |

None of these are available via `yfinance`; a separate data pipeline will
be built later, prioritized around these three single-metric, publicly
available variables.

## 9. Open Items (deferred, not blocking this HLD)

- Qualitative KPI section: strategy to be defined separately so it adds
  signal without bloating the KPI set.
- Threshold values in Section 4.1 are provisional; recalibrate once real
  sector-level data is pulled via `yfinance`.
- Macro data pipeline (Section 8) does not exist yet.
- Alignment weights (Section 4.4) and ranking weights (Section 6) are set
  to equal defaults; revisit once the model is running on real data.
