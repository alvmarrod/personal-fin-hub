# Investment Market Cycle View

## 1. Purpose

The **Investment Market Cycle View** is a new view within an existing web application.

Its purpose is to provide a compact visual representation of the current position within an inflation and interest-rate market cycle.

The view is based on a finite set of predefined market states connected by explicit transitions. It should communicate:

* the current market-cycle state;
* the direction in which the cycle is evolving;
* transitions that are approaching or beginning;
* the key macroeconomic metrics supporting the current state;
* historically relevant entry points;
* the conditions required for moving between states.

The view must remain **country- and data-source agnostic**. The HLD defines what information is required and how it affects the state machine, but does not define where that information comes from or how it is calculated for a particular country or geographic scope.

---

## 2. Core Concept

The market cycle is represented as a finite state machine.

The primary cycle contains six states:

1. **Low Real Rates**
2. **Rising Inflation**
3. **Hiking Cycle**
4. **High Real Rates**
5. **First Rate Cut**
6. **Cutting Cycle**

The normal forward progression is:

**Low Real Rates → Rising Inflation → Hiking Cycle → High Real Rates → First Rate Cut → Cutting Cycle → Low Real Rates**

The states themselves are fixed. The system must not skip states or arbitrarily jump between unrelated states.

However, transitions are not necessarily one-way.

A transition may exist in both directions when market conditions can legitimately cause the cycle to reverse. Such reverse transitions are part of the underlying state machine even if they are visually de-emphasised or hidden from the primary UI.

---

## 3. Terminology

The implementation must distinguish clearly between nominal and real interest rates.

### Inflation Rate

The rate at which the general price level is changing.

### Nominal Interest Rate

The observed policy interest rate set by the relevant monetary authority.

References to:

* rate hikes;
* rate cuts;
* hiking cycles;
* cutting cycles;

refer to changes in the **nominal policy interest rate**.

### Real Interest Rate

The interest rate adjusted for inflation.

Real interest rates are a separate metric from the nominal policy rate and are used to determine whether the environment is characterised by **Low Real Rates** or **High Real Rates**.

### Rate Direction

The direction of the nominal policy rate:

* increasing;
* stable;
* decreasing.

### Inflation Direction

The direction of inflation:

* increasing;
* stable;
* decreasing.

The exact calculation methodology and source of these metrics are outside the scope of this HLD.

---

## 4. State Model

### 4.1 Low Real Rates

Represents an environment where real interest rates are low.

Relevant characteristics:

* real interest rates are low;
* subsequent historical returns have tended to be lower when starting from low real rates.

This state is not itself defined by nominal rates being low. A nominal rate may be relatively high while the real rate remains low if inflation is sufficiently high.

#### Typical transition

**Low Real Rates → Rising Inflation**

Triggered when inflation begins to increase sufficiently to establish an inflationary trend.

---

### 4.2 Rising Inflation

Represents an environment in which inflation is increasing and monetary policy has not yet fully transitioned into a sustained hiking cycle.

Relevant characteristics:

* inflation is increasing;
* inflationary pressure is becoming established;
* the monetary authority may be approaching or beginning policy tightening.

#### Typical transition

**Rising Inflation → Hiking Cycle**

Triggered when the nominal policy rate begins a sustained sequence of increases.

---

### 4.3 Hiking Cycle

Represents an active period of nominal interest-rate increases.

Relevant characteristics:

* nominal policy rates are increasing;
* inflation may remain elevated;
* historical equity risk premiums have generally been lower during hiking cycles than during cutting cycles.

This state represents the principal tightening phase of the cycle.

#### Typical transition

**Hiking Cycle → High Real Rates**

Triggered when real interest rates become sufficiently high, indicating that the tightening process has materially changed the real-rate environment.

---

### 4.4 High Real Rates

Represents an environment where real interest rates are high.

Relevant characteristics:

* real interest rates are elevated;
* the initial real-rate level is historically associated with higher subsequent five-year returns than periods starting from low real rates.

This state is important because it represents a potentially attractive entry condition based on the starting level of real rates.

#### Typical transition

**High Real Rates → First Rate Cut**

Triggered by the first reduction in the nominal policy rate following the hiking cycle.

---

### 4.5 First Rate Cut

Represents the transition point at which the monetary authority makes the first nominal rate cut following a hiking cycle.

This is a distinct state rather than simply part of the Cutting Cycle because the first cut represents a particularly important historical signal.

Historical analysis indicates that investment after the first rate cut has produced higher returns and higher risk-adjusted returns than investment after the first rate hike.

