from bisect import bisect_right
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from db import queries
from db.analytics_queries import (
    get_all_prices,
    get_buy_sell_transactions,
    get_cash_balance_by_currency,
    get_cash_by_currency_history,
    get_cash_by_entity_raw,
    get_cash_flow_raw,
    get_dividend_transactions,
    get_dividends_raw,
    get_entity_total_cash_by_currency_as_of,
    get_fees_raw,
    get_holdings_by_entity_raw,
    get_holdings_raw,
    get_income_by_source_raw,
    get_latest_prices,
    get_latest_transaction_prices,
    get_net_positions_as_of,
    get_taxes_raw,
    get_total_cash_by_currency_as_of,
)
from db.connection import get_db
from models import (
    AllocationLine,
    CashFlowLine,
    CashFlowSummaryWithRates,
    DashboardSummary,
    DividendLine,
    FeeSummaryLine,
    FeeTaxSummary,
    HistoricalValuePoint,
    HoldingByEntityLine,
    HoldingLine,
    IncomeBySourceLine,
    IncomeBySourceWithRates,
    PerformanceRateFallback,
    PerformanceSummary,
    RateMetadata,
    RealizedGainLine,
    TaxablePnlFiscalYear,
    TaxablePnlFiscalYearExtended,
    TaxablePnlItem,
    TaxablePnlSummary,
    TaxablePnlSummaryExtended,
    TaxSummaryLine,
)
from models.enums import AssetClass, AssetType, Layer, TrackingMode
from services.currency_svc import PairNotFound, get_rate, is_stale_rate
from services.pnl_rules import (
    FISCAL_YEAR_START,
    CurrencyServiceRateProvider,
    NoRateError,
    RateFallbackInfo,
    TaxBracket,
    _lookup_rate,
    _parse_ts,
    compute_fifo,
    convert_dividend,
    convert_sale,
    fiscal_year_bounds,
    get_tax_model,
    rule_for_locale,
)


class AnalyticsError(Exception):
    pass


def _get_rate_metadata(currencies: list[str], display_currency: str) -> RateMetadata | None:
    """Get rate metadata for the given currencies converted to display_currency.

    Returns None if no conversion is needed (all currencies are display_currency)
    or if no rates are available.
    """
    if not currencies or display_currency is None:
        return None

    rates = {}
    latest_timestamp = None

    for cur in set(currencies):
        if cur == display_currency:
            continue
        try:
            rate_response = get_rate(cur, display_currency)
            rates[cur] = rate_response.rate
            if latest_timestamp is None or rate_response.timestamp > latest_timestamp:
                latest_timestamp = rate_response.timestamp
        except PairNotFound:
            pass

    if not rates:
        return None

    latest_iso = latest_timestamp.isoformat() if latest_timestamp else ""
    # Staleness verdict for the "Exchange rates from …" banner: closing-date
    # rates less than two business days old are the normal case (§16.4).
    stale = False
    if latest_timestamp is not None:
        stale = is_stale_rate(latest_timestamp.date(), datetime.now(UTC).date())

    return RateMetadata(rates=rates, latest_timestamp=latest_iso, stale=stale)


def get_dashboard(display_currency: str = "USD") -> DashboardSummary:
    holdings = get_holdings()
    conn = get_db()
    cash_by_currency = get_cash_balance_by_currency(conn)

    needed_currencies = {h.currency_code for h in holdings if h.current_value is not None}
    needed_currencies.update(row["currency"] for row in cash_by_currency)

    rate_cache: dict[str, float] = {}
    for cur in needed_currencies:
        if cur == display_currency:
            continue
        try:
            rate_cache[cur] = get_rate(cur, display_currency).rate
        except PairNotFound:
            pass

    def convert(value: float, cur: str) -> float:
        if cur == display_currency or cur not in rate_cache:
            return value
        return value * rate_cache[cur]

    total_value = 0.0
    total_invested = 0.0
    num = 0
    for h in holdings:
        if h.current_value is not None:
            total_value += convert(h.current_value, h.currency_code)
        total_invested += convert(h.total_cost, h.currency_code)
        num += 1

    realized_gains = get_realized_gains()
    needed_currencies.update(g.currency for g in realized_gains)
    rate_cache.clear()
    for cur in needed_currencies:
        if cur == display_currency:
            continue
        try:
            rate_cache[cur] = get_rate(cur, display_currency).rate
        except PairNotFound:
            pass

    unrealized_pl = sum(
        convert(h.current_value, h.currency_code) - convert(h.total_cost, h.currency_code)
        for h in holdings
        if h.current_value is not None
    )
    realized_pl = sum(convert(g.realized_pl, g.currency) for g in realized_gains)

    total_cash = 0.0
    for row in cash_by_currency:
        total_cash += convert(row["balance"], row["currency"])

    total_return = total_value + total_cash - total_invested
    return_pct = (total_return / total_invested * 100) if total_invested > 0 else 0.0
    return DashboardSummary(
        display_currency=display_currency,
        total_portfolio_value=round(total_value + total_cash, 4),
        total_invested=round(total_invested, 4),
        investment_value=round(total_value, 4),
        cash_balance=round(total_cash, 4),
        total_return=round(total_return, 4),
        total_return_pct=round(return_pct, 4),
        num_holdings=num,
        unrealized_pl=round(unrealized_pl, 4),
        realized_pl=round(realized_pl, 4),
    )


def _compute_fifo_cost_basis(conn) -> dict[int, dict[str, float]]:
    """Compute FIFO cost basis per portfolio_asset_id from all buy/sell transactions.

    Uses the shared FIFO lot engine (§10.1/§10.2): remaining cost is the sum of
    the remaining lots' ``quantity × unit_cost``.
    """
    from db.analytics_queries import get_buy_sell_transactions

    result = compute_fifo(get_buy_sell_transactions(conn))
    return {
        aid: {
            "qty": round(sum(lot.quantity for lot in lots), 4),
            "cost": round(sum(lot.quantity * lot.unit_cost for lot in lots), 4),
        }
        for aid, lots in result.remaining.items()
    }


