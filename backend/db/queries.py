import sqlite3
from datetime import datetime
from typing import Optional

from models.enums import EntityType


# ---------------------------------------------------------------------------
# Entity queries
# ---------------------------------------------------------------------------


def create_entity(
    conn: sqlite3.Connection,
    name: str,
    entity_type: EntityType,
    country: str | None = None,
    description: str | None = None,
) -> int:
    cursor = conn.execute(
        "INSERT INTO entities (name, entity_type, country, description) VALUES (?, ?, ?, ?)",
        (name, entity_type.value, country, description),
    )
    return cursor.lastrowid


def get_entity(conn: sqlite3.Connection, entity_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id, name, entity_type, country, description FROM entities WHERE id = ? AND deleted_at IS NULL",
        (entity_id,),
    ).fetchone()
    return dict(row) if row else None


def get_all_entities(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, name, entity_type, country, description FROM entities WHERE deleted_at IS NULL ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


def update_entity(
    conn: sqlite3.Connection,
    entity_id: int,
    name: str,
    entity_type: EntityType,
    country: str | None = None,
    description: str | None = None,
) -> bool:
    cursor = conn.execute(
        "UPDATE entities SET name = ?, entity_type = ?, country = ?, description = ? WHERE id = ?",
        (name, entity_type.value, country, description, entity_id),
    )
    return cursor.rowcount > 0


def delete_entity(conn: sqlite3.Connection, entity_id: int) -> bool:
    cursor = conn.execute(
        "UPDATE entities SET deleted_at = datetime('now') WHERE id = ?", (entity_id,)
    )
    return cursor.rowcount > 0


def entity_exists(
    conn: sqlite3.Connection, name: str, entity_type: EntityType
) -> bool:
    row = conn.execute(
        "SELECT 1 FROM entities WHERE name = ? AND entity_type = ? AND deleted_at IS NULL LIMIT 1",
        (name, entity_type.value),
    ).fetchone()
    return row is not None


def entity_has_assets(conn: sqlite3.Connection, entity_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM transactions WHERE entity_id = ? LIMIT 1",
        (entity_id,),
    ).fetchone()
    return row is not None


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
           (exemption_type, description, exemption_amount, exemption_rate, exemption_rate_limit)
           VALUES (?, ?, ?, ?, ?)""",
        (exemption_type, description, exemption_amount, exemption_rate, exemption_rate_limit),
    )
    return cursor.lastrowid


def get_fiscal_exemption(conn: sqlite3.Connection, exemption_id: int) -> dict | None:
    row = conn.execute(
        """SELECT id, exemption_type, description, exemption_amount, exemption_rate, exemption_rate_limit
           FROM fiscal_exemptions WHERE id = ?""",
        (exemption_id,),
    ).fetchone()
    return dict(row) if row else None


def get_all_fiscal_exemptions(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, exemption_type, description, exemption_amount, exemption_rate, exemption_rate_limit FROM fiscal_exemptions ORDER BY id"
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
           WHERE id = ?""",
        (exemption_type, description, exemption_amount, exemption_rate, exemption_rate_limit, exemption_id),
    )
    return cursor.rowcount > 0


