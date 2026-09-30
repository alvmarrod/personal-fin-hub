"""Investment Market Cycle state engine.

Implements the contract in ``doc/systems/market_cycle/state_engine.md``: a
six-state machine driven by the derived macro KPIs (Phase 3), parameterized by
market scope.

The engine is **stateless**: it replays the machine over the metric history
(which the derived series carry), so ``current_state`` and
``current_state_since`` are derived deterministically and nothing is persisted.
Transitions confirm after a persistence period (consecutive months), and two or
more simultaneously ``Triggered`` edges hold state (the tie-hold rule).
"""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import IntEnum, StrEnum
from typing import TypeGuard, cast

from services import derived_kpi_svc, world_kpi_svc
from services.config import config
from services.derived_kpi_calc import DatedSeries, TrendDirection

MonthKey = tuple[int, int]

# Inputs the engine reads per scope (``state_engine.md`` §4).
REQUIRED_INPUTS = (
    "policy_rate_trend",
    "inflation_rate_trend",
    "real_interest_rate",
    "real_interest_rate_trend",
)
# Full input set used to decide which scopes are computable.
SCOPE_INPUTS = (
    "policy_rate",
    "policy_rate_trend",
    "inflation_rate",
    "inflation_rate_trend",
    "real_interest_rate",
    "real_interest_rate_trend",
)

# The eleven signals the engine evaluates (``state_engine.md`` §4), in a stable
# order. Each signal's display data (metric, value, condition, formula) is
# assembled by ``_probe`` and surfaced in the output so the view renders it
# without any economic logic of its own.
SIGNAL_CODES = (
    "inflation_rate_trend_increasing",
    "policy_rate_trend_increasing",
    "policy_rate_trend_decreasing",
    "real_rates_high",
    "real_rates_low",
    "real_rates_declining",
    "real_rates_climbing",
    "hikes_resumed",
    "hikes_stopped",
    "cuts_stopped",
    "first_cut_detected",
)

# A trend metric is the immediate slope of a level metric.
_TREND_LEVEL = {
    "policy_rate_trend": "policy_rate",
    "inflation_rate_trend": "inflation_rate",
    "real_interest_rate_trend": "real_interest_rate",
}

_REAL_RATE_STATE_NAMES = ("Hiking Cycle", "High Real Rates")


class NotComputable(Exception):
    """Raised when a scope lacks one or more required inputs."""


class CycleState(IntEnum):
    """The six fixed states (``state_engine.md`` §3)."""

    LOW_REAL_RATES = 1
    RISING_INFLATION = 2
    HIKING_CYCLE = 3
    HIGH_REAL_RATES = 4
    FIRST_RATE_CUT = 5
    CUTTING_CYCLE = 6


STATE_NAMES: dict[CycleState, str] = {
    CycleState.LOW_REAL_RATES: "Low Real Rates",
    CycleState.RISING_INFLATION: "Rising Inflation",
    CycleState.HIKING_CYCLE: "Hiking Cycle",
    CycleState.HIGH_REAL_RATES: "High Real Rates",
    CycleState.FIRST_RATE_CUT: "First Rate Cut",
    CycleState.CUTTING_CYCLE: "Cutting Cycle",
}


class EdgeDirection(StrEnum):
    FORWARD = "Forward"
    REVERSE = "Reverse"


class TransitionStatus(StrEnum):
    INACTIVE = "Inactive"
    EMERGING = "Emerging"
    NEAR = "Near"
    TRIGGERED = "Triggered"


class EntrySignal(StrEnum):
    NONE = "none"
    FAVOURABLE = "favourable"
    STRONG = "strong"


@dataclass(frozen=True)
class SignalSet:
    """Signals evaluated at one monthly point (``state_engine.md`` §4)."""

    inflation_rate_trend_increasing: bool
    policy_rate_trend_increasing: bool
    policy_rate_trend_decreasing: bool
    real_rates_high: bool
    real_rates_low: bool
    real_rates_declining: bool
    real_rates_climbing: bool
    hikes_resumed: bool
    hikes_stopped: bool
    cuts_stopped: bool
    first_cut_detected: bool

    def holds(self, names: tuple[str, ...]) -> bool:
        return all(getattr(self, name) for name in names)


@dataclass(frozen=True)
class Transition:
    """A legal edge (``state_engine.md`` §5)."""

    source: CycleState
    target: CycleState
    direction: EdgeDirection
    signals: tuple[str, ...]
    key: str
    priority: int = 0