def get_holdings(conn=None) -> list[HoldingLine]:
    if conn is None:
        conn = get_db()
    raw = get_holdings_raw(conn)
    if not raw:
        return []

    prices = get_latest_prices(conn)
    price_map = {p["market_code"]: p["price"] for p in prices}
    price_as_of_map = {p["market_code"]: p["timestamp"] for p in prices}

    # Fallback: latest unit_price from INVESTMENT_BUY transactions per market_code
    tx_fallback = {r["market_code"]: r["unit_price"] for r in get_latest_transaction_prices(conn)}
    tx_fallback_as_of = {r["market_code"]: r["timestamp"] for r in get_latest_transaction_prices(conn)}

    fifo_map = _compute_fifo_cost_basis(conn)

    enriched = []
    total_value = 0.0

    for row in raw:
        net_qty = row["total_bought_qty"] - row["total_sold_qty"]
        fifo = fifo_map.get(row["portfolio_asset_id"])
        if fifo and fifo["qty"] > 0:
            total_cost = fifo["cost"]
            avg_cost = total_cost / fifo["qty"]
        else:
            total_cost = 0.0
            avg_cost = None

        if row["tracking_mode"] == "manual":
            from db.queries import get_latest_manual_value  # noqa: F811

            mv = get_latest_manual_value(conn, row["portfolio_asset_id"])
            current_value = mv["value"] if mv else row.get("current_value_manual")
            if current_value is None:
                price_source = "none"
                price_as_of = None
            else:
                price_source = "manual"
                price_as_of = mv["effective_date"] if mv else None
        elif net_qty > 0 and row["market_code"] in price_map:
            current_value = net_qty * price_map[row["market_code"]]
            price_source = "market-api"
            price_as_of = price_as_of_map.get(row["market_code"])
        elif net_qty > 0 and row["market_code"] in tx_fallback:
            current_value = net_qty * tx_fallback[row["market_code"]]
            price_source = "transaction-fallback"
            price_as_of = tx_fallback_as_of.get(row["market_code"])
        else:
            current_value = None
            if row["market_code"] in price_map:
                price_source = "market-api"
                price_as_of = price_as_of_map.get(row["market_code"])
            else:
                price_source = "none"
                price_as_of = None

        if current_value is not None:
            total_value += current_value

        enriched.append(
            {
                "row": row,
                "net_qty": net_qty,
                "total_cost": total_cost,
                "avg_cost": avg_cost,
                "current_value": current_value,
                "price_source": price_source,
                "price_as_of": price_as_of,
            }
        )

    holdings = []
    for item in enriched:
        row = item["row"]
        current_value = item["current_value"]

        unrealized_pl = None
        unrealized_pl_pct = None
        if current_value is not None and item["avg_cost"] is not None and item["net_qty"] > 0:
            cost_basis = item["avg_cost"] * item["net_qty"]
            unrealized_pl = current_value - cost_basis
            if cost_basis > 0:
                unrealized_pl_pct = (current_value / cost_basis - 1) * 100

        weight_pct = (current_value / total_value * 100) if total_value > 0 and current_value is not None else 0.0

        ac = row.get("asset_class")
        holdings.append(
            HoldingLine(
                portfolio_asset_id=row["portfolio_asset_id"],
                market_code=row["market_code"],
                ticker=row.get("ticker"),
                name=row.get("name"),
                asset_type=AssetType(row["asset_type"]),
                asset_class=AssetClass(ac) if ac else None,
                layer=Layer(row["layer"]) if row.get("layer") else None,
                currency_code=row["currency_code"],
                tracking_mode=TrackingMode(row["tracking_mode"]),
                net_quantity=item["net_qty"],
                avg_cost=item["avg_cost"],
                total_cost=item["total_cost"],
                latest_price=price_map.get(row["market_code"]),
                current_value=current_value,
                unrealized_pl=round(unrealized_pl, 4) if unrealized_pl is not None else None,
                unrealized_pl_pct=round(unrealized_pl_pct, 4) if unrealized_pl_pct is not None else None,
                weight_pct=round(weight_pct, 4),
                price_source=item["price_source"],
                price_as_of=item["price_as_of"],
            )
        )

    return holdings


def get_asset_allocation(dimension: str = "layer", display_currency: str | None = None) -> list[AllocationLine]:
    valid = ("layer", "asset_type", "currency", "asset_class", "entity")
    if dimension not in valid:
        raise AnalyticsError(f"Invalid dimension '{dimension}'. Must be one of: {', '.join(valid)}")

    if dimension == "entity":
        return _get_allocation_by_entity(display_currency)

    holdings = get_holdings()
    conn = get_db()
    cash_by_currency = get_cash_balance_by_currency(conn)

    # Build rate cache for currency conversion
    rate_cache: dict[str, float] = {}
    if display_currency:
        all_currencies = {h.currency_code for h in holdings if h.current_value is not None}
        all_currencies.update(row["currency"] for row in cash_by_currency)
        for cur in all_currencies:
            if cur == display_currency:
                continue
            try:
                rate_cache[cur] = get_rate(cur, display_currency).rate
            except PairNotFound:
                pass

    def convert(value: float, cur: str) -> float:
        if not display_currency or cur == display_currency or cur not in rate_cache:
            return value
        return value * rate_cache[cur]

    total_value = (
        sum(convert(h.current_value, h.currency_code) for h in holdings if h.current_value is not None)
        if holdings
        else 0.0
    )
    groups: dict[str, float] = defaultdict(float)

    for h in holdings or []:
        if h.current_value is None:
            continue
        converted_value = convert(h.current_value, h.currency_code)
        if dimension == "layer":
            key = h.layer.value if h.layer else "unspecified"
        elif dimension == "asset_type":
            key = h.asset_type.value
        elif dimension == "asset_class":
            key = h.asset_class.value if h.asset_class else "UNSPECIFIED"
        else:
            key = h.currency_code
        groups[key] += converted_value

    if dimension == "asset_class":
        for row in cash_by_currency:
            converted_cash = convert(row["balance"], row["currency"])
            if converted_cash > 0:
                groups["CASH"] += converted_cash
                total_value += converted_cash

    result = []
    for category, value_abs in sorted(groups.items(), key=lambda x: -x[1]):
        pct = (value_abs / total_value * 100) if total_value > 0 else 0.0
        result.append(
            AllocationLine(
                category=category,
                dimension=dimension,
                value_pct=round(pct, 4),
                value_abs=round(value_abs, 4),
            )
        )

    return result


