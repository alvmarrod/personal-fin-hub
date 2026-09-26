# View: Investment Market Cycle (`/investment-market-cycle`)

> The inflation / interest-rate market-cycle widget. Component and design
> conventions live in `doc/subsystems/UI.md`; the engine contract in
> `doc/subsystems/investment_market_cycle_state_engine.md`; metric registry in
> `doc/subsystems/kpi_catalog.md` §2; derived math in `doc/calculations.md`
> §18; plan of record `doc/plans/Investment_Market_Cycle_HLD_And_View.md`.

## Layout

```text
+------------------------------------------------------------------------+
| [☰]  Investment Market Cycle    [USA ▾]  [⟳ Refresh]   [last update]  |  ← header: title + scope + refresh
+----------------+-------------------------------------------------------+
| Legend         |  Investment Market Cycle diagram                      |
| (compact list) |      ① → ② → ③ → ④ → ⑤ → ⑥ → ① ...                 |
|                |  active state highlighted; approaching edges animate  |
+----------------+-------------------------------------------------------+
| Entry signal: favourable (★)      Ambiguous confirmation chip (if any) |
| Current state: High Real Rates (since 2026-01-15)                      |
|                                                                        |
| Metric                  Level                Direction                 |
| Inflation rate          3.2 %               decreasing                |
| Nominal policy rate     4.0 %               stable                    |
| Real interest rate      -0.8 %              decreasing                |
| ----------------------------------------------------------------------|
| Approaching transition: High Real Rates → First Rate Cut (emerging)    |
+------------------------------------------------------------------------+
```

The diagram sits above the supporting panel. The state nodes carry only a
number, a name, and the active/inactive status (plan §11). The economic
explanation stays out of the nodes and in the supporting panel.

## Scope Selector

A selector in the header line picks the market scope. Values match the
per-market rows in `doc/subsystems/kpi_catalog.md` §2 and the engine scopes:

* USA
* Japan
* Spain/Eurozone
* Global aggregate

Changing the scope refetches the status object for that scope.

## State Diagram

The diagram is a simplified horizontal or circular representation of the
six-state machine (plan §2, §11):

**① Low Real Rates → ② Rising Inflation → ③ Hiking Cycle → ④ High Real Rates → ⑤ First Rate Cut → ⑥ Cutting Cycle → ① Low Real Rates**

* Nodes show the state number and name. Inactive nodes render in grey.
* The active node is highlighted (plan §12: "Active state").
* Forward edges are drawn prominently.
* Reverse edges are drawn de-emphasized (plan §5, §16). They exist in the
  model, but the UI keeps them visually muted.
* The diagram reflects the engine output only (plan §16). It contains no
  country or data-source logic.

### Semantic colours

Colours communicate state and transition significance (plan §8). The mapping
below is a proposed default, derived from the plan's semantic scheme and the
entry-signal research (plan §9). It can be revised later.

| State | Colour |
|---|---|
| 1 Low Real Rates | Red (unfavourable entry environment) |
| 2 Rising Inflation | Amber (transitional; tightening approaching) |
| 3 Hiking Cycle | Blue (informational / active monitoring) |
| 4 High Real Rates | Green (favourable entry condition) |
| 5 First Rate Cut | Green with ★ (strong entry signal) |
| 6 Cutting Cycle | Green (historically more favourable) |

Inactive states render grey regardless of their semantic colour (plan §8).

### Animation

An outgoing edge of the active state animates when its transition status is
`Emerging`, `Near`, or `Triggered` (plan §7, engine §6):

* `Emerging` — subtle pulse or blink on the connecting arrow.
* `Near` — stronger highlight.
* `Triggered` — the animation continues while the transition waits for
  settlement.

The animation represents an approaching transition, not a completed one
(plan §7). When the engine commits, the target state becomes active and the
edge stops animating. By construction the fired edge leaves the current
state's outgoing set, so the animation stops automatically.

Two `Triggered` transitions animate simultaneously during the engine's
tie-hold (engine §6). The `ambiguous_confirmation` flag renders a small chip,
"transition analysis paused", next to the diagram.

## Supporting Panel

Underneath the diagram (plan §11):

* **Current state** — name and date since the state was committed.
* **Entry signal** — a badge separate from the state node (plan §9):
  * `strong` (First Rate Cut) — strong entry signal, ★.
  * `favourable` (High Real Rates) — favourable entry condition.
  * `none` — no signal.
  The badge is not a deterministic prediction (plan §17). The widget is a
  monitoring framework, not a forecast.
* **Metrics** — the six readings: inflation rate, nominal policy rate, and
  real interest rate, each with level and direction (`increasing` /
  `stable` / `decreasing`). Values and directions come from the engine input
  metrics in `doc/subsystems/kpi_catalog.md` §2 and `doc/calculations.md`
  §18.1, §18.2.
* **Approaching transition** — the highest-status outgoing transition with
  its status (`Emerging` / `Near` / `Triggered`), used as a one-line summary.
* **Last update** — the latest evaluation timestamp.

The legend (plan §12) lists: active state, inactive state, emerging
transition, approaching transition, entry condition, strong entry signal.

## Data Loading

The page consumes the engine status object via a planned endpoint:

`GET /analytics/investment-market-cycle?scope=USA`

The response is the engine output contract
(`doc/subsystems/investment_market_cycle_state_engine.md` §9):

```json
{
  "scope": "USA",
  "current_state": { "id": 4, "name": "High Real Rates" },
  "current_state_since": "2026-01-15",
  "active_transitions": [
    { "source": "High Real Rates", "target": "First Rate Cut",
      "status": "Triggered", "direction": "Forward", "priority": 3 }
  ],
  "entry_signals": "favourable",
  "ambiguous_confirmation": false,
  "last_update": "2026-09-25T10:00:00Z"
}
```

* The object loads on page mount and on every scope change.
* A refresh button refetches the current scope manually.
* Macro data is monthly. No background polling is required for the first
  version. A later version may add an auto-refresh interval.

### Empty state

`inflation_rate` is `<external>` for every market until the macro data
pipeline exists (`doc/subsystems/kpi_catalog.md` §3). Until that pipeline
lands, a scope that has no sourced data renders a "no data for this scope
yet" panel in place of the diagram and metrics. The panel is informational
and carries no animation.

## Components Needed

| Component | Type | API |
|-----------|------|-----|
| `MarketCycleDiagram` | New | `GET /analytics/investment-market-cycle?scope=` |
| `ScopeSelector` | New | refetch on change |
| `MetricCard` (compact) | Existing | same response |
| `EntrySignalBadge` | New | same response |
| `AmbiguousConfirmationChip` | New | `ambiguous_confirmation` flag |
| `Legend` | New (static) | no API |
| `RefreshButton` | Existing pattern | trigger refetch |

## API Dependencies

* `GET /analytics/investment-market-cycle?scope=` — the engine status object
  (planned endpoint, not yet implemented).

## Localization

All visible labels go through `t()` with keys in both `en.ts` and `es.ts`
(`bun run validate-i18n` gate, see `doc/subsystems/UI.md`):

* the page title, scope names, and the six state names;
* the status values (`Emerging`, `Near`, `Triggered`);
* the entry-signal labels (`none`, `favourable`, `strong`);
* the legend and the empty-state message.

## Implementation Note

The view must not contain country-specific or economic logic (plan §16). It
renders the engine output and the metric values as received. All thresholds,
persistence periods, and transition conditions live in the engine
configuration surface (`doc/subsystems/investment_market_cycle_state_engine.md`
§10).
