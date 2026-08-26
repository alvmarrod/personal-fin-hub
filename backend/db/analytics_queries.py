import sqlite3
from collections import defaultdict
from datetime import UTC, datetime

from db.queries import _pid, _profile_clause, _profile_params, compute_fee_cash_out_at, get_entity


def _apply_fee_corrections(conn: sqlite3.Connection, rows: list[dict], timestamp: str) -> list[dict]:
    """Subtract fee/tax cash-outs from non-snapshot balance rows.

    Each row must contain ``entity_id`` and ``currency``.  The fee is
    subtracted only when ``currency`` matches the entity's
    ``main_currency`` (fees always charge the main pocket).
    """
    entity_cache: dict[int, dict | None] = {}
    for r in rows:
        eid = r["entity_id"]
        if eid not in entity_cache:
            entity_cache[eid] = get_entity(conn, eid)
        ent = entity_cache[eid]
        if ent is None or ent.get("main_currency") != r["currency"]:
            continue
        r["balance"] -= compute_fee_cash_out_at(conn, eid, r["currency"], timestamp)
    return rows


def get_holdings_raw(conn: sqlite3.Connection) -> list[dict]:
    pid_clause = _profile_clause(conn, "pa.profile_id")
    rows = conn.execute(
        f"""
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
        WHERE pa.is_active = 1{pid_clause}
        GROUP BY pa.id
        ORDER BY pa.id
    """,
        _profile_params(conn),
    ).fetchall()
    return [dict(r) for r in rows]


def get_holdings_by_entity_raw(conn: sqlite3.Connection) -> list[dict]:
    pid_clause_t = _profile_clause(conn, "t.profile_id")
    pid_clause_plain = _profile_clause(conn)
    pid_clause_pa = _profile_clause(conn, "pa.profile_id")
    pid_clause_e = _profile_clause(conn, "e.profile_id")
    rows = conn.execute(
        f"""
        WITH asset_entity AS (
            SELECT
                t.portfolio_asset_id,
                t.entity_id,
                ROW_NUMBER() OVER (
                    PARTITION BY t.portfolio_asset_id
                    ORDER BY t.timestamp ASC, t.id ASC
                ) AS rn
            FROM transactions t
            WHERE t.portfolio_asset_id IS NOT NULL{pid_clause_t}
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
            WHERE portfolio_asset_id IS NOT NULL{pid_clause_plain}
            GROUP BY portfolio_asset_id
        ),
        cost_basis AS (
            SELECT
                portfolio_asset_id,
                COALESCE(SUM(CASE WHEN type = 'INVESTMENT_BUY' THEN total_value ELSE 0 END), 0) AS total_cost
            FROM transactions
            WHERE portfolio_asset_id IS NOT NULL{pid_clause_plain}
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
            ma.currency_code,
            SUM(
                CASE
                    WHEN pa.tracking_mode = 'manual' AND pa.current_value_manual IS NOT NULL
                        THEN pa.current_value_manual
                    WHEN COALESCE(nq.net_quantity, 0) > 0 AND lp.price IS NOT NULL
                        THEN nq.net_quantity * lp.price
                    WHEN COALESCE(nq.net_quantity, 0) > 0
                        THEN cb.total_cost
                    ELSE 0
                END
            ) AS current_value
        FROM portfolio_assets pa
        JOIN market_assets ma ON ma.market_code = pa.market_code
        LEFT JOIN net_qty nq ON nq.portfolio_asset_id = pa.id
        LEFT JOIN cost_basis cb ON cb.portfolio_asset_id = pa.id
        LEFT JOIN latest_prices lp ON lp.market_code = pa.market_code
        LEFT JOIN primary_entity pe ON pe.portfolio_asset_id = pa.id
        LEFT JOIN entities e ON e.id = pe.entity_id{pid_clause_e}
        WHERE pa.is_active = 1{pid_clause_pa}
        GROUP BY pe.entity_id, ma.asset_class, ma.currency_code
        ORDER BY entity_name, asset_class
    """,
        _profile_params(conn) * 5,
    ).fetchall()
    return [dict(r) for r in rows]


