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
from typing import cast

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

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "status": self.status.value,
            "direction": self.direction,
            "priority": self.priority,
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

    def to_dict(self) -> dict:
        return {
            "scope": self.scope,
            "current_state": {"id": int(self.current_state), "name": STATE_NAMES[self.current_state]},
            "current_state_since": self.current_state_since.isoformat(),
            "active_transitions": [transition.to_dict() for transition in self.active_transitions],
            "entry_signals": self.entry_signals.value,
            "ambiguous_confirmation": self.ambiguous_confirmation,
            "last_update": self.last_update.isoformat(),
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
        for name in REQUIRED_INPUTS:
            indexes[name] = _index(derived_kpi_svc.derived_kpi(name, scope, conn=conn))
    except (derived_kpi_svc.DerivedNotDefined, world_kpi_svc.KpiNotDefined) as e:
        raise NotComputable(f"scope {scope!r} lacks required inputs: {e}") from e

    months: set[MonthKey] | None = None
    for index in indexes.values():
        keys = set(index)
        months = keys if months is None else months & keys
    if not months:
        raise NotComputable(f"scope {scope!r} has no months with all inputs")
    return sorted(months), indexes


def _signals_at(
    i: int,
    months: list[MonthKey],
    indexes: dict[str, dict[MonthKey, object]],
    state: CycleState,
) -> SignalSet:
    month = months[i]
    policy = indexes["policy_rate_trend"][month]
    inflation = indexes["inflation_rate_trend"][month]
    real_rate = cast(float, indexes["real_interest_rate"][month])
    real_trend = indexes["real_interest_rate_trend"][month]

    lookback = config.market_cycle_hikes_resumed_lookback_months
    prior = [indexes["policy_rate_trend"].get(months[j]) for j in range(max(0, i - lookback), i)]

    return SignalSet(
        inflation_rate_trend_increasing=inflation == TrendDirection.INCREASING,
        policy_rate_trend_increasing=policy == TrendDirection.INCREASING,
        policy_rate_trend_decreasing=policy == TrendDirection.DECREASING,
        real_rates_high=real_rate > config.market_cycle_real_rate_high,
        real_rates_low=real_rate < config.market_cycle_real_rate_low,
        real_rates_declining=real_trend == TrendDirection.DECREASING,
        real_rates_climbing=real_trend == TrendDirection.INCREASING,
        hikes_resumed=(
            policy == TrendDirection.INCREASING
            and any(prior_value is not None and prior_value != TrendDirection.INCREASING for prior_value in prior)
        ),
        hikes_stopped=policy != TrendDirection.INCREASING,
        cuts_stopped=policy != TrendDirection.DECREASING,
        first_cut_detected=(
            policy == TrendDirection.DECREASING and state in (CycleState.HIKING_CYCLE, CycleState.HIGH_REAL_RATES)
        ),
    )


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

    active: list[ActiveTransition] = []
    triggered_final = 0
    for edge in _outgoing(state):
        status = _status_for(_held(edge, last, months, indexes, state))
        if status is TransitionStatus.TRIGGERED:
            triggered_final += 1
        active.append(
            ActiveTransition(
                source=STATE_NAMES[edge.source],
                target=STATE_NAMES[edge.target],
                status=status,
                direction=edge.direction.value,
                priority=edge.priority,
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
    )


def evaluate_all(conn: sqlite3.Connection | None = None) -> list[Status]:
    """Status for every computable scope."""
    conn = conn if conn is not None else derived_kpi_svc.get_db()
    return [evaluate(scope, conn=conn) for scope in scope_keys()]
