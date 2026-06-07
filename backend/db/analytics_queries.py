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
            ma.asset_class,
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


def get_holdings_by_entity_raw(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("""
        WITH asset_entity AS (
            SELECT
                t.portfolio_asset_id,
                t.entity_id,
                ROW_NUMBER() OVER (
                    PARTITION BY t.portfolio_asset_id
                    ORDER BY t.timestamp ASC, t.id ASC
                ) AS rn
            FROM transactions t
            WHERE t.portfolio_asset_id IS NOT NULL
        ),
        primary_entity AS (
            SELECT portfolio_asset_id, entity_id
            FROM asset_entity
            WHERE rn = 1
        ),
        net_qty AS (
            SELECT
                portfolio_asset_id,
                COALESCE(SUM(CASE WHEN type = 'INVESTMENT_BUY' THEN quantity ELSE 0 END), 0)
                - COALESCE(SUM(CASE WHEN type = 'INVESTMENT_SELL' THEN quantity ELSE 0 END), 0) AS net_quantity
            FROM transactions
            WHERE portfolio_asset_id IS NOT NULL
            GROUP BY portfolio_asset_id
        ),
        latest_prices AS (
            SELECT market_code, price
            FROM prices p1
            WHERE NOT EXISTS (
                SELECT 1 FROM prices p2
                WHERE p2.market_code = p1.market_code AND p2.timestamp > p1.timestamp
            )
        )
        SELECT
            COALESCE(pe.entity_id, -1) AS entity_id,
            COALESCE(e.name, 'Unassigned') AS entity_name,
            ma.asset_class,
            SUM(
                CASE
                    WHEN pa.tracking_mode = 'manual' AND pa.current_value_manual IS NOT NULL
                        THEN pa.current_value_manual
                    WHEN COALESCE(nq.net_quantity, 0) > 0 AND lp.price IS NOT NULL
                        THEN nq.net_quantity * lp.price
                    ELSE 0
                END
            ) AS current_value
        FROM portfolio_assets pa
        JOIN market_assets ma ON ma.market_code = pa.market_code
        LEFT JOIN net_qty nq ON nq.portfolio_asset_id = pa.id
        LEFT JOIN latest_prices lp ON lp.market_code = pa.market_code
        LEFT JOIN primary_entity pe ON pe.portfolio_asset_id = pa.id
        LEFT JOIN entities e ON e.id = pe.entity_id
        WHERE pa.is_active = 1
        GROUP BY pe.entity_id, ma.asset_class
        ORDER BY entity_name, asset_class
    """).fetchall()
    return [dict(r) for r in rows]


def get_cash_by_entity_raw(conn: sqlite3.Connection) -> list[dict]:
    from db.queries import get_balance_at_date

    snapshot_pairs = conn.execute(
        "SELECT DISTINCT entity_id, currency FROM balance_snapshots"
    ).fetchall()

    entity_currencies: dict[int, list[str]] = {}
    for row in snapshot_pairs:
        eid = row["entity_id"]
        if eid not in entity_currencies:
            entity_currencies[eid] = []
        entity_currencies[eid].append(row["currency"])

    results = []
    for eid, currencies in entity_currencies.items():
        total = 0.0
        for cur in currencies:
            balance = get_balance_at_date(conn, eid, cur, datetime.now().isoformat())
            total += balance
        name_row = conn.execute(
            "SELECT name FROM entities WHERE id = ?", (eid,)
        ).fetchone()
        results.append({
            "entity_id": eid,
            "entity_name": name_row["name"] if name_row else f"Entity #{eid}",
            "cash_balance": total,
        })

    non_snapshot_rows = conn.execute("""
        SELECT
            t.entity_id,
            e.name AS entity_name,
            SUM(
                CASE
                    WHEN t.type IN ('MONEY_IN', 'INTEREST', 'DIVIDEND', 'INVESTMENT_SELL') THEN t.total_value
                    WHEN t.type IN ('MONEY_OUT', 'INVESTMENT_BUY') THEN -t.total_value
                    ELSE 0
                END
            ) AS cash_balance
        FROM transactions t
        JOIN entities e ON e.id = t.entity_id
        WHERE t.timestamp <= datetime('now')
          AND (t.entity_id, t.currency) NOT IN (SELECT DISTINCT entity_id, currency FROM balance_snapshots)
        GROUP BY t.entity_id
    """).fetchall()
    for r in non_snapshot_rows:
        results.append(dict(r))

    return results


def get_cash_balance_by_currency(conn: sqlite3.Connection) -> list[dict]:
    from db.queries import get_balance_at_date

    pairs = conn.execute(
        "SELECT DISTINCT entity_id, currency FROM balance_snapshots"
    ).fetchall()

    results = []
    for row in pairs:
        eid = row["entity_id"]
        cur = row["currency"]
        balance = get_balance_at_date(conn, eid, cur, datetime.now().isoformat())
        results.append({
            "entity_id": eid,
            "currency": cur,
            "balance": balance,
        })

    non_snapshot_rows = conn.execute("""
        SELECT
            t.entity_id,
            t.currency,
            SUM(
                CASE
                    WHEN t.type IN ('MONEY_IN', 'INTEREST', 'DIVIDEND', 'INVESTMENT_SELL') THEN t.total_value
                    WHEN t.type IN ('MONEY_OUT', 'INVESTMENT_BUY') THEN -t.total_value
                    ELSE 0
                END
            ) AS balance
        FROM transactions t
        WHERE t.timestamp <= datetime('now')
          AND (t.entity_id, t.currency) NOT IN (SELECT DISTINCT entity_id, currency FROM balance_snapshots)
        GROUP BY t.entity_id, t.currency
    """).fetchall()
    for r in non_snapshot_rows:
        results.append(dict(r))

    return results


def get_cash_by_currency_history(
    conn: sqlite3.Connection,
    start: str,
    end: str,
    interval: str = "month",
) -> list[dict]:
    from db.queries import get_balance_at_date

    pairs = conn.execute(
        "SELECT DISTINCT entity_id, currency FROM balance_snapshots"
    ).fetchall()

    period_expr = {
        "day": "strftime('%Y-%m-%d', ?)",
        "month": "strftime('%Y-%m', ?)",
        "quarter": "printf('%s-Q%d', strftime('%Y', ?), (cast(strftime('%m', ?) as integer) + 2) / 3)",
        "year": "strftime('%Y', ?)",
    }.get(interval, "strftime('%Y-%m', ?)")

    dates = []
    d = datetime.strptime(start, "%Y-%m-%d")
    end_d = datetime.strptime(end, "%Y-%m-%d")
    while d <= end_d:
        dates.append(d)
        if interval == "day":
            from datetime import timedelta
            d += timedelta(days=1)
        elif interval == "month":
            month = d.month + 1
            year = d.year + (month - 1) // 12
            d = datetime(year, month, 1)
        elif interval == "quarter":
            month = d.month + 3
            year = d.year + (month - 1) // 12
            d = datetime(year, month, 1)
        elif interval == "year":
            d = datetime(d.year + 1, 1, 1)

    results = []
    for dt in dates:
        ts = dt.strftime("%Y-%m-%dT23:59:59")
        currency_totals: dict[str, float] = {}

        for row in pairs:
            eid = row["entity_id"]
            cur = row["currency"]
            balance = get_balance_at_date(conn, eid, cur, ts)
            currency_totals[cur] = currency_totals.get(cur, 0.0) + balance

        non_snapshot_rows = conn.execute("""
            SELECT
                t.currency,
                SUM(
                    CASE
                        WHEN t.type IN ('MONEY_IN', 'INTEREST', 'DIVIDEND', 'INVESTMENT_SELL') THEN t.total_value
                        WHEN t.type IN ('MONEY_OUT', 'INVESTMENT_BUY') THEN -t.total_value
                        ELSE 0
                    END
                ) AS balance
            FROM transactions t
            WHERE t.timestamp <= ?
              AND (t.entity_id, t.currency) NOT IN (SELECT DISTINCT entity_id, currency FROM balance_snapshots)
            GROUP BY t.currency
        """, (ts,)).fetchall()
        for r in non_snapshot_rows:
            cur = r["currency"]
            currency_totals[cur] = currency_totals.get(cur, 0.0) + r["balance"]

        period_key = dt.strftime("%Y-%m-%d") if interval == "day" else dt.strftime("%Y-%m")
        for cur, bal in currency_totals.items():
            results.append({
                "date": period_key,
                "currency": cur,
                "balance": bal,
            })

    return results


def get_total_cash_as_of(conn: sqlite3.Connection, timestamp: str) -> float:
    from db.queries import get_balance_at_date

    if "T" not in timestamp:
        timestamp = timestamp + "T23:59:59"

    pairs = conn.execute(
        "SELECT DISTINCT entity_id, currency FROM balance_snapshots"
    ).fetchall()

    total = 0.0
    for row in pairs:
        eid = row["entity_id"]
        cur = row["currency"]
        total += get_balance_at_date(conn, eid, cur, timestamp)

    ts_filter = f"timestamp <= '{timestamp}'" if timestamp != "now" else "timestamp <= datetime('now')"
    row = conn.execute(f"""
        SELECT COALESCE(SUM(
            CASE
                WHEN type IN ('MONEY_IN', 'INTEREST', 'DIVIDEND', 'INVESTMENT_SELL') THEN total_value
                WHEN type IN ('MONEY_OUT', 'INVESTMENT_BUY') THEN -total_value
                ELSE 0
            END
        ), 0) AS cash_balance
        FROM transactions
        WHERE {ts_filter}
          AND (entity_id, currency) NOT IN (SELECT DISTINCT entity_id, currency FROM balance_snapshots)
    """).fetchone()
    total += row["cash_balance"] if row else 0.0
    return total


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


def get_cash_balance(
    conn: sqlite3.Connection,
    entity_id: int | None = None,
    currency: str | None = None,
    timestamp: str | None = None,
) -> float:
    if entity_id is not None and currency is not None:
        from db.queries import get_balance_at_date
        ts = timestamp or "now"
        return get_balance_at_date(conn, entity_id, currency, ts)

    pairs = conn.execute(
        "SELECT DISTINCT entity_id, currency FROM balance_snapshots"
    ).fetchall()

    total = 0.0
    for row in pairs:
        eid = row["entity_id"]
        cur = row["currency"]
        from db.queries import get_balance_at_date
        ts = timestamp or "now"
        total += get_balance_at_date(conn, eid, cur, ts)

    ts_filter = f"timestamp <= '{timestamp}'" if timestamp else "timestamp <= datetime('now')"
    row = conn.execute(f"""
        SELECT COALESCE(SUM(
            CASE
                WHEN type IN ('MONEY_IN', 'INTEREST', 'DIVIDEND', 'INVESTMENT_SELL') THEN total_value
                WHEN type IN ('MONEY_OUT', 'INVESTMENT_BUY') THEN -total_value
                ELSE 0
            END
        ), 0) AS cash_balance
        FROM transactions
        WHERE {ts_filter}
          AND (entity_id, currency) NOT IN (SELECT DISTINCT entity_id, currency FROM balance_snapshots)
    """).fetchone()
    total += row["cash_balance"] if row else 0.0
    return total


def get_cash_flow_raw(
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


def get_income_by_source_raw(
    conn: sqlite3.Connection,
    group_by: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> list[dict]:
    period_map = {
        "day": "strftime('%Y-%m-%d', t.timestamp)",
        "week": "strftime('%Y-%W', t.timestamp)",
        "month": "strftime('%Y-%m', t.timestamp)",
        "quarter": "printf('%s-Q%d', strftime('%Y', t.timestamp), (cast(strftime('%m', t.timestamp) as integer) + 2) / 3)",
        "year": "strftime('%Y', t.timestamp)",
    }
    period_expr = period_map[group_by]
    params: list = []
    clauses: list[str] = ["t.type IN ('MONEY_IN', 'INTEREST', 'DIVIDEND')"]
    if start is not None:
        clauses.append("t.timestamp >= ?")
        params.append(start)
    if end is not None:
        clauses.append("t.timestamp <= ?")
        params.append(end)
    where = " AND ".join(clauses)
    rows = conn.execute(f"""
        SELECT {period_expr} AS period,
               t.entity_id,
               e.name AS entity_name,
               SUM(t.total_value) AS total_value,
               COUNT(*) AS count
        FROM transactions t
        JOIN entities e ON e.id = t.entity_id
        WHERE {where}
        GROUP BY period, t.entity_id
        ORDER BY period DESC, total_value DESC
    """, params).fetchall()
    return [dict(r) for r in rows]


def get_dividends_raw(
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


def get_buy_sell_transactions(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("""
        SELECT t.id AS transaction_id,
               t.portfolio_asset_id,
               pa.market_code,
               ma.ticker,
               ma.name,
               t.type,
               t.timestamp,
               t.quantity,
               t.unit_price,
               t.total_value,
               t.currency
        FROM transactions t
        JOIN portfolio_assets pa ON pa.id = t.portfolio_asset_id
        JOIN market_assets ma ON ma.market_code = pa.market_code
        WHERE t.type IN ('INVESTMENT_BUY', 'INVESTMENT_SELL')
          AND pa.is_active = 1
        ORDER BY t.portfolio_asset_id, t.timestamp, t.id
    """).fetchall()
    return [dict(r) for r in rows]


def get_net_positions_as_of(conn: sqlite3.Connection, cutoff: str, entity_id: int | None = None) -> list[dict]:
    if entity_id is not None:
        rows = conn.execute("""
            WITH primary_entity AS (
                SELECT
                    t.portfolio_asset_id,
                    t.entity_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY t.portfolio_asset_id
                        ORDER BY t.timestamp ASC, t.id ASC
                    ) AS rn
                FROM transactions t
                WHERE t.portfolio_asset_id IS NOT NULL
            )
            SELECT t.portfolio_asset_id,
                   pa.market_code,
                   COALESCE(SUM(CASE WHEN t.type = 'INVESTMENT_BUY' THEN t.quantity ELSE 0 END), 0)
                   - COALESCE(SUM(CASE WHEN t.type = 'INVESTMENT_SELL' THEN t.quantity ELSE 0 END), 0) AS net_quantity
            FROM transactions t
            JOIN portfolio_assets pa ON pa.id = t.portfolio_asset_id
            JOIN primary_entity pe ON pe.portfolio_asset_id = t.portfolio_asset_id AND pe.rn = 1
            WHERE pa.is_active = 1
              AND t.type IN ('INVESTMENT_BUY', 'INVESTMENT_SELL')
              AND t.timestamp <= ?
              AND pe.entity_id = ?
            GROUP BY t.portfolio_asset_id
            HAVING net_quantity > 0
        """, (cutoff, entity_id)).fetchall()
    else:
        rows = conn.execute("""
            SELECT t.portfolio_asset_id,
                   pa.market_code,
                   COALESCE(SUM(CASE WHEN t.type = 'INVESTMENT_BUY' THEN t.quantity ELSE 0 END), 0)
                   - COALESCE(SUM(CASE WHEN t.type = 'INVESTMENT_SELL' THEN t.quantity ELSE 0 END), 0) AS net_quantity
            FROM transactions t
            JOIN portfolio_assets pa ON pa.id = t.portfolio_asset_id
            WHERE pa.is_active = 1
              AND t.type IN ('INVESTMENT_BUY', 'INVESTMENT_SELL')
              AND t.timestamp <= ?
            GROUP BY t.portfolio_asset_id
            HAVING net_quantity > 0
        """, (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def get_all_prices(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("""
        SELECT market_code, timestamp, price
        FROM prices
        ORDER BY market_code, timestamp
    """).fetchall()
    return [dict(r) for r in rows]


def get_cash_by_currency_as_of(conn: sqlite3.Connection, cutoff: str) -> dict[str, float]:
    rows = conn.execute("""
        SELECT t.currency,
            COALESCE(SUM(
                CASE
                    WHEN t.type IN ('MONEY_IN', 'INTEREST', 'DIVIDEND', 'INVESTMENT_SELL') THEN t.total_value
                    WHEN t.type IN ('MONEY_OUT', 'INVESTMENT_BUY') THEN -t.total_value
                    ELSE 0
                END
            ), 0) AS cash_balance
        FROM transactions t
        WHERE t.timestamp <= ?
        GROUP BY t.currency
    """, (cutoff,)).fetchall()
    return {r["currency"]: r["cash_balance"] for r in rows}


def get_investment_by_currency_as_of(conn: sqlite3.Connection, cutoff: str) -> dict[str, float]:
    from bisect import bisect_right
    from collections import defaultdict

    positions = get_net_positions_as_of(conn, cutoff)
    if not positions:
        return {}

    all_prices = get_all_prices(conn)
    price_index: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for p in all_prices:
        price_index[p["market_code"]].append((p["timestamp"], p["price"]))
    for mc in price_index:
        price_index[mc].sort(key=lambda x: x[0])
    price_ts_list = {mc: [x[0] for x in entries] for mc, entries in price_index.items()}

    market_currencies = dict(
        conn.execute("SELECT code, currency_code FROM market_assets").fetchall()
    )

    result: dict[str, float] = defaultdict(float)
    for pos in positions:
        mc = pos["market_code"]
        entries = price_index.get(mc, [])
        ts_list = price_ts_list.get(mc, [])
        if not ts_list:
            continue
        idx = bisect_right(ts_list, cutoff) - 1
        if idx < 0:
            continue
        price = entries[idx][1]
        currency = market_currencies.get(mc)
        if currency:
            result[currency] += pos["net_quantity"] * price

    return dict(result)
