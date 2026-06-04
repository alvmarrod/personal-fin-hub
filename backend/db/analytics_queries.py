import sqlite3


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
