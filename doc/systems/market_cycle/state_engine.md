# Investment Market Cycle State Engine — High-Level Design (HLD)

## 1. Purpose

The **Investment Market Cycle State Engine** is a computation layer. It
determines the current market-cycle state from normalized macro metrics.

The engine is the middle layer of the Investment Market Cycle separation
(`doc/plans/Investment_Market_Cycle_HLD_And_View.md` §16):

* source data → data layer;
* state determination → this engine;
* display → view.

The engine:

* evaluates state conditions;
* evaluates transition conditions;
* tracks the current state;
* tracks emerging transitions;
* confirms state changes.

The engine does all of this for one market scope at a time. It is
parameterized by scope, not duplicated per scope. See §8.

## 2. Scope

The engine consumes normalized metrics and produces a state-machine status.
It does not:

* acquire or source data (`doc/kpis/world.md` §2,
  `doc/datasources/market_api.md`);
* compute trend direction or the real interest rate (`doc/derived/macro.md`);
* apply persistence or confirmation timing (this document, §11);
* render anything to the user (future view spec).

The behavioral intent for the state machine comes from the Investment Market
Cycle HLD plan §2–§6, §13–§16. This document formalizes that intent into an
interface contract: what the engine consumes, what edges may fire, and what it
produces.

## 3. State Model

The market cycle is a finite state machine with six fixed states (HLD plan §2,
§4):

| # | State | Definition |
|---|---|---|
| 1 | Low Real Rates | Real interest rates are low. This state is not defined by nominal rates. (HLD §4.1) |
| 2 | Rising Inflation | Inflation is increasing. Monetary policy has not yet entered a sustained hiking cycle. (HLD §4.2) |
| 3 | Hiking Cycle | An active period of nominal interest-rate increases. (HLD §4.3) |
| 4 | High Real Rates | Real interest rates are high. (HLD §4.4) |
| 5 | First Rate Cut | The first nominal rate cut following the hiking cycle. (HLD §4.5) |
| 6 | Cutting Cycle | An active period of nominal interest-rate reductions. (HLD §4.6) |

Rules:

* The states are fixed. The system must not skip states or jump between
  unrelated states (HLD §2).
* The only legal moves are the edges defined in §5.
* The normal forward progression is:

**1 → 2 → 3 → 4 → 5 → 6 → 1**

## 4. Engine Inputs

The engine consumes one set of normalized metrics per market scope. Each input
maps to a catalogued KPI and a derivation step:

| Input | KPI (`doc/kpis/world.md`, `doc/derived/macro.md`) | Derived in (`doc/derived/macro.md`) |
|---|---|---|
| nominal policy rate (level) | `policy_rate` | — |
| nominal rate trend (direction) | `policy_rate_trend` | trend direction |
| inflation rate (level) | `inflation_rate` | — |
| inflation trend (direction) | `inflation_rate_trend` | trend direction |
| real interest rate (level) | `real_interest_rate` | real interest rate |
| real rate trend (direction) | `real_interest_rate_trend` | trend direction |

Direction values are `increasing`, `stable`, and `decreasing` (HLD §3).

The engine also reads:

* `previous_state`, its own last committed state;
* the persistence status of each candidate transition (§6).

From these inputs the engine derives the following signals. Signals are
computations, not configuration; the real-rate thresholds `high`/`low` and the
`hikes_resumed` lookback are parameters (§10):

* `real_rates_high` — real interest rate above the configured high threshold.
* `real_rates_low` — real interest rate below the configured low threshold.
* `real_rates_declining` — real rate trend is `decreasing`.
* `real_rates_climbing` — real rate trend is `increasing`.
* `hikes_resumed` — nominal rate trend is `increasing` after a pause or cut
  (a non-`increasing` month within the lookback window).
* `hikes_stopped` — nominal trend is no longer `increasing` during a hiking.
* `cuts_stopped` — nominal trend is no longer `decreasing` during an easing.
* `first_cut_detected` — nominal trend is `decreasing` while in the Hiking
  Cycle or High Real Rates (the cutting phase for that state; it persists while
  cuts continue, so it can meet the confirmation period).

Transition binding in §5 uses these signals only. The engine does not read
currency, country, or data-provider specifics (HLD §15).

## 5. Transition Model

Each transition has (HLD §6):

* source state;
* target state;
* trigger conditions;
* confirmation conditions;
* transition status (§6);
* priority; display ordering only, never an arbiter;
* direction; `Forward` or `Reverse`.