#### Typical transition

**First Rate Cut → Cutting Cycle**

Triggered when the first rate cut is followed by continued monetary easing.

---

### 4.6 Cutting Cycle

Represents an active period of nominal interest-rate reductions.

Relevant characteristics:

* nominal policy rates are decreasing;
* historical equity risk premiums have been higher during cutting cycles;
* risk-adjusted returns have historically been higher during cutting cycles than during hiking cycles.

The state may eventually transition back towards the beginning of the cycle.

#### Typical transition

**Cutting Cycle → Low Real Rates**

Triggered when the easing cycle has sufficiently reduced real interest rates.

---

## 5. Reverse and Exceptional Transitions

The state machine must explicitly support reverse transitions.

These transitions are not necessarily displayed as prominent paths in the UI, but they must exist in the underlying model so that the system does not have to force real-world conditions into an incorrect forward progression.

## Example: Cutting Cycle → Rising Inflation

A cutting cycle may be interrupted if inflation begins to accelerate again.

A possible transition sequence is:

**Cutting Cycle → Rising Inflation**

The transition should be supported by multiple signals rather than a single metric.

Example transition conditions:

1. **Real interest rates begin to decline**, partly because inflation is increasing.
2. **Nominal rate cuts stop**, indicating that the easing cycle is no longer continuing.

The first signal indicates deterioration in the real-rate environment.

The second signal provides confirmation that monetary easing has stopped.

This illustrates an important design principle:

> A transition may be triggered by a combination of metric direction and policy behaviour rather than by a single absolute threshold.

Other reverse transitions may be defined in the same manner where economically meaningful.

---

## 6. Transition Model

Each transition should have its own definition.

A transition consists of:

* **Source state**
* **Target state**
* **Trigger conditions**
* **Confirmation conditions**
* **Transition status**
* **Priority**
* **Direction**

A transition can have one of several statuses:

| Status        | Meaning                                                    |
| ------------- | ---------------------------------------------------------- |
| **Inactive**  | Conditions for the transition are not currently present    |
| **Emerging**  | Initial conditions are beginning to appear                 |
| **Near**      | Most required conditions are satisfied                     |
| **Triggered** | Conditions required for the transition have been confirmed |

The UI does not need to expose all of these technical distinctions, but the underlying model should support them.

---

## 7. Transition Animation

The primary cycle should be visually simple.

The currently active state is highlighted.

Transitions that are not currently relevant remain static.

When a transition begins to become likely:

* the transition indicator may change colour;
* the connecting arrow may become highlighted;
* the arrow may begin a subtle pulse or blink animation.

The animation represents **an approaching transition**, not that the transition has already occurred.

When the transition is confirmed:

* the current state changes;
* the target state becomes active;
* the transition animation stops.

Animation should be subtle and continuous enough to attract attention without making the entire view visually noisy.

---

## 8. State Colours

Colours communicate state and transition significance rather than representing individual countries or assets.

Recommended semantic scheme:

| Visual state       | Meaning                                                 |
| ------------------ | ------------------------------------------------------- |
| **Neutral / grey** | Inactive or distant state                               |
| **Amber / yellow** | Transition emerging or conditions approaching           |
| **Green**          | Historically favourable entry environment               |
| **Red**            | Historically unfavourable entry environment             |
| **Blue**           | Informational / neutral transition or active monitoring |

The exact colour palette is a UI implementation detail.

The same semantic meaning must be preserved consistently throughout the view.

---

## 9. Entry Signals

The widget should visually distinguish between **market-cycle state** and **investment-entry signal**.

The two historically relevant entry conditions identified by the underlying research are:

### High Real Rates

Indicates that the starting real-rate environment is high.

The historical evidence associates higher initial real rates with higher subsequent returns over the analysed five-year periods.

This should be represented as a **favourable entry condition**.

### First Rate Cut

Indicates that the first nominal policy-rate cut following a hiking cycle has occurred.

Historical analysis associates this point with higher subsequent returns and higher risk-adjusted returns compared with entering after the first rate hike.

This should be represented as a **strong entry signal**.

These indicators should not be interpreted as deterministic predictions.

---

## 10. Key Metrics

The view should expose a compact set of supporting metrics.

At minimum:

| Metric                  | Purpose                                                          |
| ----------------------- | ---------------------------------------------------------------- |
| **Inflation Rate**      | Measures current inflation level                                 |
| **Inflation Trend**     | Determines whether inflation is increasing, stable or decreasing |
| **Nominal Policy Rate** | Determines hiking/cutting behaviour                              |
| **Nominal Rate Trend**  | Identifies hikes, cuts or stability                              |
| **Real Interest Rate**  | Determines the real-rate environment                             |
| **Real Rate Trend**     | Helps identify transitions between real-rate states              |

