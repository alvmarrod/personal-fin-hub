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


_PHASE_STATE_ORDER = (
    CycleState.LOW_REAL_RATES,
    CycleState.RISING_INFLATION,
    CycleState.HIKING_CYCLE,
    CycleState.HIGH_REAL_RATES,
    CycleState.FIRST_RATE_CUT,
    CycleState.CUTTING_CYCLE,
)


@dataclass(frozen=True)
class PhaseConditionResult:
    """One expected condition for a phase at one month (``state_engine.md`` §7)."""

    code: str
    met: bool
    known: bool = True
    held_months: int = 0
    required_months: int = 0
    value: object | None = None
    condition: dict | None = None

    def to_dict(self) -> dict:
        value = self.value.value if isinstance(self.value, TrendDirection) else self.value
        return {
            "code": self.code,
            "met": self.met,
            "known": self.known,
            "held_months": self.held_months,
            "required_months": self.required_months,
            "value": value,
            "condition": self.condition,
        }


@dataclass(frozen=True)
class PhaseMatch:
    """How well one phase matches the data at one month."""

    state: CycleState
    conditions: tuple[PhaseConditionResult, ...]

    @property
    def total(self) -> int:
        return len(self.conditions)

    @property
    def met(self) -> int:
        return sum(1 for condition in self.conditions if condition.met)

    @property
    def distance(self) -> int:
        return sum(1 for condition in self.conditions if not condition.met)

    def to_dict(self) -> dict:
        return {
            "state": {"id": int(self.state), "name": STATE_NAMES[self.state]},
            "distance": self.distance,
            "met": self.met,
            "total": self.total,
            "conditions": [condition.to_dict() for condition in self.conditions],
        }


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
    phase_determination: dict | None = None

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
            "phase_determination": self.phase_determination,
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


def _previous_month(month: MonthKey) -> MonthKey:
    year, month_number = month
    return (year - 1, 12) if month_number == 1 else (year, month_number - 1)


def _run_from_end(values: dict[MonthKey, object], end: MonthKey, predicate) -> int:
    """Count consecutive monthly values that satisfy ``predicate``, ending at ``end``."""
    if end not in values:
        return 0
    keys = sorted(values)
    position = keys.index(end)
    count = 0
    while position >= 0:
        month = keys[position]
        if not predicate(values[month]):
            break
        count += 1
        position -= 1
        if position >= 0 and keys[position] != _previous_month(month):
            break
    return count


def _threshold_met(value: object, op: str, threshold: float) -> bool:
    if not _is_number(value):
        return False
    if op == ">":
        return value > threshold
    if op == "<":
        return value < threshold
    if op == ">=":
        return value >= threshold
    if op == "<=":
        return value <= threshold
    raise ValueError(f"unsupported threshold operator: {op!r}")


def _threshold_condition(
    code: str,
    op: str,
    threshold: float,
    month: MonthKey,
    indexes: dict[str, dict[MonthKey, object]],
    *,
    require_held: bool = False,
    negate: bool = False,
    require_current: bool = False,
) -> PhaseConditionResult:
    values = indexes.get("real_interest_rate", {})
    value = values.get(month)
    current = _threshold_met(value, op, threshold)
    if not require_held:
        return PhaseConditionResult(
            code=code,
            met=current,
            known=_is_number(value),
            value=value if _is_number(value) else None,
            condition={"op": op, "target": threshold},
        )

    required = config.market_cycle_persistence["triggered"]
    held = _run_from_end(values, month, lambda candidate: _threshold_met(candidate, op, threshold))
    if negate:
        met = _is_number(value) and (current and held < required if require_current else held < required)
    else:
        met = current and held >= required
    return PhaseConditionResult(
        code=code,
        met=met,
        known=_is_number(value),
        held_months=held,
        required_months=required,
        value=value if _is_number(value) else None,
        condition={
            "op": "not_confirmed" if negate else "confirmed",
            "target": threshold,
            "window": required,
        },
    )


