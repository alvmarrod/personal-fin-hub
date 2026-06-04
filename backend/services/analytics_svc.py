from bisect import bisect_right
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from db.analytics_queries import (
    get_all_prices,
    get_buy_sell_transactions,
    get_cash_balance,
    get_cash_flow_raw,
    get_dividends_raw,
    get_fees_raw,
    get_holdings_raw,
    get_latest_prices,
    get_net_positions_as_of,
    get_taxes_raw,
)
from db.connection import get_db
from models import (
    AllocationLine,
    CashFlowLine,
    CashFlowSummary,
    DashboardSummary,
    DividendLine,
    FeeSummaryLine,
    FeeTaxSummary,
    HistoricalValuePoint,
    HoldingLine,
    PerformanceSummary,
    RealizedGainLine,
    TaxSummaryLine,
)
from models.enums import AssetType, Layer, TrackingMode


class AnalyticsError(Exception):
    pass


def get_dashboard() -> DashboardSummary:
    holdings = get_holdings()
    conn = get_db()
    cash = get_cash_balance(conn)
    total_value = sum(h.current_value for h in holdings if h.current_value is not None) or 0.0
    total_invested = sum(h.total_cost for h in holdings) or 0.0
    num = len(holdings)
    total_return = total_value + cash - total_invested
    return_pct = (total_return / total_invested * 100) if total_invested > 0 else 0.0
    return DashboardSummary(
        total_portfolio_value=round(total_value, 4),
        total_invested=round(total_invested, 4),
        cash_balance=round(cash, 4),
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
        else:
            current_value = None

        if current_value is not None:
            total_value += current_value

        enriched.append({
            "row": row,
            "net_qty": net_qty,
            "total_cost": total_cost,
            "avg_cost": avg_cost,
            "current_value": current_value,
        })

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

        holdings.append(HoldingLine(
            portfolio_asset_id=row["portfolio_asset_id"],
            market_code=row["market_code"],
            ticker=row.get("ticker"),
            name=row.get("name"),
            asset_type=AssetType(row["asset_type"]),
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
        ))

    return holdings


def get_asset_allocation(dimension: str = "layer") -> list[AllocationLine]:
    if dimension not in ("layer", "asset_type", "currency"):
        raise AnalyticsError(f"Invalid dimension '{dimension}'. Must be one of: layer, asset_type, currency")

    holdings = get_holdings()
    if not holdings:
        return []

    total_value = sum(h.current_value for h in holdings if h.current_value is not None) or 0.0
    groups: dict[str, float] = defaultdict(float)

    for h in holdings:
        if h.current_value is None:
            continue
        if dimension == "layer":
            key = h.layer.value if h.layer else "unspecified"
        elif dimension == "asset_type":
            key = h.asset_type.value
        else:
            key = h.currency_code
        groups[key] += h.current_value

    result = []
    for category, value_abs in sorted(groups.items(), key=lambda x: -x[1]):
        pct = (value_abs / total_value * 100) if total_value > 0 else 0.0
        result.append(AllocationLine(
            category=category,
            dimension=dimension,
            value_pct=round(pct, 4),
            value_abs=round(value_abs, 4),
        ))

    return result


def _compute_fee_amount(
    nature: str, fixed_amount: float, percentage: float, tx_total: float
) -> float:
    if nature == "FIXED":
        return fixed_amount
    elif nature == "PERCENTAGE":
        return percentage * tx_total / 100.0
    elif nature == "BOTH":
        return fixed_amount + percentage * tx_total / 100.0
    elif nature == "MIN":
        return min(fixed_amount, percentage * tx_total / 100.0)
    return 0.0


def get_cash_flow(
    group_by: str = "month",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> CashFlowSummary:
    if group_by not in ("day", "week", "month", "quarter", "year"):
        raise AnalyticsError(
            f"Invalid group_by '{group_by}'. Must be one of: day, week, month, quarter, year"
        )
    conn = get_db()
    rows = get_cash_flow_raw(conn, group_by, start_date, end_date)
    lines = [
        CashFlowLine(
            period=r["period"],
            type=r["type"],
            total_value=r["total_value"],
            count=r["count"],
            currency=r["currency"],
        )
        for r in rows
    ]
    total_in = sum(
        r["total_value"]
        for r in rows
        if r["type"] in ("MONEY_IN", "INTEREST", "DIVIDEND", "INVESTMENT_SELL")
    )
    total_out = sum(
        r["total_value"]
        for r in rows
        if r["type"] in ("MONEY_OUT", "INVESTMENT_BUY")
    )
    return CashFlowSummary(
        lines=lines,
        total_in=round(total_in, 4),
        total_out=round(total_out, 4),
        net=round(total_in - total_out, 4),
    )


def get_dividends(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
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
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> FeeTaxSummary:
    conn = get_db()
    fee_rows = get_fees_raw(conn, start_date, end_date)
    tax_rows = get_taxes_raw(conn, start_date, end_date)

    fee_groups: dict[tuple[str, str], float] = defaultdict(float)
    total_fees = 0.0
    for r in fee_rows:
        amount = _compute_fee_amount(
            r["nature"], r["fixed_amount"], r["percentage"], r["tx_total"]
        )
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
                results.append(RealizedGainLine(
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
                ))
            total_qty -= qty
            if total_qty < 0:
                total_qty = 0.0

    return results


def get_performance_summary() -> PerformanceSummary:
    conn = get_db()
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
        raise AnalyticsError(
            f"Invalid interval '{interval}'. Must be one of: day, week, month, quarter, year"
        )
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
) -> list[HistoricalValuePoint]:
    if interval not in ("day", "week", "month", "quarter", "year"):
        raise AnalyticsError(
            f"Invalid interval '{interval}'. Must be one of: day, week, month, quarter, year"
        )
    conn = get_db()
    dates = _generate_dates(start_date, end_date, interval)

    all_prices = get_all_prices(conn)
    price_index: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for p in all_prices:
        price_index[p["market_code"]].append((p["timestamp"], p["price"]))
    for mc in price_index:
        price_index[mc].sort(key=lambda x: x[0])
    price_ts_list = {mc: [x[0] for x in entries] for mc, entries in price_index.items()}

    def _price_as_of(market_code: str, dt: str) -> float | None:
        entries = price_index.get(market_code, [])
        ts_list = price_ts_list.get(market_code, [])
        if not ts_list:
            return None
        idx = bisect_right(ts_list, dt) - 1
        if idx >= 0:
            return entries[idx][1]
        return None

    results: list[HistoricalValuePoint] = []
    for dt in dates:
        positions = get_net_positions_as_of(conn, dt)
        total = 0.0
        for pos in positions:
            price = _price_as_of(pos["market_code"], dt)
            if price is not None:
                total += pos["net_quantity"] * price
        results.append(HistoricalValuePoint(
            date=dt,
            total_value=round(total, 4),
        ))

    return results