# (source, target, direction, signals, config key) — §5, in table order.
_EDGE_DEFS = (
    (
        CycleState.LOW_REAL_RATES,
        CycleState.RISING_INFLATION,
        EdgeDirection.FORWARD,
        ("inflation_rate_trend_increasing",),
        "1->2",
    ),
    (
        CycleState.RISING_INFLATION,
        CycleState.HIKING_CYCLE,
        EdgeDirection.FORWARD,
        ("policy_rate_trend_increasing",),
        "2->3",
    ),
    (CycleState.HIKING_CYCLE, CycleState.HIGH_REAL_RATES, EdgeDirection.FORWARD, ("real_rates_high",), "3->4"),
    (CycleState.HIGH_REAL_RATES, CycleState.FIRST_RATE_CUT, EdgeDirection.FORWARD, ("first_cut_detected",), "4->5"),
    (
        CycleState.FIRST_RATE_CUT,
        CycleState.CUTTING_CYCLE,
        EdgeDirection.FORWARD,
        ("policy_rate_trend_decreasing",),
        "5->6",
    ),
    (CycleState.CUTTING_CYCLE, CycleState.LOW_REAL_RATES, EdgeDirection.FORWARD, ("real_rates_low",), "6->1"),
    (
        CycleState.CUTTING_CYCLE,
        CycleState.RISING_INFLATION,
        EdgeDirection.REVERSE,
        ("real_rates_declining", "cuts_stopped"),
        "6->2",
    ),
    (
        CycleState.FIRST_RATE_CUT,
        CycleState.HIGH_REAL_RATES,
        EdgeDirection.REVERSE,
        ("real_rates_high", "hikes_resumed"),
        "5->4",
    ),
    (
        CycleState.HIGH_REAL_RATES,
        CycleState.HIKING_CYCLE,
        EdgeDirection.REVERSE,
        ("hikes_resumed", "real_rates_climbing"),
        "4->3",
    ),
    (
        CycleState.HIKING_CYCLE,
        CycleState.RISING_INFLATION,
        EdgeDirection.REVERSE,
        ("hikes_stopped", "inflation_rate_trend_increasing"),
        "3->2",
    ),
)


@dataclass(frozen=True)
class ActiveTransition:
    """One outgoing transition of the current state (``state_engine.md`` §9)."""

    source: str
    target: str
    status: TransitionStatus
    direction: str
    priority: int
    held_months: int = 0
    required_months: int = 0
    signals: tuple[dict, ...] = ()

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "status": self.status.value,
            "direction": self.direction,
            "priority": self.priority,
            "held_months": self.held_months,
            "required_months": self.required_months,
            "signals": list(self.signals),
        }


@dataclass(frozen=True)
class Status:
    """The engine output for one scope (``state_engine.md`` §9)."""

    scope: str
    current_state: CycleState
    current_state_since: date
    active_transitions: tuple[ActiveTransition, ...]
    entry_signals: EntrySignal
    ambiguous_confirmation: bool
    last_update: datetime
    metrics: tuple[dict, ...] = ()

    def to_dict(self) -> dict:
        return {
            "scope": self.scope,
            "current_state": {"id": int(self.current_state), "name": STATE_NAMES[self.current_state]},
            "current_state_since": self.current_state_since.isoformat(),
            "active_transitions": [transition.to_dict() for transition in self.active_transitions],
            "entry_signals": self.entry_signals.value,
            "ambiguous_confirmation": self.ambiguous_confirmation,
            "last_update": self.last_update.isoformat(),
            "metrics": list(self.metrics),
        }


def _edges() -> tuple[Transition, ...]:
    edges: list[Transition] = []
    priority_overrides = config.market_cycle_priority
    for index, (source, target, direction, signals, key) in enumerate(_EDGE_DEFS, start=1):
        edges.append(Transition(source, target, direction, signals, key, priority_overrides.get(key, index)))
    return tuple(edges)


def _edge_enabled(edge: Transition) -> bool:
    if edge.direction is EdgeDirection.FORWARD:
        return True
    return config.market_cycle_reverse_edges_enabled.get(edge.key, True)


def _outgoing(state: CycleState) -> tuple[Transition, ...]:
    return tuple(edge for edge in _edges() if edge.source is state and _edge_enabled(edge))


def _month_key(value: date) -> MonthKey:
    return (value.year, value.month)


def _index(series: DatedSeries) -> dict[MonthKey, object]:
    return {_month_key(point.obs_date): point.value for point in series.points}


def _input_market_keys(name: str) -> set[str]:
    if name in derived_kpi_svc.REGISTRY:
        return set(derived_kpi_svc.market_keys(name))
    return set(world_kpi_svc.market_keys(name))


