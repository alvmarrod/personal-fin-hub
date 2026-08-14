"""Fiscal-rule P&L display-currency conversion engine.

Native realized P&L (``calculations.md`` §11.1) is rule-independent; fiscal
rules only define how the display-currency conversion is applied (§16). This
module implements the FIFO lot engine (§10.1) and the ``PnlRule`` registry
(§16.2), plus the closest-in-time rate fallback (§16.4).
"""

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from services.currency_svc import PairNotFound, get_rate


@dataclass(frozen=True)
class PnlLot:
    """One purchase lot in a FIFO queue (§10.1)."""

    quantity: float
    unit_cost: float
    buy_date: datetime


@dataclass(frozen=True)
class NativeSale:
    """A sell transaction with the FIFO lots it consumed (§11.1)."""

    transaction_id: int
    portfolio_asset_id: int
    market_code: str | None
    ticker: str | None
    name: str | None
    sell_date: datetime
    sell_date_raw: str
    sell_quantity: float
    sell_price: float
    sell_total: float
    currency: str
    payment_currency: str | None
    fx_rate: float | None
    lots: tuple[PnlLot, ...]
    cost_basis: float
    realized_pl: float


@dataclass(frozen=True)
class FifoResult:
    """Result of walking the buy/sell ledger chronologically."""

    sales: list[NativeSale]
    remaining: dict[int, tuple[PnlLot, ...]]


@dataclass(frozen=True)
class RateLookup:
    """A resolved rate and whether it fell back to a neighboring date."""

    rate: float
    timestamp: datetime
    fallback: bool


@dataclass(frozen=True)
class RateFallbackInfo:
    """One fallback occurrence, aggregated before being exposed via the API."""

    currency: str
    scope: str
    reason: str
    requested_date: str | None
    used_timestamp: str | None


class NoRateError(Exception):
    """No rate data exists at all for the requested pair."""


class RateProvider(Protocol):
    def historical(self, code: str, base_code: str, at: datetime) -> RateLookup: ...

    def latest(self, code: str, base_code: str) -> RateLookup: ...


class CurrencyServiceRateProvider:
    """RateProvider backed by the stored ``currencies`` table."""

    def historical(self, code: str, base_code: str, at: datetime) -> RateLookup:
        try:
            response = get_rate(code, base_code, at)
        except PairNotFound as exc:
            raise NoRateError(f"No rate data for ({code}, {base_code})") from exc
        return RateLookup(
            rate=response.rate,
            timestamp=response.timestamp,
            fallback=_normalize(response.timestamp) != _normalize(at),
        )

    def latest(self, code: str, base_code: str) -> RateLookup:
        try:
            response = get_rate(code, base_code)
        except PairNotFound as exc:
            raise NoRateError(f"No rate data for ({code}, {base_code})") from exc
        return RateLookup(rate=response.rate, timestamp=response.timestamp, fallback=False)


@dataclass(frozen=True)
class ConvertedSale:
    """A sale converted to the display currency under a fiscal rule."""

    value: float
    fallbacks: tuple[RateFallbackInfo, ...]


def _normalize(value: datetime) -> datetime:
    """Drop timezone info so stored rates and transaction timestamps compare by date."""
    return value.replace(tzinfo=None)


def _parse_ts(value: str) -> datetime:
    if value.endswith("Z"):
        return datetime.fromisoformat(value[:-1] + "+00:00")
    return datetime.fromisoformat(value)


def compute_fifo(rows: list[dict]) -> FifoResult:
    """Walk buy/sell rows chronologically and produce consumed lots per sell.

    Rows must be ordered by ``portfolio_asset_id, timestamp, id`` and carry
    ``quantity``, ``unit_price``, ``total_value``, ``currency``,
    ``payment_currency``, ``fx_rate``.
    """
    sales: list[NativeSale] = []
    queues: dict[int, deque[PnlLot]] = {}

    for r in rows:
        qty = r["quantity"]
        total_val = r["total_value"]
        if qty is None or total_val is None or qty <= 0:
            continue

        if r["type"] == "INVESTMENT_BUY":
            buy_date = _parse_ts(r["timestamp"])
            buy_queue = queues.setdefault(r["portfolio_asset_id"], deque())
            buy_queue.append(PnlLot(quantity=qty, unit_cost=total_val / qty, buy_date=buy_date))
            continue
        if r["type"] != "INVESTMENT_SELL":
            continue

        sell_queue = queues.get(r["portfolio_asset_id"])
        if not sell_queue:
            continue

        consumed: list[PnlLot] = []
        remaining_to_consume = qty
        while remaining_to_consume > 0 and sell_queue:
            lot = sell_queue[0]
            take = min(lot.quantity, remaining_to_consume)
            consumed.append(PnlLot(quantity=take, unit_cost=lot.unit_cost, buy_date=lot.buy_date))
            remaining_to_consume -= take
            if take >= lot.quantity:
                sell_queue.popleft()
            else:
                sell_queue[0] = PnlLot(quantity=lot.quantity - take, unit_cost=lot.unit_cost, buy_date=lot.buy_date)

        if not consumed:
            continue

        cost_basis = sum(lot.quantity * lot.unit_cost for lot in consumed)
        unit_price = r["unit_price"] if r["unit_price"] is not None else total_val / qty
        sales.append(
            NativeSale(
                transaction_id=r["transaction_id"],
                portfolio_asset_id=r["portfolio_asset_id"],
                market_code=r["market_code"],
                ticker=r["ticker"],
                name=r["name"],
                sell_date=_parse_ts(r["timestamp"]),
                sell_date_raw=r["timestamp"],
                sell_quantity=qty,
                sell_price=unit_price,
                sell_total=total_val,
                currency=r["currency"],
                payment_currency=r.get("payment_currency"),
                fx_rate=r.get("fx_rate"),
                lots=tuple(consumed),
                cost_basis=round(cost_basis, 4),
                realized_pl=round(total_val - cost_basis, 4),
            )
        )

    remaining = {aid: tuple(queue) for aid, queue in queues.items()}
    return FifoResult(sales=sales, remaining=remaining)