def _get_allocation_by_entity(display_currency: str | None = None) -> list[AllocationLine]:
    conn = get_db()
    inv_rows = get_holdings_by_entity_raw(conn)
    cash_rows = get_cash_by_entity_raw(conn)

    # Build rate cache for currency conversion
    rate_cache: dict[str, float] = {}
    if display_currency:
        all_currencies = set()
        for r in inv_rows:
            if r.get("currency_code"):
                all_currencies.add(r["currency_code"])
        for r in cash_rows:
            if r.get("currency"):
                all_currencies.add(r["currency"])
        for cur in all_currencies:
            if cur == display_currency:
                continue
            try:
                rate_cache[cur] = get_rate(cur, display_currency).rate
            except PairNotFound:
                pass

    def convert(value: float, cur: str) -> float:
        if not display_currency or cur == display_currency or cur not in rate_cache:
            return value
        return value * rate_cache[cur]

    groups: dict[str, float] = defaultdict(float)
    for r in inv_rows:
        key = r["entity_name"] or "Unassigned"
        groups[key] += convert(r["current_value"], r.get("currency_code", ""))

    for r in cash_rows:
        key = r["entity_name"]
        groups[key] += convert(r["cash_balance"], r.get("currency", ""))

    total = sum(groups.values()) or 1.0
    result = []
    for category, value_abs in sorted(groups.items(), key=lambda x: -x[1]):
        result.append(
            AllocationLine(
                category=category,
                dimension="entity",
                value_pct=round(value_abs / total * 100, 4),
                value_abs=round(value_abs, 4),
            )
        )
    return result


def get_holdings_by_entity(display_currency: str | None = None) -> list[HoldingByEntityLine]:
    conn = get_db()
    inv_rows = get_holdings_by_entity_raw(conn)
    cash_rows = get_cash_by_entity_raw(conn)

    # Build rate cache for currency conversion
    rate_cache: dict[str, float] = {}
    if display_currency:
        all_currencies = set()
        for r in inv_rows:
            if r.get("currency_code"):
                all_currencies.add(r["currency_code"])
        for r in cash_rows:
            if r.get("currency"):
                all_currencies.add(r["currency"])
        for cur in all_currencies:
            if cur == display_currency:
                continue
            try:
                rate_cache[cur] = get_rate(cur, display_currency).rate
            except PairNotFound:
                pass

    def convert(value: float, cur: str) -> float:
        if not display_currency or cur == display_currency or cur not in rate_cache:
            return value
        return value * rate_cache[cur]

    result: list[HoldingByEntityLine] = []
    seen: dict[tuple[int | None, str | None, str], float] = defaultdict(float)

    for r in inv_rows:
        key = (r["entity_id"], r["asset_class"], r.get("currency_code", ""))
        seen[key] += convert(r["current_value"], r.get("currency_code", ""))

    for r in cash_rows:
        key = (r["entity_id"], "CASH", r.get("currency", ""))
        seen[key] += convert(r["cash_balance"], r.get("currency", ""))

    for (eid, ac, cur), val in sorted(seen.items(), key=lambda x: -x[1]):
        name = None
        for r in inv_rows:
            if r["entity_id"] == eid:
                name = r["entity_name"]
                break
        if name is None:
            for r in cash_rows:
                if r["entity_id"] == eid:
                    name = r["entity_name"]
                    break
        result.append(
            HoldingByEntityLine(
                entity_id=eid if eid != -1 else None,
                entity_name=name,
                asset_class=ac,
                current_value=round(val, 4),
                currency=cur or None,
            )
        )

    return result


def _compute_fee_amount(nature: str, fixed_amount: float, percentage: float, tx_total: float) -> float:
    if nature == "FIXED":
        return fixed_amount
    elif nature == "PERCENTAGE":
        return percentage * tx_total / 100.0
    elif nature == "BOTH":
        return fixed_amount + percentage * tx_total / 100.0
    elif nature == "MIN":
        return min(fixed_amount, percentage * tx_total / 100.0)
    return 0.0


def get_income_by_source(
    group_by: str = "month",
    start_date: str | None = None,
    end_date: str | None = None,
    display_currency: str | None = None,
) -> IncomeBySourceWithRates:
    if group_by not in ("day", "week", "month", "quarter", "year"):
        raise AnalyticsError(f"Invalid group_by '{group_by}'. Must be one of: day, week, month, quarter, year")
    conn = get_db()
    rows = get_income_by_source_raw(conn, group_by, start_date, end_date)

    # Build rate cache if display_currency is provided
    rate_cache: dict[str, float] = {}
    currencies = [r["currency"] for r in rows]

    if display_currency:
        for cur in set(currencies):
            if cur == display_currency:
                continue
            try:
                rate_response = get_rate(cur, display_currency)
                rate_cache[cur] = rate_response.rate
            except PairNotFound:
                pass

    def convert(value: float, cur: str) -> float:
        if not display_currency or cur == display_currency or cur not in rate_cache:
            return value
        return value * rate_cache[cur]

    result = [
        IncomeBySourceLine(
            period=r["period"],
            entity_id=r["entity_id"],
            entity_name=r["entity_name"],
            type=r["type"],
            income_category=r["income_category"],
            currency=r["currency"],
            total_value=round(convert(r["total_value"], r["currency"]), 4),
            count=r["count"],
        )
        for r in rows
    ]

    rate_info = _get_rate_metadata(currencies, display_currency) if display_currency else None

    return IncomeBySourceWithRates(data=result, rate_info=rate_info)


def get_cash_flow(
    group_by: str = "month",
    start_date: str | None = None,
    end_date: str | None = None,
    display_currency: str | None = None,
) -> CashFlowSummaryWithRates:
    if group_by not in ("day", "week", "month", "quarter", "year"):
        raise AnalyticsError(f"Invalid group_by '{group_by}'. Must be one of: day, week, month, quarter, year")
    conn = get_db()
    rows = get_cash_flow_raw(conn, group_by, start_date, end_date)

    # Build rate cache if display_currency is provided
    rate_cache: dict[str, float] = {}
    currencies = [r["currency"] for r in rows]

    if display_currency:
        for cur in set(currencies):
            if cur == display_currency:
                continue
            try:
                rate_response = get_rate(cur, display_currency)
                rate_cache[cur] = rate_response.rate
            except PairNotFound:
                pass

    def convert(value: float, cur: str) -> float:
        if not display_currency or cur == display_currency or cur not in rate_cache:
            return value
        return value * rate_cache[cur]

    lines = [
        CashFlowLine(
            period=r["period"],
            type=r["type"],
            total_value=round(convert(r["total_value"], r["currency"]), 4),
            count=r["count"],
            currency=r["currency"],
        )
        for r in rows
    ]
    total_in = sum(convert(r["total_value"], r["currency"]) for r in rows if r["type"] in ("INCOME", "INVESTMENT_SELL"))
    total_out = sum(
        convert(r["total_value"], r["currency"]) for r in rows if r["type"] in ("MONEY_OUT", "INVESTMENT_BUY")
    )

    rate_info = _get_rate_metadata(currencies, display_currency) if display_currency else None

    return CashFlowSummaryWithRates(
        lines=lines,
        total_in=round(total_in, 4),
        total_out=round(total_out, 4),
        net=round(total_in - total_out, 4),
        rate_info=rate_info,
    )