### Forward edges

| Edge | Trigger conditions | Confirmation |
|---|---|---|
| 1 → 2 Low Real Rates → Rising Inflation | `inflation_rate_trend = increasing` | §11 persistence |
| 2 → 3 Rising Inflation → Hiking Cycle | `policy_rate_trend = increasing` | §11 persistence |
| 3 → 4 Hiking Cycle → High Real Rates | `real_rates_high` | §11 persistence |
| 4 → 5 High Real Rates → First Rate Cut | `first_cut_detected` | §11 persistence |
| 5 → 6 First Rate Cut → Cutting Cycle | nominal trend stays `decreasing` | §11 persistence |
| 6 → 1 Cutting Cycle → Low Real Rates | `real_rates_low` | §11 persistence |

### Reverse edges

Reverse edges exist so the machine never forces real-world conditions into an
incorrect forward progression (HLD §2, §5). Each reverse edge is a
configuration slot. Its trigger conditions are provisional until data
calibrates them, marked `[draft]`, and each edge can be disabled in
configuration.

| Edge | Trigger conditions `[draft]` | Confirmation |
|---|---|---|
| 6 → 2 Cutting Cycle → Rising Inflation | `real_rates_declining` AND `cuts_stopped` | §11 persistence, multi-signal (HLD §5) |
| 5 → 4 First Rate Cut → High Real Rates | `real_rates_high` AND `hikes_resumed` | §11 persistence |
| 4 → 3 High Real Rates → Hiking Cycle | `hikes_resumed` AND real rates climbing | §11 persistence |
| 3 → 2 Hiking Cycle → Rising Inflation | `hikes_stopped` AND `inflation_rate_trend = increasing` | §11 persistence |

Edges not listed above are not legal transitions. The engine can only move
from its current state through the outgoing edges of that state.

## 6. Transition Statuses and Tie Handling

Each transition has one of four statuses (HLD §6):

| Status | Meaning |
|---|---|
| Inactive | Conditions for the transition are not present |
| Emerging | Initial conditions are beginning to appear |
| Near | Most required conditions are satisfied |
| Triggered | Conditions required for the transition are confirmed |

### Two-stage confirmation

A transition becomes `Triggered` only after its confirmation conditions are
satisfied for the configured persistence period (this document, §11,
HLD §14). State changes only on a confirmed transition. A single short-lived
movement in one metric is not enough to move state (HLD §14).

Status is derived from how many **consecutive monthly points** the edge's
signal(s) have held (the confirmed values below are the provisional defaults,
§10):

| Held (months) | Status |
|---|---|
| 0 | Inactive |
| 1 | Emerging |
| 2 | Near |
| 3 or more | Triggered |

### Tie-hold rule

If two or more transitions are `Triggered` at the same time, the engine does
**not** move state. All confirmed candidates remain `Triggered`, and the view
shows them all as activating. The engine re-evaluates on every refresh. It
moves to a candidate's target only when that candidate is the **only**
`Triggered` transition at that moment.

Reasoning: each transition target describes a state the analysis may still
consolidate into. If two targets comply, the analysis has not settled, so the
engine waits. As signals evolve, one candidate stops complying, and the state
then resolves to the remaining candidate.

This rule gives state changes the property of a unique, stable target. Priority
never breaks this tie.

### Ambiguous hold

If two or more `Triggered` candidates persist indefinitely, the engine holds
state and reports an `ambiguous_confirmation` condition in its output. The
cause is a signal or configuration problem for the state analysis, not
something the engine guesses at.

### Priority

`priority` is a per-transition field used for display ordering only (the order
the view lists candidate transitions). Default order: forward edges in table
order, then reverse edges R1–R4. Scope configuration may override the display
order. Priority never selects between simultaneously `Triggered` transitions.

## 7. State Determination Inputs

A market-cycle state can depend on (HLD §13):

1. current level;
2. direction;
3. persistence;
4. relationship between metrics;
5. policy behaviour;
6. previous state.

The engine evaluates all six factors. The nominal-versus-real rule is explicit:
the engine must evaluate the real-rate metric separately from the nominal
policy rate. A high nominal rate does not automatically mean High Real Rates,
and a low nominal rate does not automatically mean Low Real Rates (HLD §13).

## 8. Instantiation and Scopes