def rule_for_locale(locale: str) -> str:
    """Map a locale (e.g. ``es-ES``) to a rule key (§16.2 default rule)."""
    if not locale:
        return "default"
    language = locale.split("-")[0].lower()
    if language == "es":
        return "spain"
    if language == "ja":
        return "japan"
    return "default"


RULE_NAMES: dict[str, str] = {
    "spain": "Spain (constant sale-day rate)",
    "japan": "Japan (FX-aware)",
    "default": "Default (copy of spain)",
    "latest": "Legacy / current behavior",
}


def _proceeds_in_display(
    sale: NativeSale,
    provider: RateProvider,
    display_currency: str,
    at: datetime,
) -> tuple[float, list[RateFallbackInfo]]:
    """Convert the sale's proceeds to the display currency (§16.2).

    If the sell records ``payment_currency`` + ``fx_rate`` the proceeds are
    realized in ``payment_currency``; otherwise they stay in the asset currency.
    """
    fallbacks: list[RateFallbackInfo] = []
    if sale.payment_currency and sale.payment_currency != sale.currency and sale.fx_rate is not None:
        source = sale.payment_currency
        proceeds = sale.sell_total * sale.fx_rate
    else:
        source = sale.currency
        proceeds = sale.sell_total

    if source == display_currency:
        return proceeds, fallbacks

    try:
        lookup = provider.historical(source, display_currency, at)
    except NoRateError:
        fallbacks.append(RateFallbackInfo(source, "realized_pl", "no-rate", at.date().isoformat(), None))
        return proceeds, fallbacks
    if lookup.fallback:
        fallbacks.append(
            RateFallbackInfo(
                source, "realized_pl", "closest-in-time", at.date().isoformat(), lookup.timestamp.isoformat()
            )
        )
    return proceeds * lookup.rate, fallbacks


def _lookup_rate(
    source: str,
    display_currency: str,
    at: datetime,
    scope: str,
    provider: RateProvider,
    fallbacks: list[RateFallbackInfo],
) -> float:
    """Resolve ``source → display`` at ``at``, recording fallbacks (§16.4)."""
    if source == display_currency:
        return 1.0
    try:
        lookup = provider.historical(source, display_currency, at)
    except NoRateError:
        fallbacks.append(RateFallbackInfo(source, scope, "no-rate", at.date().isoformat(), None))
        return 1.0
    if lookup.fallback:
        fallbacks.append(
            RateFallbackInfo(source, scope, "closest-in-time", at.date().isoformat(), lookup.timestamp.isoformat())
        )
    return lookup.rate


def convert_sale(
    sale: NativeSale,
    rule_key: str,
    provider: RateProvider,
    display_currency: str,
) -> ConvertedSale:
    """Convert one native sale to the display currency under ``rule_key`` (§16.2)."""
    fallbacks: list[RateFallbackInfo] = []

    if rule_key == "japan":
        proceeds_display, proceeds_fallbacks = _proceeds_in_display(sale, provider, display_currency, sale.sell_date)
        fallbacks.extend(proceeds_fallbacks)
        cost_display = 0.0
        for lot in sale.lots:
            rate = _lookup_rate(sale.currency, display_currency, lot.buy_date, "realized_pl", provider, fallbacks)
            cost_display += lot.quantity * lot.unit_cost * rate
        return ConvertedSale(proceeds_display - cost_display, tuple(fallbacks))

    if rule_key == "latest":
        if sale.payment_currency and sale.payment_currency != sale.currency and sale.fx_rate is not None:
            source = sale.payment_currency
            proceeds = sale.sell_total * sale.fx_rate
        else:
            source = sale.currency
            proceeds = sale.sell_total
        proceeds_display = proceeds
        if source != display_currency:
            try:
                proceeds_display = proceeds * provider.latest(source, display_currency).rate
            except NoRateError:
                fallbacks.append(RateFallbackInfo(source, "realized_pl", "no-rate", None, None))
        cost_display = sale.cost_basis
        if sale.currency != display_currency:
            try:
                cost_display = sale.cost_basis * provider.latest(sale.currency, display_currency).rate
            except NoRateError:
                fallbacks.append(RateFallbackInfo(sale.currency, "realized_pl", "no-rate", None, None))
        return ConvertedSale(proceeds_display - cost_display, tuple(fallbacks))

    proceeds_display, proceeds_fallbacks = _proceeds_in_display(sale, provider, display_currency, sale.sell_date)
    fallbacks.extend(proceeds_fallbacks)
    rate = _lookup_rate(sale.currency, display_currency, sale.sell_date, "realized_pl", provider, fallbacks)
    return ConvertedSale(proceeds_display - sale.cost_basis * rate, tuple(fallbacks))