def get_projected_income(
    start_date: str | None = None,
    end_date: str | None = None,
    display_currency: str | None = None,
) -> IncomeBySourceWithRates:
    """Get projected income from schedules, optionally converted to display_currency."""
    from db.queries import get_all_entities, get_all_schedules

    conn = get_db()
    schedules = get_all_schedules(conn)

    # Filter for income schedules
    income_types = {"INCOME"}
    income_schedules = [s for s in schedules if s["type"] in income_types and s["entity_id"] is not None]

    # Entity type lookup for the legacy category fallback (mirrors the realized query)
    entity_types = {e["id"]: e["entity_type"] for e in get_all_entities(conn)}

    # Compute occurrences for each schedule

    def parse_date(s):
        if not s:
            return None
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except Exception:
            return None

    def advance_date(dt, periodicity):
        if periodicity == "DAILY":
            return dt + timedelta(days=1)
        elif periodicity == "WEEKLY":
            return dt + timedelta(weeks=1)
        elif periodicity == "MONTHLY":
            month = dt.month + 1
            year = dt.year + (month - 1) // 12
            month = ((month - 1) % 12) + 1
            day = min(
                dt.day,
                [
                    31,
                    29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                    31,
                    30,
                    31,
                    30,
                    31,
                    31,
                    30,
                    31,
                    30,
                    31,
                ][month - 1],
            )
            return dt.replace(year=year, month=month, day=day)
        elif periodicity == "QUARTERLY":
            return advance_date(advance_date(advance_date(dt, "MONTHLY"), "MONTHLY"), "MONTHLY")
        elif periodicity == "ANNUALLY":
            try:
                return dt.replace(year=dt.year + 1)
            except Exception:
                return dt.replace(year=dt.year + 1, day=28)
        return dt

    def format_period(dt):
        return f"{dt.year}-{dt.month:02d}"

    start_dt = parse_date(start_date) if start_date else datetime.now(UTC)
    end_dt = parse_date(end_date) if end_date else None
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    # Group by period, entity, type and category
    projected_data: defaultdict[str, defaultdict[int, defaultdict[tuple[str, str], float]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(float))
    )
    currencies = set()

    for schedule in income_schedules:
        schedule_start = parse_date(schedule["start_date"])
        schedule_end = parse_date(schedule["end_date"])

        if not schedule_start:
            continue

        # Skip ONE_OFF and CUSTOM periodicity
        if schedule["periodicity_type"] in ("ONE_OFF", "CUSTOM"):
            continue

        # Determine effective start (max of schedule_start, today, start_date)
        effective_start = max(schedule_start, today)
        if start_dt:
            effective_start = max(effective_start, start_dt)

        # Generate occurrences
        current = schedule_start
        while current < effective_start:
            current = advance_date(current, schedule["periodicity_type"])

        while current <= (schedule_end or end_dt or datetime(2099, 12, 31)):
            if end_dt and current > end_dt:
                break

            period = format_period(current)
            entity_id = schedule["entity_id"]
            amount = schedule["total_value"] or 0
            currency = schedule["currency"] or "USD"
            income_type = schedule["type"]
            category = schedule.get("income_category") or (
                "salary" if entity_types.get(entity_id) == "EMPLOYER" else "other"
            )

            projected_data[period][entity_id][(income_type, category)] += amount
            currencies.add(currency)

            current = advance_date(current, schedule["periodicity_type"])

    # Build rate cache if display_currency is provided
    rate_cache: dict[str, float] = {}
    if display_currency:
        for cur in currencies:
            if cur == display_currency:
                continue
            try:
                rate_response = get_rate(cur, display_currency)
                rate_cache[cur] = rate_response.rate
            except PairNotFound:
                pass

    def convert(value: float, cur: str) -> float:
        if not display_currency or cur == display_currency or cur not in rate_cache:
            return value
        return value * rate_cache[cur]

    # Get entity names
    from db.queries import get_all_entities

    entities = get_all_entities(conn)
    entity_map = {e["id"]: e["name"] for e in entities}

    # Convert to IncomeBySourceLine format
    result = []
    for period, entity_data in sorted(projected_data.items()):
        for entity_id, type_data in entity_data.items():
            for (income_type, category), total_value in sorted(type_data.items()):
                # Find the currency for this entity+type (use first matching schedule's currency)
                entity_currency = "USD"
                for schedule in income_schedules:
                    if schedule["entity_id"] == entity_id and schedule["type"] == income_type:
                        entity_currency = schedule["currency"] or "USD"
                        break

                result.append(
                    IncomeBySourceLine(
                        period=period,
                        entity_id=entity_id,
                        entity_name=entity_map.get(entity_id, f"Entity #{entity_id}"),
                        type=income_type,
                        income_category=category,
                        currency=entity_currency,
                        total_value=round(convert(total_value, entity_currency), 4),
                        count=1,
                    )
                )

    rate_info = _get_rate_metadata(list(currencies), display_currency) if display_currency else None

    return IncomeBySourceWithRates(data=result, rate_info=rate_info)


def get_dividends(
    start_date: str | None = None,
    end_date: str | None = None,
    display_currency: str | None = None,
) -> list[DividendLine]:
    conn = get_db()
    rows = get_dividends_raw(conn, start_date, end_date)
    lines = [
        DividendLine(
            portfolio_asset_id=r["portfolio_asset_id"],
            market_code=r["market_code"],
            ticker=r["ticker"],
            name=r["name"],
            currency=r["currency"],
            total_dividends=round(r["total_dividends"], 4),
            count=r["count"],
        )
        for r in rows
    ]
    if display_currency is None:
        return lines

    # Display-currency totals (§16.4): each payment converts at its own
    # transaction-date rate, then aggregates per asset/currency line.
    provider = CurrencyServiceRateProvider()
    fallbacks: list[RateFallbackInfo] = []
    converted: dict[tuple[int | None, str], float] = defaultdict(float)
    for payment in get_dividend_transactions(conn, start_date, end_date):
        cur = payment["currency"]
        value = payment["total_value"] or 0.0
        rate = _lookup_rate(cur, display_currency, _parse_ts(payment["timestamp"]), "dividends", provider, fallbacks)
        converted[(payment["portfolio_asset_id"], cur)] += value * rate
    for line in lines:
        line.total_dividends_display = round(converted.get((line.portfolio_asset_id, line.currency), 0.0), 4)
    return lines


