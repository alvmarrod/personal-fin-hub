from bisect import bisect_right
from collections import defaultdict
from datetime import datetime, timedelta

from db.analytics_queries import (
    get_all_prices,
    get_buy_sell_transactions,
    get_cash_balance_by_currency,
    get_cash_by_currency_history,
    get_cash_by_entity_raw,
    get_cash_flow_raw,
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
    PerformanceSummary,
    RateMetadata,
    RealizedGainLine,
    TaxSummaryLine,
)
from models.enums import AssetClass, AssetType, Layer, TrackingMode
from services.currency_svc import PairNotFound, get_rate


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

    return RateMetadata(rates=rates, latest_timestamp=latest_timestamp.isoformat() if latest_timestamp else "")


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
    )


def get_holdings() -> list[HoldingLine]:
    conn = get_db()
    raw = get_holdings_raw(conn)
    if not raw:
        return []

    prices = get_latest_prices(conn)
    price_map = {p["market_code"]: p["price"] for p in prices}

    # Fallback: latest unit_price from INVESTMENT_BUY transactions per market_code
    tx_fallback = {r["market_code"]: r["unit_price"] for r in get_latest_transaction_prices(conn)}

    enriched = []
    total_value = 0.0

    for row in raw:
        net_qty = row["total_bought_qty"] - row["total_sold_qty"]
        total_cost = row["total_cost"] or 0.0
        avg_cost = (total_cost / row["total_bought_qty"]) if row["total_bought_qty"] > 0 else None

        if row["tracking_mode"] == "manual" and row["current_value_manual"] is not None:
            current_value = row["current_value_manual"]
        elif net_qty > 0 and row["market_code"] in price_map:
            current_value = net_qty * price_map[row["market_code"]]
        elif net_qty > 0 and row["market_code"] in tx_fallback:
            current_value = net_qty * tx_fallback[row["market_code"]]
        else:
            current_value = None

        if current_value is not None:
            total_value += current_value

        enriched.append(
            {
                "row": row,
                "net_qty": net_qty,
                "total_cost": total_cost,
                "avg_cost": avg_cost,
                "current_value": current_value,
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
    total_in = sum(
        convert(r["total_value"], r["currency"])
        for r in rows
        if r["type"] in ("MONEY_IN", "INTEREST", "DIVIDEND", "INVESTMENT_SELL")
    )
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
    from db.queries import get_all_schedules

    conn = get_db()
    schedules = get_all_schedules(conn)

    # Filter for income schedules
    income_types = {"MONEY_IN", "INTEREST", "DIVIDEND"}
    income_schedules = [s for s in schedules if s["type"] in income_types and s["entity_id"] is not None]

    # Compute occurrences for each schedule
    from datetime import datetime, timedelta

    def parse_date(s):
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
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

    start_dt = parse_date(start_date) if start_date else datetime.now()
    end_dt = parse_date(end_date) if end_date else None
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Group by period and entity
    projected_data: defaultdict[str, defaultdict[int, float]] = defaultdict(lambda: defaultdict(float))
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

            projected_data[period][entity_id] += amount
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
        for entity_id, total_value in entity_data.items():
            # Find the currency for this entity (use first schedule's currency)
            entity_currency = "USD"
            for schedule in income_schedules:
                if schedule["entity_id"] == entity_id:
                    entity_currency = schedule["currency"] or "USD"
                    break

            result.append(
                IncomeBySourceLine(
                    period=period,
                    entity_id=entity_id,
                    entity_name=entity_map.get(entity_id, f"Entity #{entity_id}"),
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
) -> list[DividendLine]:
    conn = get_db()
    rows = get_dividends_raw(conn, start_date, end_date)
    return [
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
    rows = get_buy_sell_transactions(conn)
    if not rows:
        return []

    results: list[RealizedGainLine] = []
    current_asset_id = None
    avg_cost = 0.0
    total_qty = 0.0

    for r in rows:
        aid = r["portfolio_asset_id"]
        if aid != current_asset_id:
            avg_cost = 0.0
            total_qty = 0.0
            current_asset_id = aid

        qty = r["quantity"]
        total_val = r["total_value"]
        unit_price = r["unit_price"]

        if r["type"] == "INVESTMENT_BUY":
            total_qty += qty
            if total_qty > 0:
                avg_cost = ((avg_cost * (total_qty - qty)) + total_val) / total_qty
        elif r["type"] == "INVESTMENT_SELL":
            if total_qty > 0 and qty > 0:
                cost_basis = avg_cost * qty
                realized_pl = total_val - cost_basis
                realized_pl_pct = (realized_pl / cost_basis) * 100 if cost_basis > 0 else 0.0
                results.append(
                    RealizedGainLine(
                        transaction_id=r["transaction_id"],
                        portfolio_asset_id=r["portfolio_asset_id"],
                        market_code=r["market_code"],
                        ticker=r["ticker"],
                        name=r["name"],
                        sell_date=r["timestamp"],
                        sell_quantity=qty,
                        sell_price=unit_price,
                        sell_total=total_val,
                        cost_basis=round(cost_basis, 4),
                        realized_pl=round(realized_pl, 4),
                        realized_pl_pct=round(realized_pl_pct, 4),
                        currency=r["currency"],
                    )
                )
            total_qty -= qty
            if total_qty < 0:
                total_qty = 0.0

    return results


def get_performance_summary() -> PerformanceSummary:
    holdings = get_holdings()
    realized = get_realized_gains()

    total_unrealized = sum(h.unrealized_pl for h in holdings if h.unrealized_pl is not None) or 0.0
    total_realized = sum(g.realized_pl for g in realized) or 0.0
    total_invested = sum(h.total_cost for h in holdings) or 0.0
    total_portfolio_value = sum(h.current_value for h in holdings if h.current_value is not None) or 0.0
    total_return = total_unrealized + total_realized
    total_return_pct = (total_return / total_invested * 100) if total_invested > 0 else 0.0

    return PerformanceSummary(
        total_realized_pl=round(total_realized, 4),
        total_unrealized_pl=round(total_unrealized, 4),
        total_return=round(total_return, 4),
        total_invested=round(total_invested, 4),
        total_return_pct=round(total_return_pct, 4),
        total_portfolio_value=round(total_portfolio_value, 4),
    )


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
    today = datetime.now().date().isoformat()
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
