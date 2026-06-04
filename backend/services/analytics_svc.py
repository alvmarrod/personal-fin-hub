from collections import defaultdict
from typing import Optional

from db.analytics_queries import (
    get_cash_balance,
    get_cash_flow,
    get_dividends,
    get_fees_raw,
    get_holdings_raw,
    get_latest_prices,
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
    HoldingLine,
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
    rows = get_cash_flow(conn, group_by, start_date, end_date)
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
    rows = get_dividends(conn, start_date, end_date)
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