Additional metrics may be provided by the data layer, but the core widget should remain focused on the metrics required to understand the state machine.

> **Metric registry**: each metric above maps to a KPI in
> `doc/kpis/world.md` (§2 Macro KPI Table): `policy_rate`
> (Nominal Policy Rate), `policy_rate_trend` (Nominal Rate Trend),
> `inflation_rate` (Inflation Rate), `inflation_rate_trend` (Inflation
> Trend), `real_interest_rate` (Real Interest Rate),
> `real_interest_rate_trend` (Real Rate Trend). Derived values (trend
> direction, real interest rate, persistence and confirmation) are computed
> per `doc/derived/macro.md`.

---

## 11. Widget Layout

The primary visual component should resemble a simplified circular or horizontal state-machine diagram.

Each state should contain only:

* state number;
* state name;
* active/inactive visual status.

Example:

**① Low Real Rates → ② Rising Inflation → ③ Hiking Cycle → ④ High Real Rates → ⑤ First Rate Cut → ⑥ Cutting Cycle**

The detailed economic explanation should not be placed inside the state nodes.

Supporting information can be displayed underneath the cycle:

* current metric values;
* metric direction;
* current state;
* approaching transition;
* entry signal;
* last update.

This keeps the cycle itself readable at a glance.

---

## 12. Legend

The legend should explain the visual language used by the widget.

Recommended entries:

* **Active state** — current position in the cycle.
* **Inactive state** — state not currently active.
* **Emerging transition** — transition conditions beginning to appear.
* **Approaching transition** — transition is close to being confirmed.
* **Entry condition** — historically favourable starting condition.
* **Strong entry signal** — historically significant transition point.

The legend should remain compact and should not explain the underlying economics.

---

## 13. State Determination

The state engine should not rely exclusively on absolute values.

A state can depend on:

1. **Current level**
2. **Direction**
3. **Persistence**
4. **Relationship between metrics**
5. **Policy behaviour**
6. **Previous state**

For example, the distinction between nominal and real rates is essential.

A high nominal interest rate does not automatically mean **High Real Rates**.

Likewise, a low nominal interest rate does not automatically mean **Low Real Rates**.

The state engine must evaluate the real-rate metric separately.

---

## 14. Transition Confirmation

Where practical, transitions should use a two-stage mechanism:

### Stage 1 — Emerging

The initial conditions for a transition begin to appear.

The UI highlights the corresponding transition using a subtle animation.

### Stage 2 — Confirmed

The required confirmation conditions are satisfied.

The system moves the active state to the target state and removes the transition warning.

This prevents the UI from changing state because of a single short-lived movement in one metric.

The exact persistence periods, thresholds and confirmation algorithms are implementation details and should be configurable rather than hard-coded into the view.

---

## 15. Geographic / Market Scope

The HLD intentionally does not define a specific country, central bank, currency or data provider.

The same state machine should support:

* an individual country;
* a monetary region;
* a global aggregate;
* another supported market scope.

The data layer is responsible for providing the required normalized metrics.

The view only consumes the resulting market indicators and state-machine status.

---

## 16. Separation of Responsibilities

### Data Layer

Responsible for:

* obtaining source data (sourcing tags per `doc/kpis/world.md`);
* calculating or normalizing required metrics (derived metrics per
  `doc/derived/macro.md`);
* determining metric trends (per `doc/derived/macro.md`);
* providing historical observations.

### State Engine

Full contract: `doc/systems/market_cycle/state_engine.md`.

Responsible for:

* evaluating state conditions;
* evaluating transition conditions;
* tracking the current state;
* tracking emerging transitions;
* confirming state changes.

### View

Responsible for:

* displaying the current state;
* displaying transitions;
* displaying metric values;
* applying semantic colours;
* displaying entry signals;
* animating emerging transitions.

The view must not contain country-specific economic logic.

---

## 17. Design Principle

The widget should answer three questions immediately:

> **Where are we?**

Current market-cycle state.

> **Where are we going?**

The next transition and its current status.

> **Is this historically an interesting point to enter?**

Current entry condition, if applicable.

The detailed economic model remains behind the widget, while the visual representation provides a compact real-time interpretation of the state machine.

The model is based on historical relationships and should therefore be presented as a **market-cycle monitoring framework**, not as a deterministic forecasting system.
