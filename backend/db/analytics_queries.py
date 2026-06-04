import sqlite3
from datetime import datetime
from typing import Optional


def get_holdings_raw(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("""
        SELECT
            pa.id AS portfolio_asset_id,
            pa.market_code,
            ma.ticker,
            ma.name,
            ma.asset_type,
            ma.currency_code,
            pa.layer,
            pa.tracking_mode,
            pa.current_value_manual,
            COALESCE(SUM(CASE WHEN t.type = 'INVESTMENT_BUY' THEN t.quantity ELSE 0 END), 0) AS total_bought_qty,
            COALESCE(SUM(CASE WHEN t.type = 'INVESTMENT_BUY' THEN t.total_value ELSE 0 END), 0) AS total_cost,
            COALESCE(SUM(CASE WHEN t.type = 'INVESTMENT_SELL' THEN t.quantity ELSE 0 END), 0) AS total_sold_qty,
            COALESCE(SUM(CASE WHEN t.type = 'INVESTMENT_SELL' THEN t.total_value ELSE 0 END), 0) AS total_proceeds
        FROM portfolio_assets pa
        JOIN market_assets ma ON ma.market_code = pa.market_code
        LEFT JOIN transactions t ON t.portfolio_asset_id = pa.id
        WHERE pa.is_active = 1
        GROUP BY pa.id
        ORDER BY pa.id
    """).fetchall()
    return [dict(r) for r in rows]


def get_latest_prices(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("""
        SELECT p1.market_code, p1.price, p1.timestamp
        FROM prices p1
        WHERE NOT EXISTS (
            SELECT 1 FROM prices p2
            WHERE p2.market_code = p1.market_code
            AND p2.timestamp > p1.timestamp
        )
    """).fetchall()
    return [dict(r) for r in rows]


def get_cash_balance(conn: sqlite3.Connection) -> float:
    row = conn.execute("""
        SELECT COALESCE(SUM(
            CASE
                WHEN type IN ('MONEY_IN', 'INTEREST', 'DIVIDEND', 'INVESTMENT_SELL') THEN total_value
                WHEN type IN ('MONEY_OUT', 'INVESTMENT_BUY') THEN -total_value
                ELSE 0
            END
        ), 0) AS cash_balance
        FROM transactions
    """).fetchone()
    return row["cash_balance"] if row else 0.0


def get_cash_flow(
    conn: sqlite3.Connection,
    group_by: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> list[dict]:
    period_map = {
        "day": "strftime('%Y-%m-%d', timestamp)",
        "week": "strftime('%Y-%W', timestamp)",
        "month": "strftime('%Y-%m', timestamp)",
        "quarter": "printf('%s-Q%d', strftime('%Y', timestamp), (cast(strftime('%m', timestamp) as integer) + 2) / 3)",
        "year": "strftime('%Y', timestamp)",
    }
    period_expr = period_map[group_by]
    params: list = []
    clauses: list[str] = []
    if start is not None:
        clauses.append("timestamp >= ?")
        params.append(start)
    if end is not None:
        clauses.append("timestamp <= ?")
        params.append(end)
    where = " AND ".join(clauses) if clauses else "1=1"
    rows = conn.execute(f"""
        SELECT {period_expr} AS period,
               type,
               SUM(total_value) AS total_value,
               COUNT(*) AS count,
               currency
        FROM transactions
        WHERE {where}
        GROUP BY period, type, currency
        ORDER BY period DESC, type
    """, params).fetchall()
    return [dict(r) for r in rows]


def get_dividends(
    conn: sqlite3.Connection,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> list[dict]:
    params: list = []
    clauses: list[str] = []
    if start is not None:
        clauses.append("t.timestamp >= ?")
        params.append(start)
    if end is not None:
        clauses.append("t.timestamp <= ?")
        params.append(end)
    where = " AND ".join(clauses) if clauses else "1=1"
    rows = conn.execute(f"""
        SELECT t.portfolio_asset_id,
               pa.market_code,
               ma.ticker,
               ma.name,
               t.currency,
               SUM(t.total_value) AS total_dividends,
               COUNT(*) AS count
        FROM transactions t
        LEFT JOIN portfolio_assets pa ON pa.id = t.portfolio_asset_id
        LEFT JOIN market_assets ma ON ma.market_code = pa.market_code
        WHERE t.type = 'DIVIDEND' AND {where}
        GROUP BY t.portfolio_asset_id, t.currency
        ORDER BY total_dividends DESC
    """, params).fetchall()
    return [dict(r) for r in rows]


def get_fees_raw(
    conn: sqlite3.Connection,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> list[dict]:
    params: list = []
    clauses: list[str] = []
    if start is not None:
        clauses.append("t.timestamp >= ?")
        params.append(start)
    if end is not None:
        clauses.append("t.timestamp <= ?")
        params.append(end)
    where = " AND ".join(clauses) if clauses else "1=1"
    rows = conn.execute(f"""
        SELECT tf.fee_type, tf.nature, tf.fixed_amount, tf.percentage, tf.currency,
               t.total_value AS tx_total
        FROM transaction_fees tf
        JOIN transactions t ON t.id = tf.transaction_id
        WHERE {where}
    """, params).fetchall()
    return [dict(r) for r in rows]


def get_taxes_raw(
    conn: sqlite3.Connection,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> list[dict]:
    params: list = []
    clauses: list[str] = []
    if start is not None:
        clauses.append("t.timestamp >= ?")
        params.append(start)
    if end is not None:
        clauses.append("t.timestamp <= ?")
        params.append(end)
    where = " AND ".join(clauses) if clauses else "1=1"
    rows = conn.execute(f"""
        SELECT tt.tax_type, tt.tax_amount, tt.currency
        FROM transaction_taxes tt
        JOIN transactions t ON t.id = tt.transaction_id
        WHERE {where}
    """, params).fetchall()
    return [dict(r) for r in rows]