def get_cash_by_entity_raw(conn: sqlite3.Connection) -> list[dict]:
    from db.queries import get_balance_at_date

    snapshot_pairs = conn.execute(
        "SELECT DISTINCT entity_id, currency FROM balance_snapshots WHERE 1=1" + _profile_clause(conn),
        _profile_params(conn),
    ).fetchall()

    entity_currencies: dict[int, list[str]] = {}
    for row in snapshot_pairs:
        eid = row["entity_id"]
        if eid not in entity_currencies:
            entity_currencies[eid] = []
        entity_currencies[eid].append(row["currency"])

    results = []
    for eid, currencies in entity_currencies.items():
        for cur in currencies:
            balance = get_balance_at_date(conn, eid, cur, datetime.now(UTC).isoformat())
            name_row = conn.execute(
                "SELECT name FROM entities WHERE id = ?" + _profile_clause(conn),
                (eid,) + _profile_params(conn),
            ).fetchone()
            results.append(
                {
                    "entity_id": eid,
                    "entity_name": name_row["name"] if name_row else f"Entity #{eid}",
                    "currency": cur,
                    "cash_balance": balance,
                }
            )

    pid_clause_t = _profile_clause(conn, "t.profile_id")
    pid_clause_plain = _profile_clause(conn)
    non_snapshot_rows = conn.execute(
        f"""
        SELECT
            t.entity_id,
            e.name AS entity_name,
            t.currency,
            SUM(
                CASE
                    WHEN t.type IN ('INCOME', 'INVESTMENT_SELL', 'TRANSFER_IN') THEN t.total_value
                    WHEN t.type IN ('MONEY_OUT', 'INVESTMENT_BUY', 'TRANSFER_OUT') THEN -t.total_value
                    WHEN t.type = 'BALANCE_ADJUSTMENT' THEN t.total_value
                    ELSE 0
                END
            ) AS cash_balance
        FROM transactions t
        JOIN entities e ON e.id = t.entity_id
        WHERE t.timestamp <= datetime('now'){pid_clause_t}
          AND (t.entity_id, t.currency) NOT IN (SELECT DISTINCT entity_id, currency FROM balance_snapshots WHERE 1=1{pid_clause_plain})
        GROUP BY t.entity_id, t.currency
    """,
        _profile_params(conn) * 2,
    ).fetchall()
    for r in non_snapshot_rows:
        results.append(dict(r))

    return results


def get_cash_balance_by_currency(conn: sqlite3.Connection) -> list[dict]:
    from db.queries import get_balance_at_date

    pairs = conn.execute(
        "SELECT DISTINCT entity_id, currency FROM balance_snapshots WHERE 1=1" + _profile_clause(conn),
        _profile_params(conn),
    ).fetchall()

    results = []
    for row in pairs:
        eid = row["entity_id"]
        cur = row["currency"]
        balance = get_balance_at_date(conn, eid, cur, datetime.now(UTC).isoformat())
        results.append(
            {
                "entity_id": eid,
                "currency": cur,
                "balance": balance,
            }
        )

    pid_clause_t = _profile_clause(conn, "t.profile_id")
    pid_clause_plain = _profile_clause(conn)
    non_snapshot_rows = conn.execute(
        f"""
        SELECT
            t.entity_id,
            t.currency,
            SUM(
                CASE
                    WHEN t.type IN ('INCOME', 'INVESTMENT_SELL', 'TRANSFER_IN') THEN t.total_value
                    WHEN t.type IN ('MONEY_OUT', 'INVESTMENT_BUY', 'TRANSFER_OUT') THEN -t.total_value
                    WHEN t.type = 'BALANCE_ADJUSTMENT' THEN t.total_value
                    ELSE 0
                END
            ) AS balance
        FROM transactions t
        WHERE t.timestamp <= datetime('now'){pid_clause_t}
          AND (t.entity_id, t.currency) NOT IN (SELECT DISTINCT entity_id, currency FROM balance_snapshots WHERE 1=1{pid_clause_plain})
        GROUP BY t.entity_id, t.currency
    """,
        _profile_params(conn) * 2,
    ).fetchall()
    for r in non_snapshot_rows:
        results.append(dict(r))

    _apply_fee_corrections(conn, [r for r in results if "entity_id" in r], datetime.now(UTC).isoformat())

    return results