def scope_keys() -> list[str]:
    """Scopes with every required input wired (today: Spain/Eurozone only)."""
    markets: set[str] | None = None
    for name in SCOPE_INPUTS:
        keys = _input_market_keys(name)
        markets = keys if markets is None else markets & keys
    return sorted(markets or set())


def _load(scope: str, conn: sqlite3.Connection) -> tuple[list[MonthKey], dict[str, dict[MonthKey, object]]]:
    indexes: dict[str, dict[MonthKey, object]] = {}
    try:
        for name in SCOPE_INPUTS:
            indexes[name] = _index(derived_kpi_svc.resolve_monthly(name, scope, conn=conn))
    except (derived_kpi_svc.DerivedNotDefined, world_kpi_svc.KpiNotDefined) as e:
        raise NotComputable(f"scope {scope!r} lacks required inputs: {e}") from e

    # Computability is decided by the required inputs only (the levels are
    # supersets of their trend series, so they never shrink the month grid).
    months: set[MonthKey] | None = None
    for name in REQUIRED_INPUTS:
        keys = set(indexes[name])
        months = keys if months is None else months & keys
    if not months:
        raise NotComputable(f"scope {scope!r} has no months with all inputs")
    return sorted(months), indexes


def _num(indexes: dict[str, dict[MonthKey, object]], name: str, month: MonthKey) -> object:
    return indexes.get(name, {}).get(month)