def delete_fiscal_exemption(conn: sqlite3.Connection, exemption_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM fiscal_exemptions WHERE id = ?", (exemption_id,)
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
    cursor = conn.execute(
        "DELETE FROM market_assets WHERE market_code = ?", (market_code,)
    )
    return cursor.rowcount > 0


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
    purchase_date: str | None = None,
    notes: str | None = None,
) -> int:
    cursor = conn.execute(
        """INSERT INTO portfolio_assets
           (market_code, distribution_type, dca_status, layer, tactic, desired_weight, ter,
            tracking_mode, current_value_manual, is_active, closing_date, purchase_date, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (market_code, distribution_type, dca_status, layer, tactic, desired_weight, ter,
         tracking_mode, current_value_manual, is_active, closing_date, purchase_date, notes),
    )
    return cursor.lastrowid


def get_portfolio_asset(conn: sqlite3.Connection, asset_id: int) -> dict | None:
    row = conn.execute(
        """SELECT id, market_code, distribution_type, dca_status, layer, tactic,
                  desired_weight, ter, tracking_mode, current_value_manual,
                  is_active, closing_date, purchase_date, notes
           FROM portfolio_assets WHERE id = ?""",
        (asset_id,),
    ).fetchone()
    return dict(row) if row else None


def get_all_portfolio_assets(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """SELECT id, market_code, distribution_type, dca_status, layer, tactic,
                  desired_weight, ter, tracking_mode, current_value_manual,
                  is_active, closing_date, purchase_date, notes
           FROM portfolio_assets ORDER BY id"""
    ).fetchall()
    return [dict(r) for r in rows]


def get_portfolio_assets_by_market(
    conn: sqlite3.Connection, market_code: str
) -> list[dict]:
    rows = conn.execute(
        """SELECT id, market_code, distribution_type, dca_status, layer, tactic,
                  desired_weight, ter, tracking_mode, current_value_manual,
                  is_active, closing_date, purchase_date, notes
           FROM portfolio_assets WHERE market_code = ? ORDER BY id""",
        (market_code,),
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
    purchase_date: str | None = None,
    notes: str | None = None,
) -> bool:
    cursor = conn.execute(
        """UPDATE portfolio_assets
           SET market_code = ?, distribution_type = ?, dca_status = ?, layer = ?, tactic = ?,
               desired_weight = ?, ter = ?, tracking_mode = ?, current_value_manual = ?,
               is_active = ?, closing_date = ?, purchase_date = ?, notes = ?
           WHERE id = ?""",
        (market_code, distribution_type, dca_status, layer, tactic, desired_weight, ter,
         tracking_mode, current_value_manual, is_active, closing_date, purchase_date, notes, asset_id),
    )
    return cursor.rowcount > 0


def delete_portfolio_asset(conn: sqlite3.Connection, asset_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM portfolio_assets WHERE id = ?", (asset_id,)
    )
    return cursor.rowcount > 0


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


def create_self_rate(
    conn: sqlite3.Connection, code: str, timestamp: datetime
) -> None:
    conn.execute(
        "INSERT INTO currencies (code, base_code, rate, timestamp) VALUES (?, ?, 1.0, ?)",
        (code, code, timestamp),
    )


def get_distinct_pairs(
    conn: sqlite3.Connection, code: Optional[str] = None
) -> list[tuple[str, str]]:
    if code:
        rows = conn.execute(
            """SELECT DISTINCT code, base_code FROM currencies
               WHERE code = ? OR base_code = ?
               ORDER BY code, base_code""",
            (code, code),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT DISTINCT code, base_code FROM currencies ORDER BY code, base_code"
        ).fetchall()
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
        (code, base_code, rate, timestamp),
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
        (code, base_code, rate, timestamp),
    )


def get_latest_rate(
    conn: sqlite3.Connection, code: str, base_code: str
) -> Optional[dict]:
    row = conn.execute(
        """SELECT code, base_code, rate, timestamp
           FROM currencies
           WHERE code = ? AND base_code = ?
           ORDER BY timestamp DESC
           LIMIT 1""",
        (code, base_code),
    ).fetchone()
    return dict(row) if row else None


def get_rate_at(
    conn: sqlite3.Connection, code: str, base_code: str, at: datetime
) -> Optional[dict]:
    row = conn.execute(
        """SELECT code, base_code, rate, timestamp
           FROM currencies
           WHERE code = ? AND base_code = ?
           ORDER BY ABS(julianday(timestamp) - julianday(?))
           LIMIT 1""",
        (code, base_code, at),
    ).fetchone()
    return dict(row) if row else None


def get_rate_history(
    conn: sqlite3.Connection, code: str, base_code: str
) -> list[dict]:
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
        (rate, code, base_code, timestamp),
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


# ---------------------------------------------------------------------------
# Transaction queries
# ---------------------------------------------------------------------------


def create_transaction(
    conn: sqlite3.Connection,
    timestamp: str,
    type_: str,
    entity_id: int,
    currency: str,
    total_value: float | None = None,
    transaction_category: str | None = None,
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
) -> int:
    cursor = conn.execute(
        """INSERT INTO transactions
           (timestamp, type, transaction_category, entity_id, portfolio_asset_id,
            quantity, unit_price, currency, total_value,
            gross_amount, net_amount, payment_currency, fx_rate, settlement_date,
            fiscal_exemption_id, dividend_type, record_date, payment_date,
            dividend_currency, dividend_payment_currency, dividend_fx_rate, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (timestamp, type_, transaction_category, entity_id, portfolio_asset_id,
         quantity, unit_price, currency, total_value,
         gross_amount, net_amount, payment_currency, fx_rate, settlement_date,
         fiscal_exemption_id, dividend_type, record_date, payment_date,
         dividend_currency, dividend_payment_currency, dividend_fx_rate, notes),
    )
    return cursor.lastrowid


def get_transaction(conn: sqlite3.Connection, tx_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM transactions WHERE id = ?", (tx_id,)
    ).fetchone()
    return dict(row) if row else None


def get_all_transactions(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM transactions ORDER BY timestamp DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_transactions_by_portfolio(
    conn: sqlite3.Connection, portfolio_asset_id: int
) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM transactions WHERE portfolio_asset_id = ? ORDER BY timestamp DESC",
        (portfolio_asset_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_transactions_by_entity(
    conn: sqlite3.Connection, entity_id: int
) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM transactions WHERE entity_id = ? ORDER BY timestamp DESC",
        (entity_id,),
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
    transaction_category: str | None = None,
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
) -> bool:
    cursor = conn.execute(
        """UPDATE transactions
           SET timestamp = ?, type = ?, transaction_category = ?, entity_id = ?,
               portfolio_asset_id = ?, quantity = ?, unit_price = ?, currency = ?,
               total_value = ?, gross_amount = ?, net_amount = ?, payment_currency = ?,
               fx_rate = ?, settlement_date = ?, fiscal_exemption_id = ?, dividend_type = ?,
               record_date = ?, payment_date = ?, dividend_currency = ?,
               dividend_payment_currency = ?, dividend_fx_rate = ?, notes = ?
           WHERE id = ?""",
        (timestamp, type_, transaction_category, entity_id,
         portfolio_asset_id, quantity, unit_price, currency,
         total_value, gross_amount, net_amount, payment_currency,
         fx_rate, settlement_date, fiscal_exemption_id, dividend_type,
         record_date, payment_date, dividend_currency,
         dividend_payment_currency, dividend_fx_rate, notes, tx_id),
    )
    return cursor.rowcount > 0


def delete_transaction(conn: sqlite3.Connection, tx_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM transactions WHERE id = ?", (tx_id,)
    )
    return cursor.rowcount > 0


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
        "INSERT INTO transaction_fees (transaction_id, fee_type, nature, fixed_amount, percentage, currency) VALUES (?, ?, ?, ?, ?, ?)",
        (transaction_id, fee_type, nature, fixed_amount, percentage, currency),
    )
    return cursor.lastrowid


def get_fee(conn: sqlite3.Connection, fee_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM transaction_fees WHERE id = ?", (fee_id,)
    ).fetchone()
    return dict(row) if row else None


def get_fees_by_transaction(conn: sqlite3.Connection, transaction_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM transaction_fees WHERE transaction_id = ? ORDER BY id",
        (transaction_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_fees(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM transaction_fees ORDER BY id"
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
        "UPDATE transaction_fees SET transaction_id = ?, fee_type = ?, nature = ?, fixed_amount = ?, percentage = ?, currency = ? WHERE id = ?",
        (transaction_id, fee_type, nature, fixed_amount, percentage, currency, fee_id),
    )
    return cursor.rowcount > 0


def delete_fee(conn: sqlite3.Connection, fee_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM transaction_fees WHERE id = ?", (fee_id,)
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
        "INSERT INTO transaction_taxes (transaction_id, tax_type, tax_rate, tax_amount, currency) VALUES (?, ?, ?, ?, ?)",
        (transaction_id, tax_type, tax_rate, tax_amount, currency),
    )
    return cursor.lastrowid


def get_tax(conn: sqlite3.Connection, tax_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM transaction_taxes WHERE id = ?", (tax_id,)
    ).fetchone()
    return dict(row) if row else None


def get_taxes_by_transaction(conn: sqlite3.Connection, transaction_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM transaction_taxes WHERE transaction_id = ? ORDER BY id",
        (transaction_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_taxes(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM transaction_taxes ORDER BY id"
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
        "UPDATE transaction_taxes SET transaction_id = ?, tax_type = ?, tax_rate = ?, tax_amount = ?, currency = ? WHERE id = ?",
        (transaction_id, tax_type, tax_rate, tax_amount, currency, tax_id),
    )
    return cursor.rowcount > 0


def delete_tax(conn: sqlite3.Connection, tax_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM transaction_taxes WHERE id = ?", (tax_id,)
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
    return cursor.lastrowid


def get_price(conn: sqlite3.Connection, price_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM prices WHERE id = ?", (price_id,)
    ).fetchone()
    return dict(row) if row else None


def get_prices_by_market(conn: sqlite3.Connection, market_code: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM prices WHERE market_code = ? ORDER BY timestamp DESC",
        (market_code,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_prices(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM prices ORDER BY market_code, timestamp DESC"
    ).fetchall()
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
    cursor = conn.execute(
        "DELETE FROM prices WHERE id = ?", (price_id,)
    )
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
        "INSERT INTO balance_snapshots (entity_id, currency, amount, timestamp, notes) VALUES (?, ?, ?, ?, ?)",
        (entity_id, currency, amount, timestamp, notes),
    )
    return cursor.lastrowid


def get_balance_snapshot(conn: sqlite3.Connection, snapshot_id: int) -> dict | None:
    row = conn.execute(
        "SELECT id, entity_id, currency, amount, timestamp, notes FROM balance_snapshots WHERE id = ?",
        (snapshot_id,),
    ).fetchone()
    return dict(row) if row else None


def get_all_balance_snapshots(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, entity_id, currency, amount, timestamp, notes FROM balance_snapshots ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


def get_latest_snapshot(
    conn: sqlite3.Connection, entity_id: int, currency: str
) -> dict | None:
    row = conn.execute(
        "SELECT id, entity_id, currency, amount, timestamp, notes FROM balance_snapshots WHERE entity_id = ? AND currency = ? ORDER BY timestamp DESC LIMIT 1",
        (entity_id, currency),
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
        "UPDATE balance_snapshots SET entity_id = ?, currency = ?, amount = ?, timestamp = ?, notes = ? WHERE id = ?",
        (entity_id, currency, amount, timestamp, notes, snapshot_id),
    )
    return cursor.rowcount > 0


def delete_balance_snapshot(conn: sqlite3.Connection, snapshot_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM balance_snapshots WHERE id = ?", (snapshot_id,)
    )
    return cursor.rowcount > 0


def has_transactions_on_or_after(
    conn: sqlite3.Connection, entity_id: int, currency: str, since: str
) -> bool:
    row = conn.execute(
        "SELECT 1 FROM transactions WHERE entity_id = ? AND currency = ? AND timestamp >= ? LIMIT 1",
        (entity_id, currency, since),
    ).fetchone()
    return row is not None


def has_schedules_on_or_before(
    conn: sqlite3.Connection, entity_id: int, currency: str, until: str
) -> bool:
    row = conn.execute(
        """SELECT 1 FROM schedules s
           JOIN transactions t ON s.linked_transaction_id = t.id
           WHERE t.entity_id = ? AND t.currency = ? AND s.start_date <= ? LIMIT 1""",
        (entity_id, currency, until),
    ).fetchone()
    return row is not None


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
    linked_transaction_id: int | None = None,
) -> int:
    cursor = conn.execute(
        "INSERT INTO schedules (description, start_date, end_date, periodicity_type, custom_cron, linked_transaction_id) VALUES (?, ?, ?, ?, ?, ?)",
        (description, start_date, end_date, periodicity_type, custom_cron, linked_transaction_id),
    )
    return cursor.lastrowid


def get_schedule(conn: sqlite3.Connection, schedule_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM schedules WHERE id = ?", (schedule_id,)
    ).fetchone()
    return dict(row) if row else None


def get_all_schedules(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM schedules ORDER BY id"
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
    linked_transaction_id: int | None = None,
) -> bool:
    cursor = conn.execute(
        "UPDATE schedules SET description = ?, start_date = ?, end_date = ?, periodicity_type = ?, custom_cron = ?, linked_transaction_id = ? WHERE id = ?",
        (description, start_date, end_date, periodicity_type, custom_cron, linked_transaction_id, schedule_id),
    )
    return cursor.rowcount > 0


def delete_schedule(conn: sqlite3.Connection, schedule_id: int) -> bool:
    cursor = conn.execute(
        "DELETE FROM schedules WHERE id = ?", (schedule_id,)
    )
    return cursor.rowcount > 0