def _direction_condition(
    code: str,
    metric: str,
    target: TrendDirection,
    op: str,
    month: MonthKey,
    indexes: dict[str, dict[MonthKey, object]],
    *,
    require_held: bool = False,
    negate: bool = False,
    require_current: bool = False,
) -> PhaseConditionResult:
    values = indexes.get(metric, {})
    value = values.get(month)
    known = isinstance(value, TrendDirection)
    direction_value = value.value if isinstance(value, TrendDirection) else None
    current = known and ((value == target) if op == "==" else (value != target))
    if not require_held:
        return PhaseConditionResult(
            code=code,
            met=current,
            known=known,
            value=direction_value,
            condition={"op": op, "target": target.value},
        )

    required = config.market_cycle_persistence["triggered"]
    held = _run_from_end(values, month, lambda candidate: candidate == target)
    if negate:
        met = known and (value == target and held < required if require_current else held < required)
    else:
        met = known and value == target and held >= required
    return PhaseConditionResult(
        code=code,
        met=met,
        known=known,
        held_months=held,
        required_months=required,
        value=direction_value,
        condition={
            "op": "not_confirmed" if negate else "confirmed",
            "target": target.value,
            "window": required,
        },
    )


def _first_cut_at(month: MonthKey, indexes: dict[str, dict[MonthKey, object]]) -> tuple[bool, bool]:
    """Return (first-cut met, known) for a month, independent of the machine state."""
    values = indexes.get("policy_rate_trend", {})
    value = values.get(month)
    if value is None:
        return False, False
    if value != TrendDirection.DECREASING:
        return False, True
    keys = sorted(values)
    position = keys.index(month)
    if position == 0 or keys[position - 1] != _previous_month(month):
        return False, False
    return values[keys[position - 1]] != TrendDirection.DECREASING, True


def _first_cut_condition(month: MonthKey, indexes: dict[str, dict[MonthKey, object]]) -> PhaseConditionResult:
    met, known = _first_cut_at(month, indexes)
    value = indexes.get("policy_rate_trend", {}).get(month)
    return PhaseConditionResult(
        code="first_cut_detected",
        met=met,
        known=known,
        held_months=1 if met else 0,
        value=value.value if isinstance(value, TrendDirection) else None,
        condition={"op": "first_cut", "target": "decreasing"},
    )


def _phase_conditions(
    state: CycleState, month: MonthKey, indexes: dict[str, dict[MonthKey, object]]
) -> tuple[PhaseConditionResult, ...]:
    """The expected conditions for one phase (``state_engine.md`` §7)."""
    high = config.market_cycle_real_rate_high
    low = config.market_cycle_real_rate_low
    if state is CycleState.LOW_REAL_RATES:
        return (
            _threshold_condition("real_rates_low", "<", low, month, indexes),
            _direction_condition(
                "inflation_rate_trend_not_confirmed",
                "inflation_rate_trend",
                TrendDirection.INCREASING,
                "==",
                month,
                indexes,
                require_held=True,
                negate=True,
            ),
        )
    if state is CycleState.RISING_INFLATION:
        return (
            _direction_condition(
                "inflation_rate_trend_confirmed",
                "inflation_rate_trend",
                TrendDirection.INCREASING,
                "==",
                month,
                indexes,
                require_held=True,
            ),
            _direction_condition(
                "policy_rate_trend_not_increasing",
                "policy_rate_trend",
                TrendDirection.INCREASING,
                "!=",
                month,
                indexes,
            ),
        )
    if state is CycleState.HIKING_CYCLE:
        return (
            _direction_condition(
                "policy_rate_trend_increasing_confirmed",
                "policy_rate_trend",
                TrendDirection.INCREASING,
                "==",
                month,
                indexes,
                require_held=True,
            ),
            _threshold_condition("real_rates_not_high", "<=", high, month, indexes),
        )
    if state is CycleState.HIGH_REAL_RATES:
        return (
            _threshold_condition("real_rates_high", ">", high, month, indexes),
            _direction_condition(
                "policy_rate_trend_not_decreasing",
                "policy_rate_trend",
                TrendDirection.DECREASING,
                "!=",
                month,
                indexes,
            ),
        )
    if state is CycleState.FIRST_RATE_CUT:
        return (
            _direction_condition(
                "policy_rate_trend_decreasing_not_confirmed",
                "policy_rate_trend",
                TrendDirection.DECREASING,
                "==",
                month,
                indexes,
                require_held=True,
                negate=True,
                require_current=True,
            ),
            _threshold_condition("real_rates_high", ">", high, month, indexes),
            _first_cut_condition(month, indexes),
        )
    return (
        _direction_condition(
            "policy_rate_trend_decreasing_confirmed",
            "policy_rate_trend",
            TrendDirection.DECREASING,
            "==",
            month,
            indexes,
            require_held=True,
        ),
        _threshold_condition(
            "real_rates_low_not_confirmed",
            "<",
            low,
            month,
            indexes,
            require_held=True,
            negate=True,
        ),
    )


