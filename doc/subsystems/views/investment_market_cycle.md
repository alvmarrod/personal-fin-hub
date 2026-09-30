# View: Investment Market Cycle (`/investment-market-cycle`)

> The inflation / interest-rate market-cycle widget. Component and design
> conventions live in `doc/subsystems/UI.md`; the engine contract in
> `doc/systems/market_cycle/state_engine.md`; metric registry in
> `doc/kpis/world.md` §2; derived math in `doc/derived/macro.md`;
> plan of record `doc/plans/Investment_Market_Cycle_HLD_And_View.md`.

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
per-market rows in `doc/kpis/world.md` §2 and the engine scopes:

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
* **Metrics** — omitted in this version. The endpoint returns the engine status
  object only (no per-metric readings), and a snapshot of the current values is
  not informative enough on its own, so the metrics table is intentionally not
  rendered. It can be added once the endpoint exposes the readings.
* **Approaching transition** — the highest-status outgoing transition with
  its status (`Emerging` / `Near` / `Triggered`), used as a one-line summary.
* **Last update** — the latest evaluation timestamp.

The legend (plan §12) lists: active state, inactive state, emerging
transition, approaching transition, entry condition, strong entry signal.

## Data Loading

The page consumes the engine status object via the implemented endpoint
(`doc/subsystems/api_endpoints.md`):

`GET /analytics/investment-market-cycle?scope=spain-eurozone`

`scope` is a lowercase key (`usa`, `japan`, `spain-eurozone`, `global`); the
selector disables scopes whose sources are not wired yet.

The response is the engine output contract
(`doc/systems/market_cycle/state_engine.md` §9):

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

`inflation_rate` is not yet sourced for every market — Japan CPI has no
datasource yet (`doc/kpis/world.md` §3). For a scope that has no sourced data,
the endpoint returns **400**; the page renders a "missing data sources" warning
banner and a "no data for this scope yet" panel in place of the diagram and
metrics. The panel is informational and carries no animation. Scopes that are
not wired yet are also shown disabled in the scope selector.

## Components Needed

| Component | Type | API |
|-----------|------|-----|
| `MarketCycleDiagram` | New (`StateDiagram.svelte`) | `GET /analytics/investment-market-cycle?scope=` |
| `ScopeSelector` | New (Select with disabled options) | refetch on change |
| `MetricCard` (compact) | Omitted this version | — (endpoint returns no metric readings) |
| `EntrySignalBadge` | New (Badge) | same response |
| `AmbiguousConfirmationChip` | New (Badge) | `ambiguous_confirmation` flag |
| `Legend` | New (`MarketCycleLegend.svelte`, static) | no API |
| `RefreshButton` | Existing pattern | trigger refetch |

## API Dependencies

* `GET /analytics/investment-market-cycle?scope=` — the engine status object
  (implemented; `doc/subsystems/api_endpoints.md`).

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
configuration surface (`doc/systems/market_cycle/state_engine.md`
§10).
