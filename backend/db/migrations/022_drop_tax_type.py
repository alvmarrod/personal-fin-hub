"""Replace free-text tax entry with the tax_definitions catalog (Phase 4).

The code migration phase (021) added ``transaction_taxes.tax_definition_id``
but kept ``tax_type`` for free-text rows. This migration makes the catalog the
only way to record a tax:

  - Creates a generic ``foreign_withholding`` definition (ruleset-free, no
    rate) if it is not present.
  - Backfills the legacy rows that have ``tax_definition_id`` NULL by pointing
    them at that generic definition.
  - Rebuilds ``transaction_taxes`` without ``tax_type``, with
    ``tax_definition_id`` NOT NULL.  The existing ``idx_transaction_taxes_profile``
    index is recreated.

``transaction_fees.broker_fee_definition_id`` stays nullable: fees keep
free-text amounts under a catalog label, not a required FK.

Idempotent: on a schema that no longer has ``tax_type`` it does nothing.
"""

from db.connection import _column_exists, _table_exists

GENERIC_SLUG = "foreign_withholding"
GENERIC_NAME = "Foreign Withholding"


def up(conn):
    if _table_exists(conn, "transaction_taxes") and _column_exists(conn, "transaction_taxes", "tax_type"):
        if _table_exists(conn, "tax_definitions"):
            conn.execute(
                "INSERT OR IGNORE INTO tax_definitions (slug, ruleset_key, name, rate) VALUES (?, NULL, ?, NULL)",
                (GENERIC_SLUG, GENERIC_NAME),
            )
            conn.execute(
                """
                UPDATE transaction_taxes
                SET tax_definition_id = (SELECT id FROM tax_definitions WHERE slug = ?)
                WHERE tax_definition_id IS NULL
                """,
                (GENERIC_SLUG,),
            )
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        conn.execute("PRAGMA foreign_keys=OFF")
        try:
            conn.execute(
                """
                CREATE TABLE transaction_taxes_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id INTEGER NOT NULL REFERENCES transactions(id),
                    tax_definition_id INTEGER NOT NULL REFERENCES tax_definitions(id),
                    tax_rate REAL,
                    tax_amount REAL,
                    currency TEXT NOT NULL REFERENCES currencies(code),
                    profile_id INTEGER REFERENCES profiles(id)
                )
                """
            )
            conn.execute(
                """
                INSERT INTO transaction_taxes_new
                    (id, transaction_id, tax_definition_id, tax_rate, tax_amount, currency, profile_id)
                SELECT id, transaction_id, tax_definition_id, tax_rate, tax_amount, currency, profile_id
                FROM transaction_taxes
                """
            )
            conn.execute("DROP TABLE transaction_taxes")
            conn.execute("ALTER TABLE transaction_taxes_new RENAME TO transaction_taxes")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transaction_taxes_profile ON transaction_taxes(profile_id)")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.execute(f"PRAGMA foreign_keys={fk}")


def verify(conn):
    if not _table_exists(conn, "transaction_taxes"):
        return True
    if _column_exists(conn, "transaction_taxes", "tax_type"):
        return False
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='transaction_taxes'").fetchone()
    return row is not None and "tax_definition_id INTEGER NOT NULL" in (row["sql"] or "")
