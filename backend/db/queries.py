import sqlite3
from datetime import datetime
from typing import Any

from models.enums import EntityType


def _lastrowid(cursor: sqlite3.Cursor) -> int:
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def _pid(conn: sqlite3.Connection) -> int | None:
    """Active profile id for the connection, or None when unscoped (e.g. tests)."""
    return getattr(conn, "profile_id", None)


def _profile_clause(conn: sqlite3.Connection, column: str = "profile_id") -> str:
    """SQL fragment appended to a WHERE clause to scope a row to the profile."""
    return f" AND {column} = ?" if _pid(conn) is not None else ""


def _profile_params(conn: sqlite3.Connection) -> tuple:
    return (_pid(conn),) if _pid(conn) is not None else ()


# ---------------------------------------------------------------------------
# Entity queries
# ---------------------------------------------------------------------------


def create_entity(
    conn: sqlite3.Connection,
    name: str,
    entity_type: EntityType,
    main_currency: str | None = None,
    country: str | None = None,
    description: str | None = None,
) -> int:
    cursor = conn.execute(
        "INSERT INTO entities (name, entity_type, main_currency, country, description, profile_id) VALUES (?, ?, ?, ?, ?, ?)",
        (name, entity_type.value, main_currency, country, description, _pid(conn)),
    )
    return _lastrowid(cursor)


def get_entity(conn: sqlite3.Connection, entity_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id, name, entity_type, main_currency, country, description FROM entities WHERE id = ? AND deleted_at IS NULL"
        + _profile_clause(conn),
        (entity_id,) + _profile_params(conn),
    ).fetchone()
    return dict(row) if row else None


def get_all_entities(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, name, entity_type, main_currency, country, description FROM entities WHERE deleted_at IS NULL"
        + _profile_clause(conn)
        + " ORDER BY id",
        _profile_params(conn),
    ).fetchall()
    return [dict(r) for r in rows]


def update_entity(
    conn: sqlite3.Connection,
    entity_id: int,
    name: str,
    entity_type: EntityType,
    main_currency: str | None = None,
    country: str | None = None,
    description: str | None = None,
) -> bool:
    cursor = conn.execute(
        "UPDATE entities SET name = ?, entity_type = ?, main_currency = ?, country = ?, description = ? WHERE id = ?"
        + _profile_clause(conn),
        (name, entity_type.value, main_currency, country, description, entity_id) + _profile_params(conn),
    )
    return cursor.rowcount > 0


def delete_entity(conn: sqlite3.Connection, entity_id: int) -> bool:
    cursor = conn.execute(
        "UPDATE entities SET deleted_at = datetime('now') WHERE id = ?" + _profile_clause(conn),
        (entity_id,) + _profile_params(conn),
    )
    return cursor.rowcount > 0


def entity_exists(conn: sqlite3.Connection, name: str, entity_type: EntityType) -> bool:
    row = conn.execute(
        "SELECT 1 FROM entities WHERE name = ? AND entity_type = ? AND deleted_at IS NULL"
        + _profile_clause(conn)
        + " LIMIT 1",
        (name, entity_type.value) + _profile_params(conn),
    ).fetchone()
    return row is not None


def entity_has_assets(conn: sqlite3.Connection, entity_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM transactions WHERE entity_id = ?" + _profile_clause(conn) + " LIMIT 1",
        (entity_id,) + _profile_params(conn),
    ).fetchone()
    return row is not None


def entity_has_dependents(conn: sqlite3.Connection, entity_id: int) -> bool:
    pid_clause = _profile_clause(conn)
    params = (entity_id,) + _profile_params(conn) + (entity_id,) + _profile_params(conn)
    row = conn.execute(
        f"""SELECT 1 FROM (
            SELECT 1 FROM transactions WHERE entity_id = ?{pid_clause}
            UNION ALL
            SELECT 1 FROM balance_snapshots WHERE entity_id = ?{pid_clause}
        ) LIMIT 1""",
        params,
    ).fetchone()
    return row is not None


def get_entity_dependents(conn: sqlite3.Connection, entity_id: int) -> dict:
    pid_clause = _profile_clause(conn)
    pid_params = _profile_params(conn)

    has_transactions = (
        conn.execute(
            "SELECT 1 FROM transactions WHERE entity_id = ?" + pid_clause + " LIMIT 1",
            (entity_id,) + pid_params,
        ).fetchone()
        is not None
    )

    has_balance_snapshots = (
        conn.execute(
            "SELECT 1 FROM balance_snapshots WHERE entity_id = ?" + pid_clause + " LIMIT 1",
            (entity_id,) + pid_params,
        ).fetchone()
        is not None
    )

    has_schedules = (
        conn.execute(
            "SELECT 1 FROM schedules WHERE entity_id = ?" + pid_clause + " LIMIT 1",
            (entity_id,) + pid_params,
        ).fetchone()
        is not None
    )

    return {
        "has_transactions": has_transactions,
        "has_balance_snapshots": has_balance_snapshots,
        "has_schedules": has_schedules,
    }


# ---------------------------------------------------------------------------
# Fiscal exemption queries
# ---------------------------------------------------------------------------