def _phase_match(state: CycleState, month: MonthKey, indexes: dict[str, dict[MonthKey, object]]) -> PhaseMatch:
    return PhaseMatch(state=state, conditions=_phase_conditions(state, month, indexes))


def _ranked_phase_matches(month: MonthKey, indexes: dict[str, dict[MonthKey, object]]) -> tuple[PhaseMatch, ...]:
    """Rank phases by distance, then met conditions, then state order."""
    matches = [_phase_match(state, month, indexes) for state in _PHASE_STATE_ORDER]
    return tuple(sorted(matches, key=lambda match: (match.distance, -match.met, int(match.state))))


def _initial_confidence(ranked: tuple[PhaseMatch, ...]) -> str:
    best = ranked[0]
    if best.distance > 0:
        return "low"
    if len(ranked) > 1 and ranked[1].distance == 0:
        return "medium"
    return "high"


def _phase_direction(source: CycleState, target: CycleState) -> str | None:
    steps = (int(target) - int(source)) % len(_PHASE_STATE_ORDER)
    if steps == 0:
        return None
    return "forward" if steps <= 3 else "backward"


def _month_iso(month: MonthKey) -> str:
    return date(month[0], month[1], 1).isoformat()


def evaluate(scope: str, conn: sqlite3.Connection | None = None) -> Status:
    """Evaluate the market-cycle status for a scope (stateless replay)."""
    conn = conn if conn is not None else derived_kpi_svc.get_db()
    months, indexes = _load(scope, conn)
    last = len(months) - 1
    required_months = config.market_cycle_persistence["triggered"]

    forced_state = config.market_cycle_initial_state
    auto_initial = forced_state not in range(1, 7)
    if auto_initial:
        initial_ranked = _ranked_phase_matches(months[0], indexes)
        initial_match = initial_ranked[0]
        initial_confidence = _initial_confidence(initial_ranked)
    else:
        initial_match = _phase_match(CycleState(forced_state), months[0], indexes)
        initial_confidence = "forced"

    warnings: list[dict] = []
    if auto_initial and initial_match.distance > 0:
        warnings.append(
            {
                "type": "initial_estimated",
                "month": _month_iso(months[0]),
                "best_state": int(initial_match.state),
                "reason": "closest_match",
                "confirmation_months": initial_match.met,
                "required_months": initial_match.total,
            }
        )

    state = initial_match.state
    since = months[0]
    corrections_enabled = auto_initial and config.market_cycle_phase_corrections_enabled
    candidate: CycleState | None = None
    candidate_months = 0

    for i in range(len(months)):
        triggered = [
            edge
            for edge in _outgoing(state)
            if _status_for(_held(edge, i, months, indexes, state)) is TransitionStatus.TRIGGERED
        ]
        if len(triggered) == 1:
            state = triggered[0].target
            since = months[i]
            candidate = None
            candidate_months = 0
            continue

        if not corrections_enabled:
            continue

        current_match = _phase_match(state, months[i], indexes)
        best_match = _ranked_phase_matches(months[i], indexes)[0]
        reachable = any(edge.target is best_match.state for edge in _outgoing(state))
        if best_match.state is state or reachable:
            candidate = None
            candidate_months = 0
            continue

        if best_match.distance == 0 and current_match.distance > 0:
            if candidate is best_match.state:
                candidate_months += 1
            else:
                candidate = best_match.state
                candidate_months = 1

            if candidate_months >= required_months:
                direction = _phase_direction(state, best_match.state)
                warnings.append(
                    {
                        "type": "phase_jump",
                        "month": _month_iso(months[i]),
                        "from_state": int(state),
                        "to_state": int(best_match.state),
                        "direction": direction,
                        "reason": "backward_without_direct_edge" if direction == "backward" else "no_enabled_edge",
                        "confirmation_months": candidate_months,
                        "required_months": required_months,
                    }
                )
                state = best_match.state
                since = months[i]
                candidate = None
                candidate_months = 0
        else:
            candidate = None
            candidate_months = 0

    last_match = _phase_match(state, months[last], indexes)
    last_best = _ranked_phase_matches(months[last], indexes)[0]
    last_reachable = any(edge.target is last_best.state for edge in _outgoing(state))
    if (
        corrections_enabled
        and last_best.state is not state
        and not last_reachable
        and last_best.distance < last_match.distance
    ):
        warnings.append(
            {
                "type": "phase_divergence",
                "month": _month_iso(months[last]),
                "machine_state": int(state),
                "best_state": int(last_best.state),
                "confirmation_months": candidate_months if candidate is last_best.state else 0,
                "required_months": required_months,
            }
        )

    details = _signal_details_at(last, months, indexes, state)

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

    status_rank = {
        TransitionStatus.TRIGGERED: 3,
        TransitionStatus.NEAR: 2,
        TransitionStatus.EMERGING: 1,
        TransitionStatus.INACTIVE: 0,
    }
    advanced = [transition for transition in active if transition.status is not TransitionStatus.INACTIVE]
    best_transition = max(
        advanced, key=lambda transition: (status_rank[transition.status], -transition.priority), default=None
    )

    current_payload = last_match.to_dict()
    current_payload.update(
        {
            "best_state": {"id": int(last_best.state), "name": STATE_NAMES[last_best.state]},
            "best_distance": last_best.distance,
            "best_met": last_best.met,
            "best_total": last_best.total,
            "best_conditions": [condition.to_dict() for condition in last_best.conditions],
            "phase_kind": "transition" if best_transition is not None else "state",
            "best_transition": best_transition.to_dict() if best_transition is not None else None,
        }
    )
    initial_payload = initial_match.to_dict()
    initial_payload.update({"month": _month_iso(months[0]), "confidence": initial_confidence})
    phase_determination = {
        "initial": initial_payload,
        "current": current_payload,
        "warnings": warnings,
    }

    return Status(
        scope=scope,
        current_state=state,
        current_state_since=date(since[0], since[1], 1),
        active_transitions=tuple(active),
        entry_signals=_entry_signal(state),
        ambiguous_confirmation=triggered_final >= 2,
        last_update=datetime.now(UTC),
        metrics=_metrics(last, months, indexes),
        phase_determination=phase_determination,
    )


def evaluate_all(conn: sqlite3.Connection | None = None) -> list[Status]:
    """Status for every computable scope."""
    conn = conn if conn is not None else derived_kpi_svc.get_db()
    return [evaluate(scope, conn=conn) for scope in scope_keys()]
