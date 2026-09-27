"""Introduce the versioned tax data catalog and retire tax_rates (Phase 1).

Creates the five catalog tables from ``tax_definitions_engine.md`` (decisions
1-7):

  - ``tax_bases``: one row per ruleset (+ optional year_start) with
    ``computation`` in ('progressive', 'flat') and a direct ``flat_rate``.
  - ``tax_base_categories``: which income categories feed a base. Fixed per
    ruleset, not year-versioned.
  - ``tax_base_rates``: bracket rows, only for progressive bases.
  - ``tax_definitions``: per-operation taxes/levies with a stable ``slug``.
  - ``broker_fee_definitions``: pure broker-fee catalog, no formula.

Adds the per-operation FK columns that replace free-text entry:

  - ``transaction_taxes.tax_definition_id`` → tax_definitions(id)
  - ``transaction_fees.broker_fee_definition_id`` → broker_fee_definitions(id)

Drops the retired ``tax_rates`` table. 013's verify() no longer asserts
``tax_rates`` exists (edit shipped with this phase), so the runner does not
re-create it on every boot.

``tax_type`` on ``transaction_taxes`` is kept in place; the column DROP ships
with the code migration phase.  The existing transaction_taxes/fees rows stay
with NULL FKs (no seed data this phase).  Idempotent.
"""

from db.connection import _column_exists, _table_exists


def up(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tax_bases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ruleset_key TEXT NOT NULL,
            name TEXT NOT NULL,
            computation TEXT NOT NULL CHECK (computation IN ('progressive', 'flat')),
            flat_rate REAL,
            year_start INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tax_base_categories (
            tax_base_id INTEGER NOT NULL REFERENCES tax_bases(id),
            category TEXT NOT NULL CHECK (category IN ('capital_gains', 'dividends', 'interest')),
            PRIMARY KEY (tax_base_id, category)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tax_base_rates (
            tax_base_id INTEGER NOT NULL REFERENCES tax_bases(id),
            from_amount REAL NOT NULL,
            to_amount REAL,
            rate REAL NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tax_definitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL UNIQUE,
            ruleset_key TEXT,
            name TEXT NOT NULL,
            rate REAL,
            year_start INTEGER
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS broker_fee_definitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
        """
    )
    if _table_exists(conn, "transaction_taxes") and not _column_exists(conn, "transaction_taxes", "tax_definition_id"):
        conn.execute(
            "ALTER TABLE transaction_taxes ADD COLUMN tax_definition_id INTEGER REFERENCES tax_definitions(id)"
        )
    if _table_exists(conn, "transaction_fees") and not _column_exists(
        conn, "transaction_fees", "broker_fee_definition_id"
    ):
        conn.execute(
            "ALTER TABLE transaction_fees ADD COLUMN broker_fee_definition_id INTEGER REFERENCES broker_fee_definitions(id)"
        )
    if _table_exists(conn, "tax_rates"):
        conn.execute("DROP TABLE tax_rates")
    conn.commit()


def verify(conn):
    return (
        _table_exists(conn, "tax_bases")
        and _table_exists(conn, "tax_base_categories")
        and _table_exists(conn, "tax_base_rates")
        and _table_exists(conn, "tax_definitions")
        and _table_exists(conn, "broker_fee_definitions")
        and not _table_exists(conn, "tax_rates")
        and (
            not _table_exists(conn, "transaction_taxes")
            or _column_exists(conn, "transaction_taxes", "tax_definition_id")
        )
        and (
            not _table_exists(conn, "transaction_fees")
            or _column_exists(conn, "transaction_fees", "broker_fee_definition_id")
        )
    )