def get_fees_taxes(
    start_date: str | None = None,
    end_date: str | None = None,
) -> FeeTaxSummary:
    conn = get_db()
    fee_rows = get_fees_raw(conn, start_date, end_date)
    tax_rows = get_taxes_raw(conn, start_date, end_date)

    fee_groups: dict[tuple[str, str], float] = defaultdict(float)
    total_fees = 0.0
    for r in fee_rows:
        amount = _compute_fee_amount(r["nature"], r["fixed_amount"], r["percentage"], r["tx_total"])
        key = (r["fee_type"], r["currency"])
        fee_groups[key] += amount
        total_fees += amount

    fees = [
        FeeSummaryLine(fee_type=ft, currency=cc, total_amount=round(amt, 4), count=1)
        for (ft, cc), amt in sorted(fee_groups.items(), key=lambda x: -x[1])
    ]

    tax_groups: dict[tuple[str, str], float] = defaultdict(float)
    total_taxes = 0.0
    for r in tax_rows:
        key = (r["tax_type"], r["currency"])
        tax_groups[key] += r["tax_amount"]
        total_taxes += r["tax_amount"]

    taxes = [
        TaxSummaryLine(tax_type=tt, currency=cc, total_amount=round(amt, 4), count=1)
        for (tt, cc), amt in sorted(tax_groups.items(), key=lambda x: -x[1])
    ]

    return FeeTaxSummary(
        fees=fees,
        taxes=taxes,
        total_fees=round(total_fees, 4),
        total_taxes=round(total_taxes, 4),
    )


def get_realized_gains() -> list[RealizedGainLine]:
    conn = get_db()
    result = compute_fifo(get_buy_sell_transactions(conn))

    lines: list[RealizedGainLine] = []
    for sale in result.sales:
        pct = (sale.realized_pl / sale.cost_basis * 100) if sale.cost_basis > 0 else 0.0
        lines.append(
            RealizedGainLine(
                transaction_id=sale.transaction_id,
                portfolio_asset_id=sale.portfolio_asset_id,
                market_code=sale.market_code,
                ticker=sale.ticker,
                name=sale.name,
                sell_date=sale.sell_date_raw,
                sell_quantity=sale.sell_quantity,
                sell_price=sale.sell_price,
                sell_total=sale.sell_total,
                cost_basis=sale.cost_basis,
                realized_pl=sale.realized_pl,
                realized_pl_pct=round(pct, 4),
                currency=sale.currency,
            )
        )
    return lines


def _aggregate_rate_fallbacks(entries: list[RateFallbackInfo]) -> list[PerformanceRateFallback]:
    """Group identical fallback entries, keeping a count (§16.4)."""
    grouped: dict[tuple[str, str, str, str | None, str | None], list[RateFallbackInfo]] = {}
    for entry in entries:
        key = (entry.currency, entry.scope, entry.reason, entry.requested_date, entry.used_timestamp)
        grouped.setdefault(key, []).append(entry)
    result: list[PerformanceRateFallback] = []
    for group in grouped.values():
        first = group[0]
        result.append(
            PerformanceRateFallback(
                currency=first.currency,
                scope=cast(Literal["realized_pl", "invested_historic", "dividends", "interest"], first.scope),
                reason=cast(Literal["closest-in-time", "no-rate"], first.reason),
                requested_date=first.requested_date,
                used_timestamp=first.used_timestamp,
                count=len(group),
            )
        )
    return result


def get_performance_summary(display_currency: str = "USD", locale: str = "") -> PerformanceSummary:
    holdings = get_holdings()
    conn = get_db()
    rule_key = rule_for_locale(locale)
    provider = CurrencyServiceRateProvider()
    fallback_infos: list[RateFallbackInfo] = []

    # Invested historic is buy-side only and rule-independent (§16.3): each buy
    # is converted at the rate of its own purchase date.
    invested_rows = conn.execute(
        "SELECT timestamp, currency, total_value FROM transactions WHERE type = 'INVESTMENT_BUY'"
    ).fetchall()
    total_invested_historic = 0.0
    for row in invested_rows:
        cur = row["currency"]
        value = row["total_value"] or 0.0
        if cur == display_currency:
            total_invested_historic += value
            continue
        at = _parse_ts(row["timestamp"])
        try:
            lookup = provider.historical(cur, display_currency, at)
        except NoRateError:
            fallback_infos.append(RateFallbackInfo(cur, "invested_historic", "no-rate", at.date().isoformat(), None))
            total_invested_historic += value
            continue
        if lookup.fallback:
            fallback_infos.append(
                RateFallbackInfo(
                    cur, "invested_historic", "closest-in-time", at.date().isoformat(), lookup.timestamp.isoformat()
                )
            )
        total_invested_historic += value * lookup.rate

    # Realized P&L conversion is rule-driven (§16.2). Each sale uses its frozen
    # fiscal_rule snapshot; legacy/period-less sells (NULL) fall back to the
    # locale-inferred default.
    realized = compute_fifo(get_buy_sell_transactions(conn)).sales
    total_realized = 0.0
    total_sold_cost = 0.0
    for sale in realized:
        sale_rule = sale.fiscal_rule or rule_key
        converted = convert_sale(sale, sale_rule, provider, display_currency)
        total_realized += converted.value
        total_sold_cost += converted.cost_basis_display
        fallback_infos.extend(converted.fallbacks)

    # Investment income (§14.3): dividends count as realized investment gains;
    # interest is tracked separately (cash-derived, not investment income).
    # Each payment converts at its own transaction-date rate (§16.4 pattern).
    income_rows = conn.execute(
        "SELECT timestamp, currency, income_category, total_value FROM transactions "
        "WHERE type = 'INCOME' AND income_category IN ('dividends', 'interest')"
    ).fetchall()
    total_dividends = 0.0
    total_interest = 0.0
    for row in income_rows:
        cur = row["currency"]
        value = row["total_value"] or 0.0
        scope = "dividends" if row["income_category"] == "dividends" else "interest"
        amount = value * _lookup_rate(
            cur, display_currency, _parse_ts(row["timestamp"]), scope, provider, fallback_infos
        )
        if scope == "dividends":
            total_dividends += amount
        else:
            total_interest += amount

    needed_currencies = {h.currency_code for h in holdings if h.current_value is not None}
    needed_currencies.update(h.currency_code for h in holdings if h.total_cost is not None)
    needed_currencies.update(g.currency for g in realized)

    rate_cache: dict[str, float] = {}
    for cur in needed_currencies:
        if cur == display_currency:
            continue
        try:
            rate_cache[cur] = get_rate(cur, display_currency).rate
        except PairNotFound:
            pass

    def convert(value: float, cur: str) -> float:
        if cur == display_currency or cur not in rate_cache:
            return value
        return value * rate_cache[cur]

    total_unrealized = (
        sum(convert(h.unrealized_pl, h.currency_code) for h in holdings if h.unrealized_pl is not None) or 0.0
    )
    total_invested_now = sum(convert(h.total_cost, h.currency_code) for h in holdings) or 0.0
    total_portfolio_value = (
        sum(convert(h.current_value, h.currency_code) for h in holdings if h.current_value is not None) or 0.0
    )
    # Realized-only definition (§6): unrealized P&L is reported separately and
    # never summed into Total Return; interest stays excluded (cash yield).
    total_return = total_realized + total_dividends
    total_return_pct = (total_return / total_invested_historic * 100) if total_invested_historic > 0 else 0.0
    unrealized_pl_pct = (total_unrealized / total_invested_now * 100) if total_invested_now > 0 else 0.0
    realized_pl_pct = (total_realized / total_sold_cost * 100) if total_sold_cost > 0 else 0.0
    dividend_yield_pct = (total_dividends / total_invested_historic * 100) if total_invested_historic > 0 else 0.0

    return PerformanceSummary(
        display_currency=display_currency,
        total_realized_pl=round(total_realized, 4),
        total_unrealized_pl=round(total_unrealized, 4),
        total_return=round(total_return, 4),
        total_invested_now=round(total_invested_now, 4),
        total_invested_historic=round(total_invested_historic, 4),
        total_return_pct=round(total_return_pct, 4),
        total_portfolio_value=round(total_portfolio_value, 4),
        unrealized_pl_pct=round(unrealized_pl_pct, 4),
        realized_pl_pct=round(realized_pl_pct, 4),
        total_dividends=round(total_dividends, 4),
        dividend_yield_pct=round(dividend_yield_pct, 4),
        total_interest=round(total_interest, 4),
        rule_key=rule_key,
        rate_fallbacks=_aggregate_rate_fallbacks(fallback_infos),
    )