def get_cash_by_currency_history(
    conn: sqlite3.Connection,
    start: str,
    end: str,
    interval: str = "month",
) -> list[dict]:
    from db.queries import get_balance_at_date

    pairs = conn.execute(
        "SELECT DISTINCT entity_id, currency FROM balance_snapshots WHERE 1=1" + _profile_clause(conn),
        _profile_params(conn),
    ).fetchall()

    period_expr = {  # noqa: F841
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

        pid_clause_t = _profile_clause(conn, "t.profile_id")
        pid_clause_plain = _profile_clause(conn)
        non_snapshot_rows = conn.execute(
            f"""
            SELECT
                t.currency,
                SUM(
                    CASE
                        WHEN t.type IN ('INCOME', 'INVESTMENT_SELL', 'TRANSFER_IN') THEN t.total_value
                        WHEN t.type IN ('MONEY_OUT', 'INVESTMENT_BUY', 'TRANSFER_OUT') THEN -t.total_value
                        WHEN t.type = 'BALANCE_ADJUSTMENT' THEN t.total_value
                        ELSE 0
                    END
                ) AS balance
            FROM transactions t
            WHERE t.timestamp <= ?{pid_clause_t}
              AND (t.entity_id, t.currency) NOT IN (SELECT DISTINCT entity_id, currency FROM balance_snapshots WHERE 1=1{pid_clause_plain})
            GROUP BY t.currency
        """,
            (ts,) + _profile_params(conn) * 2,
        ).fetchall()
        for r in non_snapshot_rows:
            cur = r["currency"]
            currency_totals[cur] = currency_totals.get(cur, 0.0) + r["balance"]

        period_key = dt.strftime("%Y-%m-%d") if interval == "day" else dt.strftime("%Y-%m")
        for cur, bal in currency_totals.items():
            results.append(
                {
                    "date": period_key,
                    "currency": cur,
                    "balance": bal,
                }
            )

    return results


def get_total_cash_as_of(conn: sqlite3.Connection, timestamp: str) -> float:
    from db.queries import get_balance_at_date

    if "T" not in timestamp:
        timestamp = timestamp + "T23:59:59"

    pairs = conn.execute(
        "SELECT DISTINCT entity_id, currency FROM balance_snapshots WHERE 1=1" + _profile_clause(conn),
        _profile_params(conn),
    ).fetchall()

    total = 0.0
    for row in pairs:
        eid = row["entity_id"]
        cur = row["currency"]
        total += get_balance_at_date(conn, eid, cur, timestamp)

    ts_filter = f"timestamp <= '{timestamp}'" if timestamp != "now" else "timestamp <= datetime('now')"
    pid_clause = _profile_clause(conn)
    row = conn.execute(
        f"""
        SELECT COALESCE(SUM(
            CASE
                WHEN type IN ('INCOME', 'INVESTMENT_SELL', 'TRANSFER_IN') THEN total_value
                WHEN type IN ('MONEY_OUT', 'INVESTMENT_BUY', 'TRANSFER_OUT') THEN -total_value
                WHEN type = 'BALANCE_ADJUSTMENT' THEN total_value
                ELSE 0
            END
        ), 0) AS cash_balance
        FROM transactions
        WHERE {ts_filter}{pid_clause}
          AND (entity_id, currency) NOT IN (SELECT DISTINCT entity_id, currency FROM balance_snapshots WHERE 1=1{pid_clause})
    """,
        _profile_params(conn) * 2,
    ).fetchone()
    total += row["cash_balance"] if row else 0.0
    return total


def get_entity_cash_as_of(conn: sqlite3.Connection, entity_id: int, timestamp: str) -> float:
    from db.queries import get_balance_at_date

    if "T" not in timestamp:
        timestamp = timestamp + "T23:59:59"

    pairs = conn.execute(
        "SELECT DISTINCT currency FROM balance_snapshots WHERE entity_id = ?" + _profile_clause(conn),
        (entity_id,) + _profile_params(conn),
    ).fetchall()

    total = 0.0
    for row in pairs:
        cur = row["currency"]
        total += get_balance_at_date(conn, entity_id, cur, timestamp)

    ts_filter = f"timestamp <= '{timestamp}'"
    pid_clause = _profile_clause(conn)
    row = conn.execute(
        f"""
        SELECT COALESCE(SUM(
            CASE
                WHEN type IN ('INCOME', 'INVESTMENT_SELL', 'TRANSFER_IN') THEN total_value
                WHEN type IN ('MONEY_OUT', 'INVESTMENT_BUY', 'TRANSFER_OUT') THEN -total_value
                WHEN type = 'BALANCE_ADJUSTMENT' THEN total_value
                ELSE 0
            END
        ), 0) AS cash_balance
        FROM transactions
        WHERE entity_id = ? AND {ts_filter}{pid_clause}
          AND (entity_id, currency) NOT IN (SELECT DISTINCT entity_id, currency FROM balance_snapshots WHERE 1=1{pid_clause})
    """,
        (entity_id,) + _profile_params(conn) * 2,
    ).fetchone()
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
        "SELECT DISTINCT entity_id, currency FROM balance_snapshots WHERE 1=1" + _profile_clause(conn),
        _profile_params(conn),
    ).fetchall()

    total = 0.0
    for row in pairs:
        eid = row["entity_id"]
        cur = row["currency"]
        from db.queries import get_balance_at_date

        ts = timestamp or "now"
        total += get_balance_at_date(conn, eid, cur, ts)

    ts_filter = f"timestamp <= '{timestamp}'" if timestamp else "timestamp <= datetime('now')"
    pid_clause = _profile_clause(conn)
    rows = conn.execute(
        f"""
        SELECT entity_id, currency,
            COALESCE(SUM(
                CASE
                    WHEN type IN ('INCOME', 'INVESTMENT_SELL', 'TRANSFER_IN') THEN total_value
                    WHEN type IN ('MONEY_OUT', 'INVESTMENT_BUY', 'TRANSFER_OUT') THEN -total_value
                    WHEN type = 'BALANCE_ADJUSTMENT' THEN total_value
                    ELSE 0
                END
            ), 0) AS cash_balance
        FROM transactions
        WHERE {ts_filter}{pid_clause}
          AND (entity_id, currency) NOT IN (SELECT DISTINCT entity_id, currency FROM balance_snapshots WHERE 1=1{pid_clause})
        GROUP BY entity_id, currency
    """,
        _profile_params(conn) * 2,
    ).fetchall()
    fee_rows = [{"entity_id": r["entity_id"], "currency": r["currency"], "balance": r["cash_balance"]} for r in rows]
    _apply_fee_corrections(conn, fee_rows, timestamp or datetime.now(UTC).isoformat())
    total += sum(r["balance"] for r in fee_rows)
    return total