The engine is one component, parameterized by market scope. A market scope is
a country, a monetary region, or a global aggregate (HLD §15). Scope names match
the per-market rows in `doc/kpis/world.md` §2: USA, Japan,
Spain/Eurozone, Global aggregate.

Each scope has:

* its own normalized metrics (§4);
* its own transition configuration (§5, §10);
* its own current state and state history.

The engine logic itself is shared and scope-agnostic.

## 9. Output Contract

The view (and later the API) consumes one status object per scope:

```json
{
  "scope": "USA",
  "current_state": { "id": 4, "name": "High Real Rates" },
  "current_state_since": "2026-01-15",
  "active_transitions": [
    {
      "source": "High Real Rates",
      "target": "First Rate Cut",
      "status": "Triggered",
      "direction": "Forward",
      "priority": 3
    }
  ],
  "entry_signals": "favourable",
  "ambiguous_confirmation": false,
  "last_update": "2026-09-25T10:00:00Z"
}
```

Field meanings:

* `current_state` and `current_state_since` — the committed state and its
  commit date.
* `active_transitions` — every outgoing transition of the current state with
  its current status. The view uses this list for highlighting and animation
  (§6).
* `entry_signals` — `none`, `favourable`, or `strong`. `favourable` when the
  current state is High Real Rates. `strong` when the current state is First
  Rate Cut (HLD §9).
* `ambiguous_confirmation` — `true` while the tie-hold rule (§6) is holding on
  two or more `Triggered` candidates.
* `last_update` — the evaluation timestamp.

Entry signals describe a market-cycle monitoring framework, not deterministic
predictions (HLD §17).

## 10. Configuration Surface

All numerical and behavioral parameters are configuration, not code (HLD §5,
§14). They live in `backend/config.json` under `market_cycle`:

| Key | Default | Meaning |
|---|---|---|
| `initial_state` | `1` | State the replay starts from |
| `real_rate_thresholds.high` | `1.0` | `real_rates_high` threshold |
| `real_rate_thresholds.low` | `0.25` | `real_rates_low` threshold |
| `persistence_months.emerging` | `1` | Consecutive months → Emerging |
| `persistence_months.near` | `2` | Consecutive months → Near |
| `persistence_months.triggered` | `3` | Consecutive months → Triggered |
| `hikes_resumed_lookback_months` | `6` | Window for the `hikes_resumed` pause/cut check |
| `reverse_edges_enabled` | all `true` | Per reverse edge (`6->2`, `5->4`, `4->3`, `3->2`) |
| `priority` | (optional) | Display-order override per edge |

The forward and reverse **edges and their conditions** are the model (code,
§5); the values above are the tunable parameters. Values are provisional until
real data calibrates them. The doc stance matches
`doc/systems/asset_evaluation/methodology.md`: provisional until data.

## 11. Persistence and Confirmation

A transition uses two stages (HLD §14):

1. **Emerging** — the initial conditions for a transition begin to appear.
2. **Confirmed** — the confirmation conditions are satisfied for a minimum
   persistence period.

The active state changes only on a confirmed transition. A single short-lived
movement in one metric is not enough to move state. Persistence is measured in
**consecutive monthly points**; the engine is a **stateless replay** over the
derived metric history (nothing is persisted), so `current_state` and
`current_state_since` are derived deterministically. Persistence periods,
thresholds, and confirmation algorithms are configurable parameters, not
hard-coded into the view (HLD §14). See §5–§6 for the transition model and
status/tie handling these stages feed.

Implemented in `backend/services/market_cycle_engine.py`; consumes the derived
KPIs (`backend/services/derived_kpi_svc.py`).

## 12. State-identification Inputs

A market-cycle state can depend on (HLD §13):

1. Current level
2. Direction
3. Persistence
4. Relationship between metrics
5. Policy behaviour
6. Previous state

Reverse transitions are supported. A reverse transition may combine metric
direction with policy behaviour rather than a single absolute threshold (HLD
§5). The exact state and transition conditions are data or configuration;
they are evaluated by the state engine and are not fixed in this document.

## 13. Key References

* `doc/plans/Investment_Market_Cycle_HLD_And_View.md` §2–§6, §9, §13–§16 —
  behavioral intent.
* `doc/kpis/world.md`, `doc/derived/macro.md` — KPI definitions, sourcing tags,
  and the trend / real-interest-rate mathematics.
* `doc/datasources/macro.md` — provider series behind the world KPIs.