def _is_number(value: object) -> TypeGuard[float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _level_change(
    level: str, i: int, months: list[MonthKey], indexes: dict[str, dict[MonthKey, object]]
) -> tuple[object, object, float | None]:
    curr = _num(indexes, level, months[i])
    prev = _num(indexes, level, months[i - 1]) if i > 0 else None
    delta = (curr - prev) if (_is_number(curr) and _is_number(prev)) else None
    return prev, curr, delta


def _slope_formula(metric: str, i: int, months: list[MonthKey], indexes: dict[str, dict[MonthKey, object]]) -> dict:
    level = _TREND_LEVEL[metric]
    prev, curr, delta = _level_change(level, i, months, indexes)
    return {"code": "slope_step", "inputs": [{"kpi": level, "value": curr, "prev_value": prev}], "delta": delta}


def _real_rate_formula(i: int, months: list[MonthKey], indexes: dict[str, dict[MonthKey, object]]) -> dict:
    month = months[i]
    return {
        "code": "real_rate",
        "inputs": [
            {"kpi": "policy_rate", "value": _num(indexes, "policy_rate", month)},
            {"kpi": "inflation_rate", "value": _num(indexes, "inflation_rate", month)},
        ],
        "result": _num(indexes, "real_interest_rate", month),
    }


def _direction_probe(
    code: str,
    metric: str,
    target: TrendDirection,
    op: str,
    i: int,
    months: list[MonthKey],
    indexes: dict[str, dict[MonthKey, object]],
    detail: bool,
) -> bool | dict:
    value = _num(indexes, metric, months[i])
    met = isinstance(value, TrendDirection) and ((value == target) if op == "==" else (value != target))
    if not detail:
        return met
    return {
        "code": code,
        "metric": metric,
        "kind": "direction",
        "met": met,
        "value": value.value if isinstance(value, TrendDirection) else None,
        "unit": None,
        "condition": {"op": op, "target": target.value},
        "formula": _slope_formula(metric, i, months, indexes),
    }


def _threshold_probe(
    code: str,
    op: str,
    threshold: float,
    i: int,
    months: list[MonthKey],
    indexes: dict[str, dict[MonthKey, object]],
    detail: bool,
) -> bool | dict:
    month = months[i]
    value = _num(indexes, "real_interest_rate", month)
    met = _is_number(value) and (value > threshold if op == ">" else value < threshold)
    if not detail:
        return met
    return {
        "code": code,
        "metric": "real_interest_rate",
        "kind": "threshold",
        "met": bool(met),
        "value": value,
        "unit": "%",
        "condition": {"op": op, "target": threshold},
        "formula": _real_rate_formula(i, months, indexes),
    }


def _hikes_resumed_probe(
    i: int, months: list[MonthKey], indexes: dict[str, dict[MonthKey, object]], detail: bool
) -> bool | dict:
    policy = _num(indexes, "policy_rate_trend", months[i])
    lookback = config.market_cycle_hikes_resumed_lookback_months
    prior = [indexes["policy_rate_trend"].get(months[j]) for j in range(max(0, i - lookback), i)]
    rising = policy == TrendDirection.INCREASING
    paused = any(value is not None and value != TrendDirection.INCREASING for value in prior)
    met = rising and paused
    if not detail:
        return met
    rising_part = cast(
        "dict",
        _direction_probe(
            "policy_rate_trend_increasing",
            "policy_rate_trend",
            TrendDirection.INCREASING,
            "==",
            i,
            months,
            indexes,
            True,
        ),
    )
    rising_part.pop("code", None)
    paused_part = {
        "metric": "policy_rate_trend",
        "kind": "history",
        "met": paused,
        "value": None,
        "unit": None,
        "condition": {"op": "none_within", "target": "increasing", "window": lookback},
        "formula": None,
    }
    return {
        "code": "hikes_resumed",
        "metric": "policy_rate_trend",
        "kind": "combination",
        "met": met,
        "value": None,
        "unit": None,
        "condition": None,
        "formula": None,
        "parts": [rising_part, paused_part],
    }


def _first_cut_probe(
    i: int,
    months: list[MonthKey],
    indexes: dict[str, dict[MonthKey, object]],
    state: CycleState,
    detail: bool,
) -> bool | dict:
    policy = _num(indexes, "policy_rate_trend", months[i])
    in_cutting_state = state in (CycleState.HIKING_CYCLE, CycleState.HIGH_REAL_RATES)
    met = policy == TrendDirection.DECREASING and in_cutting_state
    if not detail:
        return met
    cut_part = cast(
        "dict",
        _direction_probe(
            "policy_rate_trend_decreasing",
            "policy_rate_trend",
            TrendDirection.DECREASING,
            "==",
            i,
            months,
            indexes,
            True,
        ),
    )
    cut_part.pop("code", None)
    state_part = {
        "metric": "state",
        "kind": "state",
        "met": in_cutting_state,
        "value": STATE_NAMES[state],
        "unit": None,
        "condition": {"op": "in", "target": list(_REAL_RATE_STATE_NAMES)},
        "formula": None,
    }
    return {
        "code": "first_cut_detected",
        "metric": "policy_rate_trend",
        "kind": "combination",
        "met": met,
        "value": None,
        "unit": None,
        "condition": None,
        "formula": None,
        "parts": [cut_part, state_part],
    }


def _probe(
    code: str,
    i: int,
    months: list[MonthKey],
    indexes: dict[str, dict[MonthKey, object]],
    state: CycleState,
    detail: bool,
) -> bool | dict:
    """Evaluate one signal at month ``i``; a bool, or its display dict when ``detail``."""
    if code == "inflation_rate_trend_increasing":
        return _direction_probe(
            code, "inflation_rate_trend", TrendDirection.INCREASING, "==", i, months, indexes, detail
        )
    if code == "policy_rate_trend_increasing":
        return _direction_probe(code, "policy_rate_trend", TrendDirection.INCREASING, "==", i, months, indexes, detail)
    if code == "policy_rate_trend_decreasing":
        return _direction_probe(code, "policy_rate_trend", TrendDirection.DECREASING, "==", i, months, indexes, detail)
    if code == "real_rates_declining":
        return _direction_probe(
            code, "real_interest_rate_trend", TrendDirection.DECREASING, "==", i, months, indexes, detail
        )
    if code == "real_rates_climbing":
        return _direction_probe(
            code, "real_interest_rate_trend", TrendDirection.INCREASING, "==", i, months, indexes, detail
        )
    if code == "hikes_stopped":
        return _direction_probe(code, "policy_rate_trend", TrendDirection.INCREASING, "!=", i, months, indexes, detail)
    if code == "cuts_stopped":
        return _direction_probe(code, "policy_rate_trend", TrendDirection.DECREASING, "!=", i, months, indexes, detail)
    if code == "real_rates_high":
        return _threshold_probe(code, ">", config.market_cycle_real_rate_high, i, months, indexes, detail)
    if code == "real_rates_low":
        return _threshold_probe(code, "<", config.market_cycle_real_rate_low, i, months, indexes, detail)
    if code == "hikes_resumed":
        return _hikes_resumed_probe(i, months, indexes, detail)
    if code == "first_cut_detected":
        return _first_cut_probe(i, months, indexes, state, detail)
    raise KeyError(f"unknown signal: {code!r}")


def _signals_at(
    i: int,
    months: list[MonthKey],
    indexes: dict[str, dict[MonthKey, object]],
    state: CycleState,
) -> SignalSet:
    return SignalSet(**{code: cast("bool", _probe(code, i, months, indexes, state, False)) for code in SIGNAL_CODES})


def _signal_details_at(
    i: int,
    months: list[MonthKey],
    indexes: dict[str, dict[MonthKey, object]],
    state: CycleState,
) -> dict[str, dict]:
    return {code: cast("dict", _probe(code, i, months, indexes, state, True)) for code in SIGNAL_CODES}


_METRIC_ROWS: tuple[tuple[str, str], ...] = (
    ("inflation_rate", "level"),
    ("inflation_rate_trend", "direction"),
    ("policy_rate", "level"),
    ("policy_rate_trend", "direction"),
    ("real_interest_rate", "level"),
    ("real_interest_rate_trend", "direction"),
)


def _metric_row(
    name: str, kind: str, i: int, months: list[MonthKey], indexes: dict[str, dict[MonthKey, object]]
) -> dict:
    value = _num(indexes, name, months[i])
    if kind == "direction":
        return {
            "kpi": name,
            "kind": "direction",
            "value": value.value if isinstance(value, TrendDirection) else None,
            "unit": None,
            "prev_value": None,
            "delta": None,
            "formula": _slope_formula(name, i, months, indexes),
        }
    prev, curr, delta = _level_change(name, i, months, indexes)
    return {
        "kpi": name,
        "kind": "level",
        "value": curr,
        "unit": "%",
        "prev_value": prev,
        "delta": delta,
        "formula": _real_rate_formula(i, months, indexes) if name == "real_interest_rate" else None,
    }


def _metrics(i: int, months: list[MonthKey], indexes: dict[str, dict[MonthKey, object]]) -> tuple[dict, ...]:
    return tuple(_metric_row(name, kind, i, months, indexes) for name, kind in _METRIC_ROWS)


def _held(
    edge: Transition, i: int, months: list[MonthKey], indexes: dict[str, dict[MonthKey, object]], state: CycleState
) -> int:
    count = 0
    j = i
    while j >= 0:
        if edge.signals and _signals_at(j, months, indexes, state).holds(edge.signals):
            count += 1
            j -= 1
        else:
            break
    return count


def _status_for(held: int) -> TransitionStatus:
    thresholds = config.market_cycle_persistence
    if held >= thresholds["triggered"]:
        return TransitionStatus.TRIGGERED
    if held >= thresholds["near"]:
        return TransitionStatus.NEAR
    if held >= thresholds["emerging"]:
        return TransitionStatus.EMERGING
    return TransitionStatus.INACTIVE


def _entry_signal(state: CycleState) -> EntrySignal:
    if state is CycleState.HIGH_REAL_RATES:
        return EntrySignal.FAVOURABLE
    if state is CycleState.FIRST_RATE_CUT:
        return EntrySignal.STRONG
    return EntrySignal.NONE


def evaluate(scope: str, conn: sqlite3.Connection | None = None) -> Status:
    """Evaluate the market-cycle status for a scope (stateless replay)."""
    conn = conn if conn is not None else derived_kpi_svc.get_db()
    months, indexes = _load(scope, conn)
    last = len(months) - 1

    state = CycleState(config.market_cycle_initial_state)
    since = months[0]
    for i in range(len(months)):
        triggered = [
            edge
            for edge in _outgoing(state)
            if _status_for(_held(edge, i, months, indexes, state)) is TransitionStatus.TRIGGERED
        ]
        if len(triggered) == 1:
            state = triggered[0].target
            since = months[i]

    details = _signal_details_at(last, months, indexes, state)
    required_months = config.market_cycle_persistence["triggered"]

    active: list[ActiveTransition] = []
    triggered_final = 0
    for edge in _outgoing(state):
        held = _held(edge, last, months, indexes, state)
        status = _status_for(held)
        if status is TransitionStatus.TRIGGERED:
            triggered_final += 1
        active.append(
            ActiveTransition(
                source=STATE_NAMES[edge.source],
                target=STATE_NAMES[edge.target],
                status=status,
                direction=edge.direction.value,
                priority=edge.priority,
                held_months=held,
                required_months=required_months,
                signals=tuple(details[code] for code in edge.signals),
            )
        )
    active.sort(key=lambda transition: transition.priority)

    return Status(
        scope=scope,
        current_state=state,
        current_state_since=date(since[0], since[1], 1),
        active_transitions=tuple(active),
        entry_signals=_entry_signal(state),
        ambiguous_confirmation=triggered_final >= 2,
        last_update=datetime.now(UTC),
        metrics=_metrics(last, months, indexes),
    )


def evaluate_all(conn: sqlite3.Connection | None = None) -> list[Status]:
    """Status for every computable scope."""
    conn = conn if conn is not None else derived_kpi_svc.get_db()
    return [evaluate(scope, conn=conn) for scope in scope_keys()]