def _apply_exemption(
    gross: float,
    exemption: dict,
    currency: str,
    at: datetime,
    provider: CurrencyServiceRateProvider,
    display_currency: str,
    fallbacks: list[RateFallbackInfo],
    scope: str,
) -> float:
    """Reduce a positive taxable amount by its linked fiscal exemption (§17.3).

    Losses are returned unchanged. ``exemption_rate`` (0-100) exempts a
    percentage; ``exemption_amount`` is a fixed allowance in the transaction's
    currency (converted); ``exemption_rate_limit`` caps the rate-based portion
    (in display currency).
    """
    if gross <= 0:
        return gross
    rate_exempt = gross * (exemption["exemption_rate"] / 100.0)
    if exemption["exemption_rate_limit"] is not None:
        rate_exempt = min(rate_exempt, exemption["exemption_rate_limit"])
    fixed = exemption["exemption_amount"]
    if fixed:
        fixed = fixed * _lookup_rate(currency, display_currency, at, scope, provider, fallbacks)
    return gross - min(gross, rate_exempt + fixed)


def _get_exemptions(conn) -> dict[int, dict]:
    from db import queries

    return {e["id"]: e for e in queries.get_all_fiscal_exemptions(conn)}


def get_taxable_pnl(display_currency: str = "USD", locale: str = "", ruleset: str = "") -> TaxablePnlSummary:
    """Compute taxable P&L per fiscal year for a ruleset (§17)."""
    conn = get_db()
    resolved_ruleset = ruleset or rule_for_locale(locale)
    fiscal_start = FISCAL_YEAR_START.get(resolved_ruleset, (1, 1))
    provider = CurrencyServiceRateProvider()
    fallback_infos: list[RateFallbackInfo] = []

    fiscal_years: dict[int, dict] = {}

    def _year_bucket(ts: datetime) -> dict:
        fy = fiscal_year_bounds(ts, fiscal_start)
        if fy.label not in fiscal_years:
            fiscal_years[fy.label] = {
                "fiscal_year": fy.label,
                "start_date": fy.start_date,
                "end_date": fy.end_date,
                "realized_gains_taxable": 0.0,
                "dividends_taxable": 0.0,
                "num_sells": 0,
                "num_dividends": 0,
            }
        return fiscal_years[fy.label]

    exemptions = _get_exemptions(conn)

    # Realized gains (rule-driven, frozen snapshot).
    sales = compute_fifo(get_buy_sell_transactions(conn)).sales
    for sale in sales:
        converted = convert_sale(sale, sale.fiscal_rule or resolved_ruleset, provider, display_currency)
        fallback_infos.extend(converted.fallbacks)
        taxable = converted.value
        exemption = exemptions.get(sale.fiscal_exemption_id) if sale.fiscal_exemption_id else None
        if exemption is not None:
            taxable = _apply_exemption(
                taxable,
                exemption,
                sale.currency,
                sale.sell_date,
                provider,
                display_currency,
                fallback_infos,
                "realized_pl",
            )
        bucket = _year_bucket(sale.sell_date)
        bucket["realized_gains_taxable"] += taxable
        bucket["num_sells"] += 1

    # Dividends (taxable income, converted at payment date).
    for div in get_dividend_transactions(conn):
        at = _parse_ts(div["payment_date"] or div["timestamp"])
        taxable = convert_dividend(
            div["total_value"] or 0.0, div["currency"], at, provider, display_currency, fallback_infos
        )
        exemption = exemptions.get(div["fiscal_exemption_id"])
        if exemption is not None:
            taxable = _apply_exemption(
                taxable, exemption, div["currency"], at, provider, display_currency, fallback_infos, "dividends"
            )
        bucket = _year_bucket(at)
        bucket["dividends_taxable"] += taxable
        bucket["num_dividends"] += 1

    years = []
    total = 0.0
    for key in sorted(fiscal_years):
        bucket = fiscal_years[key]
        bucket["realized_gains_taxable"] = round(bucket["realized_gains_taxable"], 4)
        bucket["dividends_taxable"] = round(bucket["dividends_taxable"], 4)
        bucket["total_taxable"] = round(bucket["realized_gains_taxable"] + bucket["dividends_taxable"], 4)
        total += bucket["total_taxable"]
        years.append(TaxablePnlFiscalYear(**bucket))

    return TaxablePnlSummary(
        ruleset=resolved_ruleset,
        display_currency=display_currency,
        fiscal_years=years,
        total_taxable=round(total, 4),
        rate_fallbacks=_aggregate_rate_fallbacks(fallback_infos),
    )