def get_cash_flow_raw(
    conn: sqlite3.Connection,
    group_by: str,
    start: str | None = None,
    end: str | None = None,
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
    if _pid(conn) is not None:
        clauses.append("profile_id = ?")
        params.append(_pid(conn))
    where = " AND ".join(clauses) if clauses else "1=1"
    rows = conn.execute(
        f"""
        SELECT {period_expr} AS period,
               type,
               SUM(total_value) AS total_value,
               COUNT(*) AS count,
               currency
        FROM transactions
        WHERE {where}
        GROUP BY period, type, currency
        ORDER BY period DESC, type
    """,
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_income_by_source_raw(
    conn: sqlite3.Connection,
    group_by: str,
    start: str | None = None,
    end: str | None = None,
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
    clauses: list[str] = ["t.type = 'INCOME'"]
    if start is not None:
        clauses.append("t.timestamp >= ?")
        params.append(start)
    if end is not None:
        clauses.append("t.timestamp <= ?")
        params.append(end)
    if _pid(conn) is not None:
        clauses.append("t.profile_id = ?")
        params.append(_pid(conn))
    where = " AND ".join(clauses)
    rows = conn.execute(
        f"""
        SELECT {period_expr} AS period,
               t.entity_id,
               e.name AS entity_name,
               t.type,
               COALESCE(
                   t.income_category,
                   CASE
                       WHEN e.entity_type = 'EMPLOYER' THEN 'salary'
                       ELSE 'other'
                   END
               ) AS income_category,
               t.currency,
               SUM(t.total_value) AS total_value,
               COUNT(*) AS count
        FROM transactions t
        JOIN entities e ON e.id = t.entity_id
        WHERE {where}
        GROUP BY period, t.entity_id, t.type, t.currency, income_category
        ORDER BY period DESC, total_value DESC
    """,
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_dividends_raw(
    conn: sqlite3.Connection,
    start: str | None = None,
    end: str | None = None,
) -> list[dict]:
    params: list = []
    clauses: list[str] = []
    if start is not None:
        clauses.append("t.timestamp >= ?")
        params.append(start)
    if end is not None:
        clauses.append("t.timestamp <= ?")
        params.append(end)
    if _pid(conn) is not None:
        clauses.append("t.profile_id = ?")
        params.append(_pid(conn))
    where = " AND ".join(clauses) if clauses else "1=1"
    rows = conn.execute(
        f"""
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
        WHERE t.income_category = 'dividends' AND {where}
        GROUP BY t.portfolio_asset_id, t.currency
        ORDER BY total_dividends DESC
    """,
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_dividend_transactions(
    conn: sqlite3.Connection,
    start: str | None = None,
    end: str | None = None,
) -> list[dict]:
    """Return dividend transactions (gross, currency, date, exemption, asset info) for tax reporting."""
    clauses: list[str] = []
    params: list = []
    if start is not None:
        clauses.append("t.timestamp >= ?")
        params.append(start)
    if end is not None:
        clauses.append("t.timestamp <= ?")
        params.append(end)
    extra = (" AND " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(
        "SELECT t.id, t.timestamp, t.payment_date, t.currency, t.total_value, t.fiscal_exemption_id, "
        "t.portfolio_asset_id, t.entity_id, "
        "pa.market_code, ma.ticker, ma.name AS asset_name, "
        "e.name AS entity_name "
        "FROM transactions t "
        "LEFT JOIN portfolio_assets pa ON pa.id = t.portfolio_asset_id "
        "LEFT JOIN market_assets ma ON ma.market_code = pa.market_code "
        "JOIN entities e ON e.id = t.entity_id "
        "WHERE t.income_category = 'dividends'"
        + extra
        + _profile_clause(conn, "t.profile_id")
        + " ORDER BY t.timestamp, t.id",
        [*params, *_profile_params(conn)],
    ).fetchall()
    return [dict(r) for r in rows]


def get_fees_raw(
    conn: sqlite3.Connection,
    start: str | None = None,
    end: str | None = None,
) -> list[dict]:
    params: list = []
    clauses: list[str] = []
    if start is not None:
        clauses.append("t.timestamp >= ?")
        params.append(start)
    if end is not None:
        clauses.append("t.timestamp <= ?")
        params.append(end)
    if _pid(conn) is not None:
        clauses.append("t.profile_id = ?")
        params.append(_pid(conn))
    where = " AND ".join(clauses) if clauses else "1=1"
    rows = conn.execute(
        f"""
        SELECT tf.fee_type, tf.nature, tf.fixed_amount, tf.percentage, tf.currency,
               t.total_value AS tx_total
        FROM transaction_fees tf
        JOIN transactions t ON t.id = tf.transaction_id
        WHERE {where}
    """,
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_taxes_raw(
    conn: sqlite3.Connection,
    start: str | None = None,
    end: str | None = None,
) -> list[dict]:
    params: list = []
    clauses: list[str] = []
    if start is not None:
        clauses.append("t.timestamp >= ?")
        params.append(start)
    if end is not None:
        clauses.append("t.timestamp <= ?")
        params.append(end)
    if _pid(conn) is not None:
        clauses.append("t.profile_id = ?")
        params.append(_pid(conn))
    where = " AND ".join(clauses) if clauses else "1=1"
    rows = conn.execute(
        f"""
        SELECT tt.tax_type, tt.tax_amount, tt.currency
        FROM transaction_taxes tt
        JOIN transactions t ON t.id = tt.transaction_id
        WHERE {where}
    """,
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_buy_sell_transactions(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
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
               t.currency,
               t.payment_currency,
               t.fx_rate,
               t.fiscal_rule,
               t.fiscal_exemption_id
        FROM transactions t
        JOIN portfolio_assets pa ON pa.id = t.portfolio_asset_id
        JOIN market_assets ma ON ma.market_code = pa.market_code
        WHERE t.type IN ('INVESTMENT_BUY', 'INVESTMENT_SELL')"""
        + _profile_clause(conn, "t.profile_id")
        + " ORDER BY t.portfolio_asset_id, t.timestamp, t.id",
        _profile_params(conn),
    ).fetchall()
    return [dict(r) for r in rows]


def get_net_positions_as_of(
    conn: sqlite3.Connection, cutoff: str, entity_id: int | None = None, include_inactive: bool = False
) -> list[dict]:
    active_filter = "" if include_inactive else "AND pa.is_active = 1"
    profile_clause = _profile_clause(conn, "t.profile_id")
    if entity_id is not None:
        rows = conn.execute(
            f"""
            WITH primary_entity AS (
                SELECT
                    t.portfolio_asset_id,
                    t.entity_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY t.portfolio_asset_id
                        ORDER BY t.timestamp ASC, t.id ASC
                    ) AS rn
                FROM transactions t
                WHERE t.portfolio_asset_id IS NOT NULL{profile_clause}
            )
            SELECT t.portfolio_asset_id,
                   pa.market_code,
                   ma.currency_code,
                   COALESCE(SUM(CASE WHEN t.type = 'INVESTMENT_BUY' THEN t.quantity ELSE 0 END), 0)
                   - COALESCE(SUM(CASE WHEN t.type = 'INVESTMENT_SELL' THEN t.quantity ELSE 0 END), 0) AS net_quantity
            FROM transactions t
            JOIN portfolio_assets pa ON pa.id = t.portfolio_asset_id
            JOIN market_assets ma ON ma.market_code = pa.market_code
            JOIN primary_entity pe ON pe.portfolio_asset_id = t.portfolio_asset_id AND pe.rn = 1
            WHERE t.type IN ('INVESTMENT_BUY', 'INVESTMENT_SELL')
              AND t.timestamp <= ?
              AND pe.entity_id = ?
              {active_filter}
              {profile_clause}
            GROUP BY t.portfolio_asset_id
            HAVING net_quantity > 0
        """,
            (cutoff, entity_id) + _profile_params(conn),
        ).fetchall()
    else:
        rows = conn.execute(
            f"""
            SELECT t.portfolio_asset_id,
                   pa.market_code,
                   ma.currency_code,
                   COALESCE(SUM(CASE WHEN t.type = 'INVESTMENT_BUY' THEN t.quantity ELSE 0 END), 0)
                   - COALESCE(SUM(CASE WHEN t.type = 'INVESTMENT_SELL' THEN t.quantity ELSE 0 END), 0) AS net_quantity
            FROM transactions t
            JOIN portfolio_assets pa ON pa.id = t.portfolio_asset_id
            JOIN market_assets ma ON ma.market_code = pa.market_code
            WHERE t.type IN ('INVESTMENT_BUY', 'INVESTMENT_SELL')
              AND t.timestamp <= ?
              {active_filter}
              {profile_clause}
            GROUP BY t.portfolio_asset_id
            HAVING net_quantity > 0
        """,
            (cutoff,) + _profile_params(conn),
        ).fetchall()
    return [dict(r) for r in rows]


def get_cumulative_invested_as_of(
    conn: sqlite3.Connection, cutoff: str, entity_id: int | None = None
) -> dict[str, float]:
    """Net cash invested in active portfolio assets as of a cutoff timestamp,
    broken down by currency. Returns {currency: net_amount}."""
    if entity_id is not None:
        rows = conn.execute(
            """
            SELECT t.currency,
                   COALESCE(SUM(
                       CASE
                           WHEN t.type = 'INVESTMENT_BUY' THEN t.total_value
                           WHEN t.type = 'INVESTMENT_SELL' THEN -t.total_value
                           ELSE 0
                       END
                   ), 0) AS net
            FROM transactions t
            JOIN portfolio_assets pa ON pa.id = t.portfolio_asset_id
            WHERE pa.is_active = 1
              AND t.type IN ('INVESTMENT_BUY', 'INVESTMENT_SELL')
              AND t.timestamp <= ?
              AND t.entity_id = ?"""
            + _profile_clause(conn, "t.profile_id")
            + " GROUP BY t.currency",
            (cutoff, entity_id) + _profile_params(conn),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT t.currency,
                   COALESCE(SUM(
                       CASE
                           WHEN t.type = 'INVESTMENT_BUY' THEN t.total_value
                           WHEN t.type = 'INVESTMENT_SELL' THEN -t.total_value
                           ELSE 0
                       END
                   ), 0) AS net
            FROM transactions t
            JOIN portfolio_assets pa ON pa.id = t.portfolio_asset_id
            WHERE pa.is_active = 1
              AND t.type IN ('INVESTMENT_BUY', 'INVESTMENT_SELL')
              AND t.timestamp <= ?"""
            + _profile_clause(conn, "t.profile_id")
            + " GROUP BY t.currency",
            (cutoff,) + _profile_params(conn),
        ).fetchall()
    return {r["currency"]: float(r["net"]) for r in rows}


def get_all_prices(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("""
        SELECT market_code, timestamp, price
        FROM prices
        ORDER BY market_code, timestamp
    """).fetchall()
    return [dict(r) for r in rows]


def get_latest_transaction_prices(conn: sqlite3.Connection) -> list[dict]:
    """Get the latest unit_price from INVESTMENT_BUY transactions per market_code.

    Used as a fallback when no market price exists in the prices table,
    ensuring assets contribute value from the moment they are purchased.
    """
    rows = conn.execute(
        """
        SELECT pa.market_code,
               t.unit_price,
               t.timestamp,
               ma.currency_code
        FROM transactions t
        JOIN portfolio_assets pa ON pa.id = t.portfolio_asset_id
        JOIN market_assets ma ON ma.market_code = pa.market_code
        WHERE t.type = 'INVESTMENT_BUY'
          AND t.unit_price IS NOT NULL
          AND pa.is_active = 1"""
        + _profile_clause(conn, "t.profile_id")
        + " ORDER BY pa.market_code, t.timestamp DESC",
        _profile_params(conn),
    ).fetchall()
    seen = set()
    result = []
    for r in rows:
        mc = r["market_code"]
        if mc not in seen:
            seen.add(mc)
            result.append(dict(r))
    return result


def get_cash_by_currency_as_of(conn: sqlite3.Connection, cutoff: str) -> dict[str, float]:
    rows = conn.execute(
        """
        SELECT t.entity_id, t.currency,
            COALESCE(SUM(
                CASE
                    WHEN t.type IN ('INCOME', 'INVESTMENT_SELL', 'TRANSFER_IN') THEN t.total_value
                    WHEN t.type IN ('MONEY_OUT', 'INVESTMENT_BUY', 'TRANSFER_OUT') THEN -t.total_value
                    WHEN t.type = 'BALANCE_ADJUSTMENT' THEN t.total_value
                    ELSE 0
                END
            ), 0) AS cash_balance
        FROM transactions t
        WHERE t.timestamp <= ?"""
        + _profile_clause(conn, "t.profile_id")
        + " GROUP BY t.entity_id, t.currency",
        (cutoff,) + _profile_params(conn),
    ).fetchall()
    fee_rows = [{"entity_id": r["entity_id"], "currency": r["currency"], "balance": r["cash_balance"]} for r in rows]
    _apply_fee_corrections(conn, fee_rows, cutoff)
    result: dict[str, float] = defaultdict(float)
    for r in fee_rows:
        result[r["currency"]] += r["balance"]
    return dict(result)


def get_total_cash_by_currency_as_of(conn: sqlite3.Connection, timestamp: str) -> dict[str, float]:
    from db.queries import get_balance_at_date

    if "T" not in timestamp:
        timestamp = timestamp + "T23:59:59"

    pairs = conn.execute(
        "SELECT DISTINCT entity_id, currency FROM balance_snapshots WHERE 1=1" + _profile_clause(conn),
        _profile_params(conn),
    ).fetchall()

    result: dict[str, float] = defaultdict(float)
    for row in pairs:
        eid = row["entity_id"]
        cur = row["currency"]
        balance = get_balance_at_date(conn, eid, cur, timestamp)
        result[cur] += balance

    ts_filter = f"timestamp <= '{timestamp}'" if timestamp != "now" else "timestamp <= datetime('now')"
    pid_clause = _profile_clause(conn)
    rows = conn.execute(
        f"""
        SELECT entity_id, currency,
            COALESCE(SUM(
                CASE
                    WHEN type IN ('INCOME', 'INVESTMENT_SELL', 'TRANSFER_IN') THEN total_value
                    WHEN type IN ('MONEY_OUT', 'INVESTMENT_BUY', 'TRANSFER_OUT') THEN -total_value
                    WHEN type = 'BALANCE_ADJUSTMENT' THEN total_value
                    ELSE 0
                END
            ), 0) AS cash_balance
        FROM transactions
        WHERE {ts_filter}{pid_clause}
          AND (entity_id, currency) NOT IN (SELECT DISTINCT entity_id, currency FROM balance_snapshots WHERE 1=1{pid_clause})
        GROUP BY entity_id, currency
    """,
        _profile_params(conn) * 2,
    ).fetchall()
    fee_rows = [{"entity_id": r["entity_id"], "currency": r["currency"], "balance": r["cash_balance"]} for r in rows]
    _apply_fee_corrections(conn, fee_rows, timestamp)
    for r in fee_rows:
        result[r["currency"]] += r["balance"]

    return dict(result)


def get_entity_cash_by_currency_as_of(conn: sqlite3.Connection, entity_id: int, cutoff: str) -> dict[str, float]:
    rows = conn.execute(
        """
        SELECT t.currency,
            COALESCE(SUM(
                CASE
                    WHEN t.type IN ('INCOME', 'INVESTMENT_SELL', 'TRANSFER_IN') THEN t.total_value
                    WHEN t.type IN ('MONEY_OUT', 'INVESTMENT_BUY', 'TRANSFER_OUT') THEN -t.total_value
                    WHEN t.type = 'BALANCE_ADJUSTMENT' THEN t.total_value
                    ELSE 0
                END
            ), 0) AS cash_balance
        FROM transactions t
        WHERE t.timestamp <= ? AND t.entity_id = ?"""
        + _profile_clause(conn, "t.profile_id")
        + " GROUP BY t.currency",
        (cutoff, entity_id) + _profile_params(conn),
    ).fetchall()
    result = {r["currency"]: r["cash_balance"] for r in rows}
    fee_rows = [{"entity_id": entity_id, "currency": cur, "balance": bal} for cur, bal in result.items()]
    _apply_fee_corrections(conn, fee_rows, cutoff)
    return {r["currency"]: r["balance"] for r in fee_rows}


def get_entity_total_cash_by_currency_as_of(
    conn: sqlite3.Connection, entity_id: int, timestamp: str
) -> dict[str, float]:
    from db.queries import get_balance_at_date

    if "T" not in timestamp:
        timestamp = timestamp + "T23:59:59"

    pairs = conn.execute(
        "SELECT DISTINCT currency FROM balance_snapshots WHERE entity_id = ?" + _profile_clause(conn),
        (entity_id,) + _profile_params(conn),
    ).fetchall()

    result: dict[str, float] = defaultdict(float)
    for row in pairs:
        cur = row["currency"]
        balance = get_balance_at_date(conn, entity_id, cur, timestamp)
        result[cur] += balance

    ts_filter = f"timestamp <= '{timestamp}'" if timestamp != "now" else "timestamp <= datetime('now')"
    pid_clause = _profile_clause(conn)
    rows = conn.execute(
        f"""
        SELECT currency,
            COALESCE(SUM(
                CASE
                    WHEN type IN ('INCOME', 'INVESTMENT_SELL', 'TRANSFER_IN') THEN total_value
                    WHEN type IN ('MONEY_OUT', 'INVESTMENT_BUY', 'TRANSFER_OUT') THEN -total_value
                    WHEN type = 'BALANCE_ADJUSTMENT' THEN total_value
                    ELSE 0
                END
            ), 0) AS cash_balance
        FROM transactions
        WHERE {ts_filter}{pid_clause}
          AND entity_id = ?
          AND currency NOT IN (SELECT DISTINCT currency FROM balance_snapshots WHERE entity_id = ?{pid_clause})
        GROUP BY currency
    """,
        _profile_params(conn) + (entity_id, entity_id) + _profile_params(conn),
    ).fetchall()
    fee_rows = [{"entity_id": entity_id, "currency": r["currency"], "balance": r["cash_balance"]} for r in rows]
    _apply_fee_corrections(conn, fee_rows, timestamp)
    for r in fee_rows:
        result[r["currency"]] += r["balance"]

    return dict(result)


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

    market_currencies = dict(conn.execute("SELECT market_code, currency_code FROM market_assets").fetchall())

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


def detect_stock_splits(conn: sqlite3.Connection) -> list[dict]:
    """Detect stock splits by comparing buy unit_prices with market prices on the buy date.

    Returns a list of dicts with keys: portfolio_asset_id, market_code, buy_timestamp, ratio.
    A split is inferred when buy_price / market_price >= 2 and rounds to a clean integer.
    """
    rows = conn.execute(
        """
        SELECT t.id AS tx_id, t.portfolio_asset_id, t.timestamp, t.unit_price,
               t.quantity, t.total_value, pa.market_code
        FROM transactions t
        JOIN portfolio_assets pa ON pa.id = t.portfolio_asset_id
        WHERE t.type = 'INVESTMENT_BUY'
          AND t.unit_price IS NOT NULL
          AND t.quantity IS NOT NULL"""
        + _profile_clause(conn, "t.profile_id")
        + " ORDER BY t.portfolio_asset_id, t.timestamp ASC",
        _profile_params(conn),
    ).fetchall()

    all_prices = get_all_prices(conn)
    price_index: dict[str, list[tuple[str, float]]] = {}
    for p in all_prices:
        price_index.setdefault(p["market_code"], []).append((p["timestamp"][:10], p["price"]))
    for mc in price_index:
        price_index[mc].sort(key=lambda x: x[0])

    splits: list[dict] = []
    for r in rows:
        mc = r["market_code"]
        buy_price = r["unit_price"]
        buy_date = r["timestamp"][:10]

        prices = price_index.get(mc, [])
        if not prices:
            continue

        # Find market price closest to buy date
        from bisect import bisect_right

        dates = [p[0] for p in prices]
        idx = bisect_right(dates, buy_date) - 1
        if idx < 0 or dates[idx] != buy_date:
            continue
        market_price = prices[idx][1]
        if market_price <= 0 or buy_price <= 0:
            continue

        ratio = buy_price / market_price
        if ratio < 2.0:
            continue

        nearest = int(ratio + 0.5)
        if nearest < 2:
            continue

        # Must be close to an integer (15% tolerance)
        if abs(ratio - nearest) / nearest > 0.15:
            continue

        splits.append(
            {
                "portfolio_asset_id": r["portfolio_asset_id"],
                "market_code": mc,
                "buy_timestamp": buy_date,
                "ratio": nearest,
                "quantity": r["quantity"],
            }
        )

    return splits