def create_fiscal_exemption(
    conn: sqlite3.Connection,
    exemption_type: str,
    description: str | None = None,
    exemption_amount: float = 0,
    exemption_rate: float = 100,
    exemption_rate_limit: float | None = None,
) -> int:
    cursor = conn.execute(
        """INSERT INTO fiscal_exemptions
           (exemption_type, description, exemption_amount, exemption_rate, exemption_rate_limit, profile_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (exemption_type, description, exemption_amount, exemption_rate, exemption_rate_limit, _pid(conn)),
    )
    return _lastrowid(cursor)


def get_fiscal_exemption(conn: sqlite3.Connection, exemption_id: int) -> dict | None:
    row = conn.execute(
        """SELECT id, exemption_type, description, exemption_amount, exemption_rate, exemption_rate_limit
           FROM fiscal_exemptions WHERE id = ?"""
        + _profile_clause(conn),
        (exemption_id,) + _profile_params(conn),
    ).fetchone()
    return dict(row) if row else None


def get_all_fiscal_exemptions(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, exemption_type, description, exemption_amount, exemption_rate, exemption_rate_limit FROM fiscal_exemptions WHERE 1=1"
        + _profile_clause(conn)
        + " ORDER BY id",
        _profile_params(conn),
    ).fetchall()
    return [dict(r) for r in rows]


def update_fiscal_exemption(
    conn: sqlite3.Connection,
    exemption_id: int,
    exemption_type: str,
    description: str | None = None,
    exemption_amount: float = 0,
    exemption_rate: float = 100,
    exemption_rate_limit: float | None = None,
) -> bool:
    cursor = conn.execute(
        """UPDATE fiscal_exemptions
           SET exemption_type = ?, description = ?, exemption_amount = ?, exemption_rate = ?, exemption_rate_limit = ?
           WHERE id = ?"""
        + _profile_clause(conn),
        (exemption_type, description, exemption_amount, exemption_rate, exemption_rate_limit, exemption_id)
        + _profile_params(conn),
    )
    return cursor.rowcount > 0


def delete_fiscal_exemption(conn: sqlite3.Connection, exemption_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM fiscal_exemptions WHERE id = ?" + _profile_clause(conn),
        (exemption_id,) + _profile_params(conn),
    )
    return cursor.rowcount > 0


def fiscal_exemption_has_dependents(conn: sqlite3.Connection, exemption_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM transactions WHERE fiscal_exemption_id = ?" + _profile_clause(conn) + " LIMIT 1",
        (exemption_id,) + _profile_params(conn),
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Fiscal period queries
# ---------------------------------------------------------------------------


def create_fiscal_period(
    conn: sqlite3.Connection,
    rule_key: str,
    start_date: str,
    end_date: str | None = None,
) -> int:
    cursor = conn.execute(
        """INSERT INTO fiscal_periods (rule_key, start_date, end_date, profile_id)
           VALUES (?, ?, ?, ?)""",
        (rule_key, start_date, end_date, _pid(conn)),
    )
    return _lastrowid(cursor)


def get_fiscal_period(conn: sqlite3.Connection, period_id: int) -> dict | None:
    row = conn.execute(
        """SELECT id, rule_key, start_date, end_date
           FROM fiscal_periods WHERE id = ?"""
        + _profile_clause(conn),
        (period_id,) + _profile_params(conn),
    ).fetchone()
    return dict(row) if row else None


def get_all_fiscal_periods(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, rule_key, start_date, end_date FROM fiscal_periods WHERE 1=1"
        + _profile_clause(conn)
        + " ORDER BY start_date",
        _profile_params(conn),
    ).fetchall()
    return [dict(r) for r in rows]


def update_fiscal_period(
    conn: sqlite3.Connection,
    period_id: int,
    rule_key: str,
    start_date: str,
    end_date: str | None = None,
) -> bool:
    cursor = conn.execute(
        """UPDATE fiscal_periods
           SET rule_key = ?, start_date = ?, end_date = ?
           WHERE id = ?"""
        + _profile_clause(conn),
        (rule_key, start_date, end_date, period_id) + _profile_params(conn),
    )
    return cursor.rowcount > 0


def delete_fiscal_period(conn: sqlite3.Connection, period_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM fiscal_periods WHERE id = ?" + _profile_clause(conn),
        (period_id,) + _profile_params(conn),
    )
    return cursor.rowcount > 0


def get_fiscal_period_at(conn: sqlite3.Connection, sell_date: str) -> dict | None:
    """Return the fiscal period containing ``sell_date`` (or None).

    A period with ``end_date IS NULL`` is open-ended and contains any date at or
    after its ``start_date``.
    """
    row = conn.execute(
        """SELECT id, rule_key, start_date, end_date
           FROM fiscal_periods
           WHERE start_date <= date(?) AND (end_date IS NULL OR date(?) <= end_date)
        """
        + _profile_clause(conn)
        + " ORDER BY start_date DESC LIMIT 1",
        (sell_date, sell_date) + _profile_params(conn),
    ).fetchone()
    return dict(row) if row else None


def resolve_fiscal_rule(conn: sqlite3.Connection, sell_date: str) -> str | None:
    """Resolve the fiscal rule active on ``sell_date`` (period rule or None)."""
    period = get_fiscal_period_at(conn, sell_date)
    return period["rule_key"] if period else None


# ---------------------------------------------------------------------------
# Tax rate queries (§17.8)
# ---------------------------------------------------------------------------


def create_tax_rate(
    conn: sqlite3.Connection,
    ruleset_key: str,
    category: str,
    from_amount: float,
    rate: float,
    to_amount: float | None = None,
    year_start: int | None = None,
) -> int:
    cursor = conn.execute(
        """INSERT INTO tax_rates (ruleset_key, category, from_amount, to_amount, rate, year_start, profile_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (ruleset_key, category, from_amount, to_amount, rate, year_start, _pid(conn)),
    )
    return _lastrowid(cursor)


def get_tax_rate(conn: sqlite3.Connection, rate_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM tax_rates WHERE id = ?" + _profile_clause(conn),
        (rate_id,) + _profile_params(conn),
    ).fetchone()
    return dict(row) if row else None


def get_all_tax_rates(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM tax_rates WHERE 1=1" + _profile_clause(conn) + " ORDER BY ruleset_key, category, from_amount",
        _profile_params(conn),
    ).fetchall()
    return [dict(r) for r in rows]


def get_tax_rates_for_ruleset(
    conn: sqlite3.Connection,
    ruleset_key: str,
    category: str | None = None,
    year_start: int | None = None,
) -> list[dict]:
    conditions = ["ruleset_key = ?"]
    params: list = [ruleset_key]
    if category:
        conditions.append("category = ?")
        params.append(category)
    if year_start is not None:
        conditions.append("(year_start = ? OR year_start IS NULL)")
        params.append(year_start)
    where = " AND ".join(conditions)
    rows = conn.execute(
        f"SELECT * FROM tax_rates WHERE {where}" + _profile_clause(conn) + " ORDER BY category, from_amount",
        params + list(_profile_params(conn)),
    ).fetchall()
    return [dict(r) for r in rows]


def update_tax_rate(
    conn: sqlite3.Connection,
    rate_id: int,
    ruleset_key: str,
    category: str,
    from_amount: float,
    rate: float,
    to_amount: float | None = None,
    year_start: int | None = None,
) -> bool:
    cursor = conn.execute(
        """UPDATE tax_rates
           SET ruleset_key = ?, category = ?, from_amount = ?, to_amount = ?, rate = ?, year_start = ?
           WHERE id = ?"""
        + _profile_clause(conn),
        (ruleset_key, category, from_amount, to_amount, rate, year_start, rate_id) + _profile_params(conn),
    )
    return cursor.rowcount > 0


def delete_tax_rate(conn: sqlite3.Connection, rate_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM tax_rates WHERE id = ?" + _profile_clause(conn),
        (rate_id,) + _profile_params(conn),
    )
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Market asset queries
# ---------------------------------------------------------------------------


def create_market_asset(
    conn: sqlite3.Connection,
    market_code: str,
    currency_code: str,
    asset_type: str,
    ticker: str | None = None,
    asset_class: str | None = None,
    name: str | None = None,
    description: str | None = None,
    exchange: str | None = None,
) -> None:
    conn.execute(
        """INSERT INTO market_assets
           (market_code, ticker, asset_type, asset_class, currency_code, name, description, exchange)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (market_code, ticker, asset_type, asset_class, currency_code, name, description, exchange),
    )


def get_market_asset(conn: sqlite3.Connection, market_code: str) -> dict | None:
    row = conn.execute(
        "SELECT market_code, ticker, asset_type, asset_class, currency_code, name, description, exchange FROM market_assets WHERE market_code = ?",
        (market_code,),
    ).fetchone()
    return dict(row) if row else None


def get_all_market_assets(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT market_code, ticker, asset_type, asset_class, currency_code, name, description, exchange FROM market_assets ORDER BY market_code"
    ).fetchall()
    return [dict(r) for r in rows]


def update_market_asset(
    conn: sqlite3.Connection,
    market_code: str,
    currency_code: str,
    asset_type: str,
    ticker: str | None = None,
    asset_class: str | None = None,
    name: str | None = None,
    description: str | None = None,
    exchange: str | None = None,
) -> bool:
    cursor = conn.execute(
        """UPDATE market_assets
           SET ticker = ?, asset_type = ?, asset_class = ?, currency_code = ?, name = ?, description = ?, exchange = ?
           WHERE market_code = ?""",
        (ticker, asset_type, asset_class, currency_code, name, description, exchange, market_code),
    )
    return cursor.rowcount > 0


def delete_market_asset(conn: sqlite3.Connection, market_code: str) -> bool:
    cursor = conn.execute("DELETE FROM market_assets WHERE market_code = ?", (market_code,))
    return cursor.rowcount > 0


def market_asset_has_dependents(conn: sqlite3.Connection, market_code: str) -> bool:
    pid_clause = _profile_clause(conn)
    params = (market_code,) + _profile_params(conn) + (market_code,)
    row = conn.execute(
        f"""SELECT 1 FROM (
            SELECT 1 FROM portfolio_assets WHERE market_code = ?{pid_clause}
            UNION ALL
            SELECT 1 FROM prices WHERE market_code = ?
        ) LIMIT 1""",
        params,
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Portfolio asset queries
# ---------------------------------------------------------------------------


def create_portfolio_asset(
    conn: sqlite3.Connection,
    market_code: str,
    distribution_type: str | None = None,
    dca_status: str | None = None,
    layer: str | None = None,
    tactic: bool = False,
    desired_weight: float | None = None,
    ter: float | None = None,
    tracking_mode: str = "auto",
    current_value_manual: float | None = None,
    is_active: bool = True,
    closing_date: str | None = None,
    notes: str | None = None,
) -> int:
    cursor = conn.execute(
        """INSERT INTO portfolio_assets
           (market_code, distribution_type, dca_status, layer, tactic, desired_weight, ter,
            tracking_mode, current_value_manual, is_active, closing_date, notes, profile_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            market_code,
            distribution_type,
            dca_status,
            layer,
            tactic,
            desired_weight,
            ter,
            tracking_mode,
            current_value_manual,
            is_active,
            closing_date,
            notes,
            _pid(conn),
        ),
    )
    return _lastrowid(cursor)


def get_portfolio_asset(conn: sqlite3.Connection, asset_id: int) -> dict | None:
    row = conn.execute(
        """SELECT id, market_code, distribution_type, dca_status, layer, tactic,
                  desired_weight, ter, tracking_mode, current_value_manual,
                   is_active, closing_date, notes
           FROM portfolio_assets WHERE id = ?"""
        + _profile_clause(conn),
        (asset_id,) + _profile_params(conn),
    ).fetchone()
    return dict(row) if row else None


def get_all_portfolio_assets(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """SELECT id, market_code, distribution_type, dca_status, layer, tactic,
                  desired_weight, ter, tracking_mode, current_value_manual,
                  is_active, closing_date, notes
           FROM portfolio_assets WHERE 1=1"""
        + _profile_clause(conn)
        + " ORDER BY id",
        _profile_params(conn),
    ).fetchall()
    return [dict(r) for r in rows]


def get_portfolio_assets_by_market(conn: sqlite3.Connection, market_code: str) -> list[dict]:
    rows = conn.execute(
        """SELECT id, market_code, distribution_type, dca_status, layer, tactic,
                  desired_weight, ter, tracking_mode, current_value_manual,
                  is_active, closing_date, notes
           FROM portfolio_assets WHERE market_code = ?"""
        + _profile_clause(conn)
        + " ORDER BY id"
        "",
        (market_code,) + _profile_params(conn),
    ).fetchall()
    return [dict(r) for r in rows]


def update_portfolio_asset(
    conn: sqlite3.Connection,
    asset_id: int,
    market_code: str,
    distribution_type: str | None = None,
    dca_status: str | None = None,
    layer: str | None = None,
    tactic: bool = False,
    desired_weight: float | None = None,
    ter: float | None = None,
    tracking_mode: str = "auto",
    current_value_manual: float | None = None,
    is_active: bool = True,
    closing_date: str | None = None,
    notes: str | None = None,
) -> bool:
    cursor = conn.execute(
        """UPDATE portfolio_assets
           SET market_code = ?, distribution_type = ?, dca_status = ?, layer = ?, tactic = ?,
               desired_weight = ?, ter = ?, tracking_mode = ?, current_value_manual = ?,
               is_active = ?, closing_date = ?, notes = ?
           WHERE id = ?"""
        + _profile_clause(conn),
        (
            market_code,
            distribution_type,
            dca_status,
            layer,
            tactic,
            desired_weight,
            ter,
            tracking_mode,
            current_value_manual,
            is_active,
            closing_date,
            notes,
            asset_id,
        )
        + _profile_params(conn),
    )
    return cursor.rowcount > 0


def delete_portfolio_asset(conn: sqlite3.Connection, asset_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM portfolio_assets WHERE id = ?" + _profile_clause(conn),
        (asset_id,) + _profile_params(conn),
    )
    return cursor.rowcount > 0


def portfolio_asset_has_dependents(conn: sqlite3.Connection, asset_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM transactions WHERE portfolio_asset_id = ?" + _profile_clause(conn) + " LIMIT 1",
        (asset_id,) + _profile_params(conn),
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Currency queries
# ---------------------------------------------------------------------------


def get_distinct_codes(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT code FROM (SELECT code FROM currencies UNION SELECT base_code AS code FROM currencies) ORDER BY code"
    ).fetchall()
    return [row["code"] for row in rows]


def code_exists(conn: sqlite3.Connection, code: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM currencies WHERE code = ? OR base_code = ? LIMIT 1",
        (code, code),
    ).fetchone()
    return row is not None


def create_self_rate(conn: sqlite3.Connection, code: str, timestamp: datetime) -> None:
    conn.execute(
        "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES (?, ?, 1.0, ?)",
        (code, code, timestamp.isoformat()),
    )


def get_distinct_pairs(conn: sqlite3.Connection, code: str | None = None) -> list[tuple[str, str]]:
    if code:
        rows = conn.execute(
            """SELECT DISTINCT code, base_code FROM currencies
               WHERE code = ? OR base_code = ?
               ORDER BY code, base_code""",
            (code, code),
        ).fetchall()
    else:
        rows = conn.execute("SELECT DISTINCT code, base_code FROM currencies ORDER BY code, base_code").fetchall()
    return [(row["code"], row["base_code"]) for row in rows]


def pair_exists(conn: sqlite3.Connection, code: str, base_code: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM currencies WHERE code = ? AND base_code = ? LIMIT 1",
        (code, base_code),
    ).fetchone()
    return row is not None


def insert_rate(
    conn: sqlite3.Connection,
    code: str,
    base_code: str,
    rate: float,
    timestamp: datetime,
) -> None:
    conn.execute(
        "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES (?, ?, ?, ?)",
        (code, base_code, rate, timestamp.isoformat()),
    )


def upsert_rate(
    conn: sqlite3.Connection,
    code: str,
    base_code: str,
    rate: float,
    timestamp: datetime,
) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO currencies (code, base_code, rate, timestamp) VALUES (?, ?, ?, ?)",
        (code, base_code, rate, timestamp.isoformat()),
    )


def get_latest_rate(conn: sqlite3.Connection, code: str, base_code: str) -> dict | None:
    row = conn.execute(
        """SELECT code, base_code, rate, timestamp
           FROM currencies
           WHERE code = ? AND base_code = ?
           ORDER BY timestamp DESC
           LIMIT 1""",
        (code, base_code),
    ).fetchone()
    return dict(row) if row else None


def get_rate_at(conn: sqlite3.Connection, code: str, base_code: str, at: datetime) -> dict | None:
    """Latest stored rate on or before ``at`` (previous-close convention).

    Non-trading days (weekends, holidays) intentionally have no rows; lookups
    resolve to the most recent earlier rate and never look forward.
    """
    row = conn.execute(
        """SELECT code, base_code, rate, timestamp
           FROM currencies
           WHERE code = ? AND base_code = ? AND julianday(timestamp) <= julianday(?)
           ORDER BY julianday(timestamp) DESC
           LIMIT 1""",
        (code, base_code, at.isoformat()),
    ).fetchone()
    return dict(row) if row else None


def get_rate_history(conn: sqlite3.Connection, code: str, base_code: str) -> list[dict]:
    rows = conn.execute(
        """SELECT code, base_code, rate, timestamp
           FROM currencies
           WHERE code = ? AND base_code = ?
           ORDER BY timestamp""",
        (code, base_code),
    ).fetchall()
    return [dict(r) for r in rows]


def update_rate(
    conn: sqlite3.Connection,
    code: str,
    base_code: str,
    timestamp: datetime,
    rate: float,
) -> bool:
    cursor = conn.execute(
        "UPDATE currencies SET rate = ? WHERE code = ? AND base_code = ? AND timestamp = ?",
        (rate, code, base_code, timestamp.isoformat()),
    )
    return cursor.rowcount > 0


def delete_pair(conn: sqlite3.Connection, code: str, base_code: str) -> bool:
    cursor = conn.execute(
        "DELETE FROM currencies WHERE code = ? AND base_code = ?",
        (code, base_code),
    )
    return cursor.rowcount > 0


def delete_code(conn: sqlite3.Connection, code: str) -> None:
    conn.execute(
        "DELETE FROM currencies WHERE code = ? OR base_code = ?",
        (code, code),
    )


def currency_code_has_dependents(conn: sqlite3.Connection, code: str) -> bool:
    pid_clause = _profile_clause(conn)
    pid_params = _profile_params(conn)
    row = conn.execute(
        f"""SELECT 1 FROM (
            SELECT 1 FROM market_assets WHERE currency_code = ?
            UNION ALL
            SELECT 1 FROM transactions WHERE (currency = ? OR payment_currency = ? OR dividend_currency = ? OR dividend_payment_currency = ?){pid_clause}
            UNION ALL
            SELECT 1 FROM transaction_fees WHERE currency = ?{pid_clause}
            UNION ALL
            SELECT 1 FROM transaction_taxes WHERE currency = ?{pid_clause}
            UNION ALL
            SELECT 1 FROM balance_snapshots WHERE currency = ?{pid_clause}
        ) LIMIT 1""",
        (code, code, code, code, code)
        + pid_params
        + (code,)
        + pid_params
        + (code,)
        + pid_params
        + (code,)
        + pid_params,
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Transaction queries
# ---------------------------------------------------------------------------


def get_earliest_transaction_timestamp(conn: sqlite3.Connection) -> str | None:
    """Earliest transaction timestamp across all profiles (ISO string or None)."""
    row = conn.execute("SELECT MIN(timestamp) FROM transactions").fetchone()
    return row[0] if row else None


def create_transaction(
    conn: sqlite3.Connection,
    timestamp: str,
    type_: str,
    entity_id: int,
    currency: str,
    total_value: float | None = None,
    investment_transaction_category: str | None = None,
    income_category: str | None = None,
    portfolio_asset_id: int | None = None,
    quantity: float | None = None,
    unit_price: float | None = None,
    gross_amount: float | None = None,
    net_amount: float | None = None,
    payment_currency: str | None = None,
    fx_rate: float | None = None,
    settlement_date: str | None = None,
    fiscal_exemption_id: int | None = None,
    dividend_type: str | None = None,
    record_date: str | None = None,
    payment_date: str | None = None,
    dividend_currency: str | None = None,
    dividend_payment_currency: str | None = None,
    dividend_fx_rate: float | None = None,
    notes: str | None = None,
    cash_handling: str | None = None,
) -> int:
    fiscal_rule = resolve_fiscal_rule(conn, timestamp) if type_ == "INVESTMENT_SELL" else None
    cursor = conn.execute(
        """INSERT INTO transactions
           (timestamp, type, investment_transaction_category, income_category, entity_id, portfolio_asset_id,
            quantity, unit_price, currency, total_value,
            gross_amount, net_amount, payment_currency, fx_rate, settlement_date,
            fiscal_exemption_id, fiscal_rule, dividend_type, record_date, payment_date,
            dividend_currency, dividend_payment_currency, dividend_fx_rate, notes,
            cash_handling, profile_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            timestamp,
            type_,
            investment_transaction_category,
            income_category,
            entity_id,
            portfolio_asset_id,
            quantity,
            unit_price,
            currency,
            total_value,
            gross_amount,
            net_amount,
            payment_currency,
            fx_rate,
            settlement_date,
            fiscal_exemption_id,
            fiscal_rule,
            dividend_type,
            record_date,
            payment_date,
            dividend_currency,
            dividend_payment_currency,
            dividend_fx_rate,
            notes,
            cash_handling,
            _pid(conn),
        ),
    )
    return _lastrowid(cursor)


def get_transaction(conn: sqlite3.Connection, tx_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM transactions WHERE id = ?" + _profile_clause(conn),
        (tx_id,) + _profile_params(conn),
    ).fetchone()
    return dict(row) if row else None


def get_all_transactions(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
    type_filter: str | None = None,
    entity_id: int | None = None,
    currency: str | None = None,
) -> list[dict]:
    conditions: list[str] = []
    params: list[Any] = []

    if start_date:
        conditions.append("timestamp >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("timestamp <= ?")
        params.append(end_date + "T23:59:59")
    if type_filter:
        conditions.append("type = ?")
        params.append(type_filter)
    if entity_id is not None:
        conditions.append("entity_id = ?")
        params.append(entity_id)
    if currency:
        conditions.append("currency = ?")
        params.append(currency)

    pid = _pid(conn)
    if pid is not None:
        conditions.append("profile_id = ?")
        params.append(pid)

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

    rows = conn.execute(
        f"SELECT * FROM transactions{where_clause} ORDER BY timestamp DESC",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_transactions_by_portfolio(conn: sqlite3.Connection, portfolio_asset_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM transactions WHERE portfolio_asset_id = ?" + _profile_clause(conn) + " ORDER BY timestamp DESC",
        (portfolio_asset_id,) + _profile_params(conn),
    ).fetchall()
    return [dict(r) for r in rows]


def get_transactions_by_entity(conn: sqlite3.Connection, entity_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM transactions WHERE entity_id = ?" + _profile_clause(conn) + " ORDER BY timestamp DESC",
        (entity_id,) + _profile_params(conn),
    ).fetchall()
    return [dict(r) for r in rows]


def update_transaction(
    conn: sqlite3.Connection,
    tx_id: int,
    timestamp: str,
    type_: str,
    entity_id: int,
    currency: str,
    total_value: float | None = None,
    investment_transaction_category: str | None = None,
    income_category: str | None = None,
    portfolio_asset_id: int | None = None,
    quantity: float | None = None,
    unit_price: float | None = None,
    gross_amount: float | None = None,
    net_amount: float | None = None,
    payment_currency: str | None = None,
    fx_rate: float | None = None,
    settlement_date: str | None = None,
    fiscal_exemption_id: int | None = None,
    dividend_type: str | None = None,
    record_date: str | None = None,
    payment_date: str | None = None,
    dividend_currency: str | None = None,
    dividend_payment_currency: str | None = None,
    dividend_fx_rate: float | None = None,
    notes: str | None = None,
    cash_handling: str | None = None,
) -> bool:
    fiscal_rule = resolve_fiscal_rule(conn, timestamp) if type_ == "INVESTMENT_SELL" else None
    cursor = conn.execute(
        """UPDATE transactions
           SET timestamp = ?, type = ?, investment_transaction_category = ?, income_category = ?, entity_id = ?,
               portfolio_asset_id = ?, quantity = ?, unit_price = ?, currency = ?,
               total_value = ?, gross_amount = ?, net_amount = ?, payment_currency = ?,
               fx_rate = ?, settlement_date = ?, fiscal_exemption_id = ?, fiscal_rule = ?, dividend_type = ?,
           record_date = ?, payment_date = ?, dividend_currency = ?,
           dividend_payment_currency = ?, dividend_fx_rate = ?, notes = ?, cash_handling = ?
           WHERE id = ?"""
        + _profile_clause(conn),
        (
            timestamp,
            type_,
            investment_transaction_category,
            income_category,
            entity_id,
            portfolio_asset_id,
            quantity,
            unit_price,
            currency,
            total_value,
            gross_amount,
            net_amount,
            payment_currency,
            fx_rate,
            settlement_date,
            fiscal_exemption_id,
            fiscal_rule,
            dividend_type,
            record_date,
            payment_date,
            dividend_currency,
            dividend_payment_currency,
            dividend_fx_rate,
            notes,
            cash_handling,
            tx_id,
        )
        + _profile_params(conn),
    )
    return cursor.rowcount > 0


def delete_transaction(conn: sqlite3.Connection, tx_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM transactions WHERE id = ?" + _profile_clause(conn),
        (tx_id,) + _profile_params(conn),
    )
    return cursor.rowcount > 0


def transaction_has_dependents(conn: sqlite3.Connection, tx_id: int) -> bool:
    pid_clause = _profile_clause(conn)
    pid_params = _profile_params(conn)
    row = conn.execute(
        f"""SELECT 1 FROM (
            SELECT 1 FROM transaction_fees WHERE transaction_id = ?{pid_clause}
            UNION ALL
            SELECT 1 FROM transaction_taxes WHERE transaction_id = ?{pid_clause}
            UNION ALL
            SELECT 1 FROM schedules WHERE linked_transaction_id = ?{pid_clause}
        ) LIMIT 1""",
        (tx_id,) + pid_params + (tx_id,) + pid_params + (tx_id,) + pid_params,
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Transaction fee queries
# ---------------------------------------------------------------------------


def create_fee(
    conn: sqlite3.Connection,
    transaction_id: int,
    fee_type: str,
    nature: str,
    currency: str,
    fixed_amount: float = 0.0,
    percentage: float = 0.0,
) -> int:
    cursor = conn.execute(
        "INSERT INTO transaction_fees (transaction_id, fee_type, nature, fixed_amount, percentage, currency, profile_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (transaction_id, fee_type, nature, fixed_amount, percentage, currency, _pid(conn)),
    )
    return _lastrowid(cursor)


def get_fee(conn: sqlite3.Connection, fee_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM transaction_fees WHERE id = ?" + _profile_clause(conn),
        (fee_id,) + _profile_params(conn),
    ).fetchone()
    return dict(row) if row else None


def get_fees_by_transaction(conn: sqlite3.Connection, transaction_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM transaction_fees WHERE transaction_id = ?" + _profile_clause(conn) + " ORDER BY id",
        (transaction_id,) + _profile_params(conn),
    ).fetchall()
    return [dict(r) for r in rows]


def delete_fees_by_transaction(conn: sqlite3.Connection, transaction_id: int) -> None:
    conn.execute(
        "DELETE FROM transaction_fees WHERE transaction_id = ?" + _profile_clause(conn),
        (transaction_id,) + _profile_params(conn),
    )


def get_all_fees(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM transaction_fees WHERE 1=1" + _profile_clause(conn) + " ORDER BY id", _profile_params(conn)
    ).fetchall()
    return [dict(r) for r in rows]


def update_fee(
    conn: sqlite3.Connection,
    fee_id: int,
    transaction_id: int,
    fee_type: str,
    nature: str,
    currency: str,
    fixed_amount: float = 0.0,
    percentage: float = 0.0,
) -> bool:
    cursor = conn.execute(
        "UPDATE transaction_fees SET transaction_id = ?, fee_type = ?, nature = ?, fixed_amount = ?, percentage = ?, currency = ? WHERE id = ?"
        + _profile_clause(conn),
        (transaction_id, fee_type, nature, fixed_amount, percentage, currency, fee_id) + _profile_params(conn),
    )
    return cursor.rowcount > 0


def delete_fee(conn: sqlite3.Connection, fee_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM transaction_fees WHERE id = ?" + _profile_clause(conn),
        (fee_id,) + _profile_params(conn),
    )
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Transaction tax queries
# ---------------------------------------------------------------------------


def create_tax(
    conn: sqlite3.Connection,
    transaction_id: int,
    tax_type: str,
    tax_amount: float,
    currency: str,
    tax_rate: float | None = None,
) -> int:
    cursor = conn.execute(
        "INSERT INTO transaction_taxes (transaction_id, tax_type, tax_rate, tax_amount, currency, profile_id) VALUES (?, ?, ?, ?, ?, ?)",
        (transaction_id, tax_type, tax_rate, tax_amount, currency, _pid(conn)),
    )
    return _lastrowid(cursor)


def get_tax(conn: sqlite3.Connection, tax_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM transaction_taxes WHERE id = ?" + _profile_clause(conn),
        (tax_id,) + _profile_params(conn),
    ).fetchone()
    return dict(row) if row else None


def get_taxes_by_transaction(conn: sqlite3.Connection, transaction_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM transaction_taxes WHERE transaction_id = ?" + _profile_clause(conn) + " ORDER BY id",
        (transaction_id,) + _profile_params(conn),
    ).fetchall()
    return [dict(r) for r in rows]


def delete_taxes_by_transaction(conn: sqlite3.Connection, transaction_id: int) -> None:
    conn.execute(
        "DELETE FROM transaction_taxes WHERE transaction_id = ?" + _profile_clause(conn),
        (transaction_id,) + _profile_params(conn),
    )


def get_all_taxes(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM transaction_taxes WHERE 1=1" + _profile_clause(conn) + " ORDER BY id", _profile_params(conn)
    ).fetchall()
    return [dict(r) for r in rows]


def update_tax(
    conn: sqlite3.Connection,
    tax_id: int,
    transaction_id: int,
    tax_type: str,
    tax_amount: float,
    currency: str,
    tax_rate: float | None = None,
) -> bool:
    cursor = conn.execute(
        "UPDATE transaction_taxes SET transaction_id = ?, tax_type = ?, tax_rate = ?, tax_amount = ?, currency = ? WHERE id = ?"
        + _profile_clause(conn),
        (transaction_id, tax_type, tax_rate, tax_amount, currency, tax_id) + _profile_params(conn),
    )
    return cursor.rowcount > 0


def delete_tax(conn: sqlite3.Connection, tax_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM transaction_taxes WHERE id = ?" + _profile_clause(conn),
        (tax_id,) + _profile_params(conn),
    )
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Price queries
# ---------------------------------------------------------------------------


def create_price(
    conn: sqlite3.Connection,
    market_code: str,
    timestamp: str,
    price: float,
    provider: str | None = None,
) -> int:
    cursor = conn.execute(
        "INSERT INTO prices (market_code, timestamp, price, provider) VALUES (?, ?, ?, ?)",
        (market_code, timestamp, price, provider),
    )
    return _lastrowid(cursor)


def get_price(conn: sqlite3.Connection, price_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM prices WHERE id = ?", (price_id,)).fetchone()
    return dict(row) if row else None


def get_prices_by_market(conn: sqlite3.Connection, market_code: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM prices WHERE market_code = ? ORDER BY timestamp DESC",
        (market_code,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_prices(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM prices ORDER BY market_code, timestamp DESC").fetchall()
    return [dict(r) for r in rows]


def update_price(
    conn: sqlite3.Connection,
    price_id: int,
    market_code: str,
    timestamp: str,
    price: float,
    provider: str | None = None,
) -> bool:
    cursor = conn.execute(
        "UPDATE prices SET market_code = ?, timestamp = ?, price = ?, provider = ? WHERE id = ?",
        (market_code, timestamp, price, provider, price_id),
    )
    return cursor.rowcount > 0


def delete_price(conn: sqlite3.Connection, price_id: int) -> bool:
    cursor = conn.execute("DELETE FROM prices WHERE id = ?", (price_id,))
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Balance snapshot queries
# ---------------------------------------------------------------------------


def create_balance_snapshot(
    conn: sqlite3.Connection,
    entity_id: int,
    currency: str,
    amount: float,
    timestamp: str,
    notes: str | None = None,
) -> int:
    cursor = conn.execute(
        "INSERT INTO balance_snapshots (entity_id, currency, amount, timestamp, notes, profile_id) VALUES (?, ?, ?, ?, ?, ?)",
        (entity_id, currency, amount, timestamp, notes, _pid(conn)),
    )
    return _lastrowid(cursor)


def get_balance_snapshot(conn: sqlite3.Connection, snapshot_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id, entity_id, currency, amount, timestamp, notes FROM balance_snapshots WHERE id = ?"
        + _profile_clause(conn),
        (snapshot_id,) + _profile_params(conn),
    ).fetchone()
    return dict(row) if row else None


def get_all_balance_snapshots(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, entity_id, currency, amount, timestamp, notes FROM balance_snapshots WHERE 1=1"
        + _profile_clause(conn)
        + " ORDER BY id",
        _profile_params(conn),
    ).fetchall()
    return [dict(r) for r in rows]


def get_latest_snapshot(conn: sqlite3.Connection, entity_id: int, currency: str) -> dict | None:
    row = conn.execute(
        "SELECT id, entity_id, currency, amount, timestamp, notes FROM balance_snapshots WHERE entity_id = ? AND currency = ?"
        + _profile_clause(conn)
        + " ORDER BY timestamp DESC LIMIT 1",
        (entity_id, currency) + _profile_params(conn),
    ).fetchone()
    return dict(row) if row else None


def update_balance_snapshot(
    conn: sqlite3.Connection,
    snapshot_id: int,
    entity_id: int,
    currency: str,
    amount: float,
    timestamp: str,
    notes: str | None = None,
) -> bool:
    cursor = conn.execute(
        "UPDATE balance_snapshots SET entity_id = ?, currency = ?, amount = ?, timestamp = ?, notes = ? WHERE id = ?"
        + _profile_clause(conn),
        (entity_id, currency, amount, timestamp, notes, snapshot_id) + _profile_params(conn),
    )
    return cursor.rowcount > 0


def delete_balance_snapshot(conn: sqlite3.Connection, snapshot_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM balance_snapshots WHERE id = ?" + _profile_clause(conn),
        (snapshot_id,) + _profile_params(conn),
    )
    return cursor.rowcount > 0


def has_transactions_on_or_after(conn: sqlite3.Connection, entity_id: int, currency: str, since: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM transactions WHERE entity_id = ? AND currency = ? AND timestamp >= ? AND type != 'BALANCE_ADJUSTMENT'"
        + _profile_clause(conn)
        + " LIMIT 1",
        (entity_id, currency, since) + _profile_params(conn),
    ).fetchone()
    return row is not None


def has_schedules_on_or_before(conn: sqlite3.Connection, entity_id: int, currency: str, until: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM schedules WHERE entity_id = ? AND currency = ? AND start_date <= ?"
        + _profile_clause(conn)
        + " LIMIT 1",
        (entity_id, currency, until) + _profile_params(conn),
    ).fetchone()
    return row is not None


def get_snapshot_at_timestamp(conn: sqlite3.Connection, entity_id: int, currency: str, timestamp: str) -> dict | None:
    row = conn.execute(
        "SELECT id, entity_id, currency, amount, timestamp, notes FROM balance_snapshots WHERE entity_id = ? AND currency = ? AND timestamp = ?"
        + _profile_clause(conn),
        (entity_id, currency, timestamp) + _profile_params(conn),
    ).fetchone()
    return dict(row) if row else None


def get_previous_snapshot(conn: sqlite3.Connection, entity_id: int, currency: str, timestamp: str) -> dict | None:
    row = conn.execute(
        "SELECT id, entity_id, currency, amount, timestamp, notes FROM balance_snapshots WHERE entity_id = ? AND currency = ? AND timestamp < ?"
        + _profile_clause(conn)
        + " ORDER BY timestamp DESC LIMIT 1",
        (entity_id, currency, timestamp) + _profile_params(conn),
    ).fetchone()
    return dict(row) if row else None


def get_next_snapshot(conn: sqlite3.Connection, entity_id: int, currency: str, timestamp: str) -> dict | None:
    row = conn.execute(
        "SELECT id, entity_id, currency, amount, timestamp, notes FROM balance_snapshots WHERE entity_id = ? AND currency = ? AND timestamp > ?"
        + _profile_clause(conn)
        + " ORDER BY timestamp ASC LIMIT 1",
        (entity_id, currency, timestamp) + _profile_params(conn),
    ).fetchone()
    return dict(row) if row else None


def get_snapshots_for_entity(conn: sqlite3.Connection, entity_id: int, currency: str) -> list[dict]:
    rows = conn.execute(
        "SELECT id, entity_id, currency, amount, timestamp, notes FROM balance_snapshots WHERE entity_id = ? AND currency = ?"
        + _profile_clause(conn)
        + " ORDER BY timestamp",
        (entity_id, currency) + _profile_params(conn),
    ).fetchall()
    return [dict(r) for r in rows]


def get_transactions_between(
    conn: sqlite3.Connection,
    entity_id: int,
    currency: str,
    start: str,
    end: str,
    exclude_adjustment_snapshot_id: int | None = None,
    exclude_adjustment_id: int | None = None,
    exclude_transaction_id: int | None = None,
) -> list[dict]:
    params: list = [entity_id, currency, start, end]
    extra = ""
    if exclude_adjustment_snapshot_id is not None:
        extra += " AND NOT (type = 'BALANCE_ADJUSTMENT' AND balance_snapshot_id IS ?)"
        params.append(exclude_adjustment_snapshot_id)
    if exclude_adjustment_id is not None:
        extra += " AND NOT (type = 'BALANCE_ADJUSTMENT' AND id = ?)"
        params.append(exclude_adjustment_id)
    if exclude_transaction_id is not None:
        extra += " AND id != ?"
        params.append(exclude_transaction_id)
    rows = conn.execute(
        """SELECT id, timestamp, type, entity_id, currency, total_value, notes
           FROM transactions
           WHERE entity_id = ? AND currency = ? AND timestamp >= ? AND timestamp < ?"""
        + extra
        + _profile_clause(conn)
        + " ORDER BY timestamp",
        tuple(params) + _profile_params(conn),
    ).fetchall()
    return [dict(r) for r in rows]


def adjustment_timestamp(snapshot_timestamp: str) -> str:
    """Timestamp of a snapshot's reconciliation adjustment.

    The last second of the day before the snapshot (`N-1 23:59:59`), so the
    adjustment is strictly before the snapshot and is the final event of the
    interval — making ``actual_balance`` land exactly on the target.
    """
    from datetime import datetime as _dt
    from datetime import timedelta as _td

    d = _dt.strptime(snapshot_timestamp[:10], "%Y-%m-%d")
    return (d - _td(days=1)).strftime("%Y-%m-%d") + "T23:59:59"


def get_adjustment_transaction(
    conn: sqlite3.Connection, entity_id: int, currency: str, snapshot_id: int
) -> dict | None:
    row = conn.execute(
        """SELECT id, timestamp, type, entity_id, currency, total_value, balance_snapshot_id, notes
           FROM transactions
           WHERE entity_id = ? AND currency = ? AND type = 'BALANCE_ADJUSTMENT' AND balance_snapshot_id = ?"""
        + _profile_clause(conn),
        (entity_id, currency, snapshot_id) + _profile_params(conn),
    ).fetchone()
    return dict(row) if row else None


def get_injected_adjustment_at(conn: sqlite3.Connection, entity_id: int, currency: str, timestamp: str) -> dict | None:
    """Injected (standalone inferred-cash) adjustment at an exact timestamp."""
    row = conn.execute(
        """SELECT id, timestamp, type, entity_id, currency, total_value, balance_snapshot_id, notes
           FROM transactions
           WHERE entity_id = ? AND currency = ? AND type = 'BALANCE_ADJUSTMENT'
             AND balance_snapshot_id IS NULL AND notes LIKE 'Inferred cash%' AND timestamp = ?"""
        + _profile_clause(conn),
        (entity_id, currency, timestamp) + _profile_params(conn),
    ).fetchone()
    return dict(row) if row else None


def create_adjustment_transaction(
    conn: sqlite3.Connection,
    entity_id: int,
    currency: str,
    amount: float,
    timestamp: str,
    snapshot_id: int | None = None,
    notes: str | None = None,
) -> int:
    cursor = conn.execute(
        """INSERT INTO transactions (timestamp, type, entity_id, currency, total_value, balance_snapshot_id, notes, profile_id)
           VALUES (?, 'BALANCE_ADJUSTMENT', ?, ?, ?, ?, ?, ?)""",
        (timestamp, entity_id, currency, amount, snapshot_id, notes, _pid(conn)),
    )
    return _lastrowid(cursor)


def update_adjustment_transaction(
    conn: sqlite3.Connection,
    tx_id: int,
    amount: float,
    notes: str | None = None,
) -> bool:
    cursor = conn.execute(
        "UPDATE transactions SET total_value = ?, notes = ? WHERE id = ?" + _profile_clause(conn),
        (amount, notes, tx_id) + _profile_params(conn),
    )
    return cursor.rowcount > 0


def delete_adjustment_transaction(conn: sqlite3.Connection, entity_id: int, currency: str, snapshot_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM transactions WHERE entity_id = ? AND currency = ? AND type = 'BALANCE_ADJUSTMENT' AND balance_snapshot_id = ?"
        + _profile_clause(conn),
        (entity_id, currency, snapshot_id) + _profile_params(conn),
    )
    return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Balance adjustment links (injected adjustment <-> spends it funds)
# ---------------------------------------------------------------------------


def link_adjustment_to_transaction(conn: sqlite3.Connection, adjustment_id: int, transaction_id: int) -> bool:
    """Attach an injected BALANCE_ADJUSTMENT to a same-day spend. Idempotent."""
    cursor = conn.execute(
        "INSERT OR IGNORE INTO balance_adjustment_links (balance_adjustment_id, linked_transaction_id) VALUES (?, ?)",
        (adjustment_id, transaction_id),
    )
    return cursor.rowcount > 0


def get_attached_transaction_ids(conn: sqlite3.Connection, adjustment_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT linked_transaction_id FROM balance_adjustment_links WHERE balance_adjustment_id = ? ORDER BY id",
        (adjustment_id,),
    ).fetchall()
    return [r["linked_transaction_id"] for r in rows]


def get_adjustments_linked_to_transaction(conn: sqlite3.Connection, tx_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT t.* FROM transactions t "
        "JOIN balance_adjustment_links l ON l.balance_adjustment_id = t.id "
        "WHERE l.linked_transaction_id = ?" + _profile_clause(conn),
        (tx_id,) + _profile_params(conn),
    ).fetchall()
    return [dict(r) for r in rows]


def remove_links_for_transaction(conn: sqlite3.Connection, tx_id: int) -> None:
    """Drop every link row touching tx_id (either side)."""
    conn.execute(
        "DELETE FROM balance_adjustment_links WHERE balance_adjustment_id = ? OR linked_transaction_id = ?",
        (tx_id, tx_id),
    )


def delete_injection_if_unlinked(conn: sqlite3.Connection, adjustment_id: int) -> bool:
    """Delete an injected adjustment once no spend links remain.

    Only standalone inferred-cash adjustments qualify — manual adjustments and
    snapshot-linked adjustments are never touched here.
    """
    row = conn.execute("SELECT balance_snapshot_id FROM transactions WHERE id = ?", (adjustment_id,)).fetchone()
    if row is None or row["balance_snapshot_id"] is not None:
        return False
    linked = conn.execute(
        "SELECT 1 FROM balance_adjustment_links WHERE balance_adjustment_id = ? LIMIT 1", (adjustment_id,)
    ).fetchone()
    if linked:
        return False
    cursor = conn.execute(
        "DELETE FROM transactions WHERE id = ? AND type = 'BALANCE_ADJUSTMENT' AND balance_snapshot_id IS NULL "
        "AND notes LIKE 'Inferred cash%'",
        (adjustment_id,),
    )
    return cursor.rowcount > 0


def get_balance_at_date(
    conn: sqlite3.Connection,
    entity_id: int,
    currency: str,
    timestamp: str,
    exclude_adjustment_snapshot_id: int | None = None,
    exclude_adjustment_id: int | None = None,
    exclude_transaction_id: int | None = None,
    inclusive_end: bool = True,
) -> float:
    snapshot = get_previous_snapshot(conn, entity_id, currency, timestamp)
    if snapshot:
        txns = get_transactions_between(
            conn,
            entity_id,
            currency,
            snapshot["timestamp"],
            timestamp,
            exclude_adjustment_snapshot_id=exclude_adjustment_snapshot_id,
            exclude_adjustment_id=exclude_adjustment_id,
            exclude_transaction_id=exclude_transaction_id,
        )
        balance = snapshot["amount"]
        for tx in txns:
            if tx["type"] in ("INCOME", "INVESTMENT_SELL", "TRANSFER_IN"):
                balance += tx["total_value"]
            elif tx["type"] in ("MONEY_OUT", "INVESTMENT_BUY", "TRANSFER_OUT"):
                balance -= tx["total_value"]
            elif tx["type"] == "BALANCE_ADJUSTMENT":
                balance += tx["total_value"] or 0.0
        fee_t = compute_fee_cash_out_at(
            conn, entity_id, currency, timestamp, exclude_transaction_id=exclude_transaction_id
        )
        fee_s = compute_fee_cash_out_at(
            conn, entity_id, currency, snapshot["timestamp"], exclude_transaction_id=exclude_transaction_id
        )
        balance -= fee_t - fee_s
        return balance

    operator = "<=" if inclusive_end else "<"
    if timestamp != "now":
        ts_filter = f"timestamp {operator} '{timestamp}'"
    else:
        ts_filter = "timestamp <= datetime('now')"
    extra = ""
    params: list = [entity_id, currency]
    if exclude_adjustment_snapshot_id is not None:
        extra += " AND NOT (type = 'BALANCE_ADJUSTMENT' AND balance_snapshot_id IS ?)"
        params.append(exclude_adjustment_snapshot_id)
    if exclude_adjustment_id is not None:
        extra += " AND NOT (type = 'BALANCE_ADJUSTMENT' AND id = ?)"
        params.append(exclude_adjustment_id)
    if exclude_transaction_id is not None:
        extra += " AND id != ?"
        params.append(exclude_transaction_id)
    row = conn.execute(
        f"""
        SELECT COALESCE(SUM(
            CASE
                WHEN type IN ('INCOME', 'INVESTMENT_SELL', 'TRANSFER_IN') THEN total_value
                WHEN type IN ('MONEY_OUT', 'INVESTMENT_BUY', 'TRANSFER_OUT') THEN -total_value
                WHEN type = 'BALANCE_ADJUSTMENT' THEN total_value
                ELSE 0
            END
        ), 0) AS balance
        FROM transactions
        WHERE entity_id = ? AND currency = ? AND {ts_filter}{extra}"""
        + _profile_clause(conn),
        tuple(params) + _profile_params(conn),
    ).fetchone()
    balance = row["balance"] if row else 0.0
    balance -= compute_fee_cash_out_at(
        conn, entity_id, currency, timestamp, exclude_transaction_id=exclude_transaction_id
    )
    return balance


def compute_fee_cash_out_at(
    conn: sqlite3.Connection,
    entity_id: int,
    target_currency: str,
    timestamp: str,
    exclude_transaction_id: int | None = None,
) -> float:
    """Total fee/tax cash-out for *entity_id* in *target_currency* at *timestamp*.

    Returns 0 when ``target_currency`` differs from the entity's
    ``main_currency`` (fees always charge the main pocket).  When
    ``main_currency`` is NULL, fees charge their own recorded pair and
    return 0 for any cross-pair query.
    """
    entity = get_entity(conn, entity_id)
    if entity is None:
        return 0.0
    main_currency = entity.get("main_currency")
    if main_currency is None or main_currency != target_currency:
        return 0.0

    extra = ""
    params: list = [entity_id, timestamp]
    if exclude_transaction_id is not None:
        extra = " AND t.id != ?"
        params.append(exclude_transaction_id)

    fees = conn.execute(
        f"""
        SELECT f.nature, f.fixed_amount, f.percentage, f.currency,
               t.id AS tx_id, t.total_value AS tx_total, t.timestamp AS tx_ts
        FROM transaction_fees f
        JOIN transactions t ON t.id = f.transaction_id
        WHERE t.entity_id = ? AND t.timestamp <= ?{extra}
        """
        + _profile_clause(conn, "f.profile_id"),
        tuple(params) + _profile_params(conn),
    ).fetchall()

    taxes = conn.execute(
        f"""
        SELECT tx.tax_amount, tx.currency,
               t.id AS tx_id, t.timestamp AS tx_ts
        FROM transaction_taxes tx
        JOIN transactions t ON t.id = tx.transaction_id
        WHERE t.entity_id = ? AND t.timestamp <= ? AND tx.tax_amount IS NOT NULL{extra}
        """
        + _profile_clause(conn, "tx.profile_id"),
        tuple(params) + _profile_params(conn),
    ).fetchall()

    total = 0.0
    rate_cache: dict[str, float | None] = {}

    for f in fees:
        if f["nature"] == "FIXED":
            amt = f["fixed_amount"]
        elif f["nature"] == "PERCENTAGE":
            amt = f["percentage"] * f["tx_total"] / 100.0
        elif f["nature"] == "BOTH":
            amt = f["fixed_amount"] + f["percentage"] * f["tx_total"] / 100.0
        elif f["nature"] == "MIN":
            amt = min(f["fixed_amount"], f["percentage"] * f["tx_total"] / 100.0)
        else:
            continue

        fee_cur = f["currency"]
        if fee_cur == main_currency:
            total += amt
        else:
            cache_key = f"{fee_cur}:{main_currency}"
            if cache_key not in rate_cache:
                r = get_rate_at(conn, fee_cur, main_currency, datetime.fromisoformat(f["tx_ts"]))
                rate_cache[cache_key] = r["rate"] if r else None
            rate = rate_cache[cache_key]
            if rate is not None:
                total += amt * rate

    for t in taxes:
        tax_cur = t["currency"]
        amt = t["tax_amount"]
        if tax_cur == main_currency:
            total += amt
        else:
            cache_key = f"{tax_cur}:{main_currency}"
            if cache_key not in rate_cache:
                r = get_rate_at(conn, tax_cur, main_currency, datetime.fromisoformat(t["tx_ts"]))
                rate_cache[cache_key] = r["rate"] if r else None
            rate = rate_cache[cache_key]
            if rate is not None:
                total += amt * rate

    return total


# ---------------------------------------------------------------------------
# Schedule queries
# ---------------------------------------------------------------------------


def create_schedule(
    conn: sqlite3.Connection,
    description: str,
    start_date: str,
    periodicity_type: str,
    end_date: str | None = None,
    custom_cron: str | None = None,
    entity_id: int | None = None,
    currency: str | None = None,
    type_: str | None = None,
    income_category: str | None = None,
    total_value: float | None = None,
    notes: str | None = None,
    portfolio_asset_id: int | None = None,
) -> int:
    cursor = conn.execute(
        """INSERT INTO schedules
           (description, start_date, end_date, periodicity_type, custom_cron,
            entity_id, currency, type, income_category, total_value, notes, portfolio_asset_id, profile_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            description,
            start_date,
            end_date,
            periodicity_type,
            custom_cron,
            entity_id,
            currency,
            type_,
            income_category,
            total_value,
            notes,
            portfolio_asset_id,
            _pid(conn),
        ),
    )
    return _lastrowid(cursor)


def get_schedule(conn: sqlite3.Connection, schedule_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM schedules WHERE id = ?" + _profile_clause(conn),
        (schedule_id,) + _profile_params(conn),
    ).fetchone()
    return dict(row) if row else None


def get_all_schedules(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM schedules WHERE 1=1" + _profile_clause(conn) + " ORDER BY id", _profile_params(conn)
    ).fetchall()
    return [dict(r) for r in rows]


def update_schedule(
    conn: sqlite3.Connection,
    schedule_id: int,
    description: str,
    start_date: str,
    periodicity_type: str,
    end_date: str | None = None,
    custom_cron: str | None = None,
    entity_id: int | None = None,
    currency: str | None = None,
    type_: str | None = None,
    income_category: str | None = None,
    total_value: float | None = None,
    notes: str | None = None,
    portfolio_asset_id: int | None = None,
) -> bool:
    cursor = conn.execute(
        """UPDATE schedules
           SET description = ?, start_date = ?, end_date = ?, periodicity_type = ?,
               custom_cron = ?,
               entity_id = ?, currency = ?, type = ?, income_category = ?, total_value = ?, notes = ?,
               portfolio_asset_id = ?
           WHERE id = ?"""
        + _profile_clause(conn),
        (
            description,
            start_date,
            end_date,
            periodicity_type,
            custom_cron,
            entity_id,
            currency,
            type_,
            income_category,
            total_value,
            notes,
            portfolio_asset_id,
            schedule_id,
        )
        + _profile_params(conn),
    )
    return cursor.rowcount > 0


def delete_schedule(conn: sqlite3.Connection, schedule_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM schedules WHERE id = ?" + _profile_clause(conn),
        (schedule_id,) + _profile_params(conn),
    )
    return cursor.rowcount > 0


def get_schedule_occurrence(conn: sqlite3.Connection, schedule_id: int, occurrence_date: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM schedule_occurrences WHERE schedule_id = ? AND occurrence_date = ?" + _profile_clause(conn),
        (schedule_id, occurrence_date) + _profile_params(conn),
    ).fetchone()
    return dict(row) if row else None


def insert_schedule_occurrence(
    conn: sqlite3.Connection,
    schedule_id: int,
    occurrence_date: str,
    transaction_id: int,
) -> None:
    conn.execute(
        "INSERT INTO schedule_occurrences (schedule_id, occurrence_date, transaction_id, profile_id) VALUES (?, ?, ?, ?)",
        (schedule_id, occurrence_date, transaction_id, _pid(conn)),
    )


def delete_schedule_occurrences(conn: sqlite3.Connection, schedule_id: int) -> None:
    conn.execute(
        "DELETE FROM schedule_occurrences WHERE schedule_id = ?" + _profile_clause(conn),
        (schedule_id,) + _profile_params(conn),
    )


def create_manual_value(
    conn: sqlite3.Connection,
    portfolio_asset_id: int,
    value: float,
    effective_date: str,
    notes: str | None = None,
) -> int:
    cursor = conn.execute(
        "INSERT INTO manual_values (portfolio_asset_id, value, effective_date, notes, profile_id) VALUES (?, ?, ?, ?, ?)",
        (portfolio_asset_id, value, effective_date, notes, _pid(conn)),
    )
    return cursor.lastrowid if cursor.lastrowid else 0


def upsert_manual_value(
    conn: sqlite3.Connection,
    portfolio_asset_id: int,
    value: float,
    effective_date: str,
    notes: str | None = None,
) -> dict:
    """Insert or replace the snapshot for a (portfolio_asset_id, effective_date) pair.

    Revaluing a date that already has a snapshot replaces that date's row (UC-45).
    Returns the resulting ledger row.
    """
    conn.execute(
        "INSERT INTO manual_values (portfolio_asset_id, value, effective_date, notes, profile_id) "
        "VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT(portfolio_asset_id, effective_date) DO UPDATE SET"
        " value = excluded.value, notes = excluded.notes",
        (portfolio_asset_id, value, effective_date, notes, _pid(conn)),
    )
    row = conn.execute(
        "SELECT * FROM manual_values WHERE portfolio_asset_id = ? AND effective_date = ?" + _profile_clause(conn),
        (portfolio_asset_id, effective_date) + _profile_params(conn),
    ).fetchone()
    return dict(row)


def get_manual_values(conn: sqlite3.Connection, portfolio_asset_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM manual_values WHERE portfolio_asset_id = ?"
        + _profile_clause(conn)
        + " ORDER BY effective_date DESC",
        (portfolio_asset_id,) + _profile_params(conn),
    ).fetchall()
    return [dict(r) for r in rows]


def get_latest_manual_value(conn: sqlite3.Connection, portfolio_asset_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM manual_values WHERE portfolio_asset_id = ?"
        + _profile_clause(conn)
        + " ORDER BY effective_date DESC LIMIT 1",
        (portfolio_asset_id,) + _profile_params(conn),
    ).fetchone()
    return dict(row) if row else None


def get_manual_value_as_of(conn: sqlite3.Connection, portfolio_asset_id: int, date_str: str) -> float | None:
    row = conn.execute(
        "SELECT value FROM manual_values WHERE portfolio_asset_id = ? AND effective_date <= ?"
        + _profile_clause(conn)
        + " ORDER BY effective_date DESC LIMIT 1",
        (portfolio_asset_id, date_str) + _profile_params(conn),
    ).fetchone()
    return row["value"] if row else None


def delete_manual_value(conn: sqlite3.Connection, value_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM manual_values WHERE id = ?" + _profile_clause(conn),
        (value_id,) + _profile_params(conn),
    )
    return cursor.rowcount > 0


def get_manual_tracked_assets(conn: sqlite3.Connection) -> list[dict]:
    pid_clause = _profile_clause(conn, "pa.profile_id")
    rows = conn.execute(
        f"""
        SELECT pa.id, pa.market_code, ma.currency_code
        FROM portfolio_assets pa
        JOIN market_assets ma ON ma.market_code = pa.market_code
        WHERE pa.tracking_mode = 'manual' AND pa.is_active = 1{pid_clause}
    """,
        _profile_params(conn),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Profile queries
# ---------------------------------------------------------------------------


def get_all_profiles(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, name, password_hash, default_fiscal_rule, created_at FROM profiles ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


def get_profile(conn: sqlite3.Connection, profile_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id, name, password_hash, default_fiscal_rule, created_at FROM profiles WHERE id = ?", (profile_id,)
    ).fetchone()
    return dict(row) if row else None


def get_profile_by_name(conn: sqlite3.Connection, name: str) -> dict | None:
    row = conn.execute(
        "SELECT id, name, password_hash, default_fiscal_rule, created_at FROM profiles WHERE name = ?", (name,)
    ).fetchone()
    return dict(row) if row else None


def create_profile(conn: sqlite3.Connection, name: str, password_hash: str | None) -> int:
    cursor = conn.execute("INSERT INTO profiles (name, password_hash) VALUES (?, ?)", (name, password_hash))
    return _lastrowid(cursor)


def rename_profile(conn: sqlite3.Connection, profile_id: int, name: str) -> bool:
    cursor = conn.execute("UPDATE profiles SET name = ?, updated_at = datetime('now') WHERE id = ?", (name, profile_id))
    return cursor.rowcount > 0


def update_profile_default_fiscal_rule(conn: sqlite3.Connection, profile_id: int, ruleset: str | None) -> bool:
    cursor = conn.execute(
        "UPDATE profiles SET default_fiscal_rule = ?, updated_at = datetime('now') WHERE id = ?",
        (ruleset, profile_id),
    )
    return cursor.rowcount > 0


def delete_profile(conn: sqlite3.Connection, profile_id: int) -> bool:
    cursor = conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
    return cursor.rowcount > 0


def count_profiles(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS c FROM profiles").fetchone()
    return int(row["c"])