def get_taxable_pnl_extended(
    display_currency: str = "USD",
    locale: str = "",
    ruleset: str = "",
) -> TaxablePnlSummaryExtended:
    """Extended taxable P&L: adds per-year tax owed, item detail, and default ruleset (§17.9, §17.10, §17.11)."""
    conn = get_db()
    resolved_ruleset = ruleset or rule_for_locale(locale)
    fiscal_start = FISCAL_YEAR_START.get(resolved_ruleset, (1, 1))
    provider = CurrencyServiceRateProvider()
    fallback_infos: list[RateFallbackInfo] = []

    # Load tax rates for this ruleset into TaxBracket objects (§17.8).
    raw_rates = queries.get_tax_rates_for_ruleset(conn, resolved_ruleset)
    brackets = [
        TaxBracket(
            category=r["category"],
            from_amount=r["from_amount"],
            to_amount=r["to_amount"],
            rate=r["rate"],
        )
        for r in raw_rates
    ]

    # Profile default ruleset (§17.11).
    profile_row = conn.execute("SELECT default_fiscal_rule FROM profiles LIMIT 1").fetchone()
    default_ruleset = profile_row["default_fiscal_rule"] if profile_row and profile_row["default_fiscal_rule"] else None

    fiscal_years: dict[int, dict] = {}

    def _year_bucket(ts: datetime) -> dict:
        fy = fiscal_year_bounds(ts, fiscal_start)
        if fy.label not in fiscal_years:
            fiscal_years[fy.label] = {
                "fiscal_year": fy.label,
                "start_date": fy.start_date,
                "end_date": fy.end_date,
                "realized_gains_taxable": 0.0,
                "dividends_taxable": 0.0,
                "num_sells": 0,
                "num_dividends": 0,
                "items": [],
            }
        return fiscal_years[fy.label]

    exemptions = _get_exemptions(conn)

    # Realized gains — each item gets its own TaxablePnlItem.
    sales = compute_fifo(get_buy_sell_transactions(conn)).sales
    for sale in sales:
        converted = convert_sale(sale, sale.fiscal_rule or resolved_ruleset, provider, display_currency)
        fallback_infos.extend(converted.fallbacks)
        taxable = converted.value
        exemption = exemptions.get(sale.fiscal_exemption_id) if sale.fiscal_exemption_id else None
        if exemption is not None:
            taxable = _apply_exemption(
                taxable,
                exemption,
                sale.currency,
                sale.sell_date,
                provider,
                display_currency,
                fallback_infos,
                "realized_pl",
            )
        bucket = _year_bucket(sale.sell_date)
        bucket["realized_gains_taxable"] += taxable
        bucket["num_sells"] += 1
        bucket["items"].append(
            TaxablePnlItem(
                transaction_id=sale.transaction_id,
                market_code=sale.market_code,
                ticker=sale.ticker,
                name=sale.name,
                category="capital_gains",
                date=sale.sell_date_raw,
                native_amount=sale.sell_total - sale.cost_basis,
                display_amount=round(taxable, 4),
                tax_owed=0.0,  # filled after tax model
                source="computed",
                fiscal_rule=sale.fiscal_rule,
                currency=sale.currency,
            )
        )

    # Dividends.
    for div in get_dividend_transactions(conn):
        at = _parse_ts(div["payment_date"] or div["timestamp"])
        taxable = convert_dividend(
            div["total_value"] or 0.0, div["currency"], at, provider, display_currency, fallback_infos
        )
        exemption = exemptions.get(div["fiscal_exemption_id"])
        if exemption is not None:
            taxable = _apply_exemption(
                taxable, exemption, div["currency"], at, provider, display_currency, fallback_infos, "dividends"
            )
        bucket = _year_bucket(at)
        bucket["dividends_taxable"] += taxable
        bucket["num_dividends"] += 1
        bucket["items"].append(
            TaxablePnlItem(
                transaction_id=div["id"],
                market_code=div.get("market_code"),
                ticker=div.get("ticker"),
                name=div.get("asset_name") or div.get("entity_name"),
                category="dividends",
                date=at.isoformat(),
                native_amount=div["total_value"] or 0.0,
                display_amount=round(taxable, 4),
                tax_owed=0.0,
                source="computed",
                currency=div["currency"],
            )
        )

    # Confirmed taxes override computed values (§17.12: confirmed if present else computed).
    confirmed_map = _build_confirmed_tax_map(conn)
    for bucket in fiscal_years.values():
        for item in bucket["items"]:
            confirmed = confirmed_map.get(item.transaction_id)
            if confirmed is not None:
                item.tax_owed = confirmed
                item.source = "confirmed"

    # Apply tax model per fiscal year (§17.10).
    tax_model = get_tax_model(resolved_ruleset)
    combined_base_all = 0.0
    total_tax_owed = 0.0
    for key in sorted(fiscal_years):
        bucket = fiscal_years[key]
        bucket["realized_gains_taxable"] = round(bucket["realized_gains_taxable"], 4)
        bucket["dividends_taxable"] = round(bucket["dividends_taxable"], 4)
        bucket["total_taxable"] = round(bucket["realized_gains_taxable"] + bucket["dividends_taxable"], 4)

        bases = {
            "capital_gains": bucket["realized_gains_taxable"],
            "dividends": bucket["dividends_taxable"],
        }
        result = tax_model.compute(bases, brackets)
        bucket["tax_owed"] = dict(result.tax_owed)
        total_tax_owed += result.total_tax_owed
        if result.combined_base is not None:
            combined_base_all += result.combined_base

        # Apply tax_owed to non-confirmed items proportionally.
        confirmed_cats: dict[str, float] = {}
        for item in bucket["items"]:
            if item.source == "confirmed":
                confirmed_cats[item.category] = confirmed_cats.get(item.category, 0.0) + item.tax_owed
        for item in bucket["items"]:
            if item.source == "computed":
                cat_base = bases.get(item.category, 0.0)
                if cat_base > 0 and result.tax_owed.get(item.category, 0.0) > 0:
                    cat_confirmed = confirmed_cats.get(item.category, 0.0)
                    cat_remaining = max(result.tax_owed[item.category] - cat_confirmed, 0.0)
                    cat_computed_base = max(
                        cat_base
                        - sum(
                            i.display_amount
                            for i in bucket["items"]
                            if i.source == "confirmed" and i.category == item.category
                        ),
                        0.0,
                    )
                    if cat_computed_base > 0:
                        item.tax_owed = round(cat_remaining * (item.display_amount / cat_computed_base), 4)
                    else:
                        item.tax_owed = 0.0
                else:
                    item.tax_owed = 0.0

        bucket["items"].sort(key=lambda i: i.date)

    years = []
    total = 0.0
    for key in sorted(fiscal_years):
        bucket = fiscal_years[key]
        total += bucket["total_taxable"]
        years.append(TaxablePnlFiscalYearExtended(**bucket))

    return TaxablePnlSummaryExtended(
        ruleset=resolved_ruleset,
        display_currency=display_currency,
        fiscal_years=years,
        total_taxable=round(total, 4),
        total_tax_owed=round(total_tax_owed, 4),
        combined_base=round(combined_base_all, 4) if combined_base_all else None,
        rate_fallbacks=_aggregate_rate_fallbacks(fallback_infos),
        default_ruleset=default_ruleset,
    )


def _build_confirmed_tax_map(conn) -> dict[int, float]:
    """Map transaction_id → sum of confirmed tax amounts (§17.12)."""
    rows = conn.execute(
        "SELECT transaction_id, SUM(tax_amount) as total FROM transaction_taxes GROUP BY transaction_id"
    ).fetchall()
    return {r["transaction_id"]: r["total"] for r in rows}


def _generate_dates(start: str, end: str, interval: str) -> list[str]:
    if interval not in ("day", "week", "month", "quarter", "year"):
        raise AnalyticsError(f"Invalid interval '{interval}'. Must be one of: day, week, month, quarter, year")
    start_dt = datetime.fromisoformat(start).date()
    end_dt = datetime.fromisoformat(end).date()
    dates: list[str] = []
    current = start_dt
    while current <= end_dt:
        dates.append(current.isoformat())
        if interval == "day":
            current += timedelta(days=1)
        elif interval == "week":
            current += timedelta(weeks=1)
        elif interval == "month":
            y = current.year + (current.month // 12)
            m = (current.month % 12) + 1
            current = current.replace(year=y, month=m, day=1)
        elif interval == "quarter":
            m = ((current.month - 1) // 3 + 1) * 3 - 2
            current = current.replace(month=m, day=1)
            m = current.month + 3
            y = current.year
            if m > 12:
                m -= 12
                y += 1
            current = current.replace(year=y, month=m)
        elif interval == "year":
            current = current.replace(year=current.year + 1, month=1, day=1)
    return dates


def get_historical_values(
    start_date: str,
    end_date: str,
    interval: str = "month",
    entity_id: int | None = None,
    display_currency: str | None = None,
) -> list[HistoricalValuePoint]:
    if interval not in ("day", "week", "month", "quarter", "year"):
        raise AnalyticsError(f"Invalid interval '{interval}'. Must be one of: day, week, month, quarter, year")
    conn = get_db()
    dates = _generate_dates(start_date, end_date, interval)

    # Add today's date if not already included to ensure latest snapshots are captured
    today = datetime.now(UTC).date().isoformat()
    if dates[-1] < today <= end_date:
        dates.append(today)

    all_prices = get_all_prices(conn)
    price_index: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for p in all_prices:
        price_index[p["market_code"]].append((p["timestamp"], p["price"]))
    for mc in price_index:
        price_index[mc].sort(key=lambda x: x[0])
    price_ts_list = {mc: [x[0] for x in entries] for mc, entries in price_index.items()}

    # Fallback: latest unit_price from INVESTMENT_BUY transactions per market_code
    tx_fallback = {r["market_code"]: r["unit_price"] for r in get_latest_transaction_prices(conn)}

    def _price_as_of(market_code: str, dt: str) -> float | None:
        entries = price_index.get(market_code, [])
        ts_list = price_ts_list.get(market_code, [])
        if ts_list:
            idx = bisect_right(ts_list, dt) - 1
            if idx >= 0:
                return entries[idx][1]
        # Fallback to latest transaction unit_price if no market price exists
        return tx_fallback.get(market_code)

    # Build rate cache for currency conversion
    rate_cache: dict[str, float] = {}
    if display_currency:
        # Collect all currencies from positions and cash
        all_currencies = set()
        for dt in dates:
            dt_ts = dt if "T" in dt else dt + "T23:59:59"
            positions = get_net_positions_as_of(conn, dt_ts, entity_id)
            for pos in positions:
                if pos.get("currency_code"):
                    all_currencies.add(pos["currency_code"])
            # Add cash currencies (using snapshot-aware function)
            if entity_id is None:
                cash_by_cur = get_total_cash_by_currency_as_of(conn, dt_ts)
            else:
                cash_by_cur = get_entity_total_cash_by_currency_as_of(conn, entity_id, dt_ts)
            all_currencies.update(cash_by_cur.keys())

        # Build rate cache
        for cur in all_currencies:
            if cur == display_currency:
                continue
            try:
                rate_cache[cur] = get_rate(cur, display_currency).rate
            except PairNotFound:
                pass

    def convert(value: float, cur: str) -> float:
        if not display_currency or cur == display_currency or cur not in rate_cache:
            return value
        return value * rate_cache[cur]

    results: list[HistoricalValuePoint] = []
    for dt in dates:
        dt_ts = dt if "T" in dt else dt + "T23:59:59"
        positions = get_net_positions_as_of(conn, dt_ts, entity_id)
        investment = 0.0
        total = 0.0
        for pos in positions:
            price = _price_as_of(pos["market_code"], dt_ts)
            if price is not None:
                value = pos["net_quantity"] * price
                converted = convert(value, pos.get("currency_code", ""))
                investment += converted
                total += converted

        # Include manual-tracked assets
        from db.queries import get_manual_tracked_assets, get_manual_value_as_of

        manual_assets = get_manual_tracked_assets(conn)
        for ma in manual_assets:
            mv = get_manual_value_as_of(conn, ma["id"], dt)
            if mv is None:
                # Fallback to current_value_manual
                cv = conn.execute(
                    "SELECT current_value_manual FROM portfolio_assets WHERE id = ?",
                    (ma["id"],),
                ).fetchone()
                if cv and cv["current_value_manual"] is not None:
                    mv = cv["current_value_manual"]
            if mv is not None:
                total += convert(mv, ma.get("currency_code", ""))

        # Use snapshot-aware cash function
        if entity_id is None:
            cash_by_cur = get_total_cash_by_currency_as_of(conn, dt_ts)
        else:
            cash_by_cur = get_entity_total_cash_by_currency_as_of(conn, entity_id, dt_ts)
        for cur, cash_amount in cash_by_cur.items():
            total += convert(cash_amount, cur)

        results.append(
            HistoricalValuePoint(
                date=dt,
                total_value=round(total, 4),
                investment_value=round(investment, 4),
            )
        )

    return results


def get_cash_balances() -> list[dict]:
    conn = get_db()
    return get_cash_balance_by_currency(conn)


def get_cash_by_currency_history_svc(
    start_date: str,
    end_date: str,
    interval: str = "month",
) -> list[dict]:
    conn = get_db()
    return get_cash_by_currency_history(conn, start_date, end_date, interval)
