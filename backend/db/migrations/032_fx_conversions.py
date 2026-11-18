"""Add the FX_CONVERSION type, ``auto_generated`` and the cash-flow view.

A currency conversion is a single transaction: ``currency`` (source) is
debited by ``total_value`` and ``payment_currency`` (destination) is credited
by ``gross_amount``. ``auto_generated`` separates conversions the funding
engine creates from user-recorded broker conversions.

``transaction_cash_flows`` normalizes every transaction into signed per-pocket
movements so the cash queries can stay single-sided.

Idempotent: ``verify`` checks the type CHECK, the column and the view.
"""

from db.connection import _column_exists

TRANSACTIONS_DDL = """
    CREATE TABLE transactions_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME NOT NULL,
        type TEXT NOT NULL CHECK (type IN ('INCOME', 'MONEY_OUT', 'INVESTMENT_BUY', 'INVESTMENT_SELL', 'TRANSFER', 'TRANSFER_IN', 'TRANSFER_OUT', 'BALANCE_ADJUSTMENT', 'FX_CONVERSION')),
        investment_transaction_category TEXT CHECK (investment_transaction_category IN ('NORMAL', 'DCA', 'REBALANCE')),
        income_category TEXT CHECK (income_category IN ('salary', 'other', 'dividends', 'interest', 'cashback')),
        entity_id INTEGER NOT NULL REFERENCES entities(id),
        portfolio_asset_id INTEGER REFERENCES portfolio_assets(id),
        quantity REAL,
        unit_price REAL,
        currency TEXT NOT NULL REFERENCES currencies(code),
        total_value REAL,
        gross_amount REAL,
        net_amount REAL,
        payment_currency TEXT REFERENCES currencies(code),
        fx_rate REAL,
        settlement_date DATE,
        fiscal_exemption_id INTEGER REFERENCES fiscal_exemptions(id),
        fiscal_rule TEXT,
        dividend_type TEXT CHECK (dividend_type IN ('regular', 'special', 'qualified')),
        record_date DATE,
        payment_date DATE,
        dividend_currency TEXT REFERENCES currencies(code),
        dividend_payment_currency TEXT REFERENCES currencies(code),
        dividend_fx_rate REAL,
        notes TEXT,
        balance_snapshot_id INTEGER REFERENCES balance_snapshots(id),
        cash_handling TEXT,
        auto_generated INTEGER NOT NULL DEFAULT 0,
        profile_id INTEGER REFERENCES profiles(id)
    )
"""

VIEW_DDL = """
    CREATE VIEW transaction_cash_flows AS
    SELECT
        t.id AS transaction_id,
        t.profile_id,
        t.entity_id,
        t.timestamp,
        COALESCE(t.payment_currency, t.currency) AS currency,
        CASE
            WHEN t.type IN ('INCOME', 'INVESTMENT_SELL', 'TRANSFER_IN') THEN COALESCE(t.gross_amount, t.total_value)
            WHEN t.type IN ('MONEY_OUT', 'INVESTMENT_BUY', 'TRANSFER_OUT') THEN -COALESCE(t.gross_amount, t.total_value)
            WHEN t.type = 'BALANCE_ADJUSTMENT' THEN COALESCE(t.total_value, 0.0)
            ELSE 0
        END AS amount
    FROM transactions t
    WHERE t.type <> 'FX_CONVERSION'
    UNION ALL
    SELECT t.id, t.profile_id, t.entity_id, t.timestamp, t.currency, -COALESCE(t.total_value, 0.0)
    FROM transactions t
    WHERE t.type = 'FX_CONVERSION'
    UNION ALL
    SELECT t.id, t.profile_id, t.entity_id, t.timestamp, t.payment_currency,
           COALESCE(t.gross_amount, t.total_value * t.fx_rate)
    FROM transactions t
    WHERE t.type = 'FX_CONVERSION'
"""


def _convert_pair(conn, out, inn, buy_id: int | None) -> int:
    """Replace one generated transfer pair with a single FX_CONVERSION row."""
    source_amount = out["total_value"] or 0.0
    target_amount = inn["total_value"] or 0.0
    rate = target_amount / source_amount if source_amount else None
    cursor = conn.execute(
        """INSERT INTO transactions
           (timestamp, type, entity_id, currency, total_value, payment_currency,
            fx_rate, gross_amount, net_amount, notes, auto_generated, profile_id)
           VALUES (?, 'FX_CONVERSION', ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
        (
            out["timestamp"],
            out["entity_id"],
            out["currency"],
            source_amount,
            inn["currency"],
            rate,
            target_amount,
            target_amount,
            out["notes"],
            out["profile_id"] if out["profile_id"] is not None else inn["profile_id"],
        ),
    )
    conversion_id = cursor.lastrowid
    if buy_id is not None:
        conn.execute(
            "UPDATE transaction_funding_links SET funding_transaction_id = ? "
            "WHERE transaction_id = ? AND funding_transaction_id = ?",
            (conversion_id, buy_id, out["id"]),
        )
    # Re-point any adjustment links, then drop every remaining reference.
    for leg in (out, inn):
        for link in conn.execute(
            "SELECT balance_adjustment_id FROM balance_adjustment_links WHERE linked_transaction_id = ?",
            (leg["id"],),
        ).fetchall():
            conn.execute(
                "INSERT OR IGNORE INTO balance_adjustment_links "
                "(balance_adjustment_id, linked_transaction_id) VALUES (?, ?)",
                (link["balance_adjustment_id"], conversion_id),
            )
    conn.execute(
        "DELETE FROM balance_adjustment_links WHERE linked_transaction_id IN (?, ?)",
        (out["id"], inn["id"]),
    )
    conn.execute(
        "DELETE FROM transaction_funding_links WHERE transaction_id IN (?, ?) OR funding_transaction_id IN (?, ?)",
        (out["id"], inn["id"], out["id"], inn["id"]),
    )
    conn.execute("DELETE FROM transactions WHERE id IN (?, ?)", (out["id"], inn["id"]))
    return int(conversion_id)


def _convert_generated_pairs(conn) -> None:
    from collections import defaultdict

    by_buy: dict[int, list[int]] = defaultdict(list)
    for row in conn.execute(
        "SELECT l.transaction_id AS buy_id, l.funding_transaction_id AS leg_id "
        "FROM transaction_funding_links l "
        "JOIN transactions t ON t.id = l.transaction_id "
        "WHERE t.type = 'INVESTMENT_BUY'"
    ).fetchall():
        by_buy[row["buy_id"]].append(row["leg_id"])

    handled: set[int] = set()
    for buy_id, leg_ids in by_buy.items():
        legs = [conn.execute("SELECT * FROM transactions WHERE id = ?", (leg_id,)).fetchone() for leg_id in leg_ids]
        outs = [leg for leg in legs if leg is not None and leg["type"] == "TRANSFER_OUT"]
        ins = [leg for leg in legs if leg is not None and leg["type"] == "TRANSFER_IN"]
        for out, inn in zip(outs, ins, strict=False):
            _convert_pair(conn, out, inn, buy_id)
            handled.update({out["id"], inn["id"]})

    # Orphans: a pair whose buy was deleted still moved cash; keep it as an
    # unlinked automatic conversion so balances do not change.
    orphan_rows = conn.execute(
        "SELECT * FROM transactions "
        "WHERE type IN ('TRANSFER_OUT', 'TRANSFER_IN') "
        "AND notes LIKE 'FX funding for investment buy%' "
        "ORDER BY timestamp, id"
    ).fetchall()
    pending: dict[tuple, dict] = {}
    for row in orphan_rows:
        if row["id"] in handled:
            continue
        key = (row["entity_id"], row["timestamp"], row["notes"])
        slot = pending.setdefault(key, {})
        slot.setdefault("out" if row["type"] == "TRANSFER_OUT" else "in", row)
        if "out" in slot and "in" in slot:
            _convert_pair(conn, slot["out"], slot["in"], None)
            handled.update({slot["out"]["id"], slot["in"]["id"]})
            del pending[key]


def _transactions_sql(conn) -> str:
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'transactions'").fetchone()
    return row["sql"] if row else ""


def _view_exists(conn) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'view' AND name = 'transaction_cash_flows'"
    ).fetchone()
    return row is not None


def verify(conn) -> bool:
    return (
        "FX_CONVERSION" in _transactions_sql(conn)
        and _column_exists(conn, "transactions", "auto_generated")
        and _view_exists(conn)
        and conn.execute(
            "SELECT 1 FROM transactions WHERE type IN ('TRANSFER_OUT', 'TRANSFER_IN')"
            " AND notes LIKE 'FX funding for investment buy%' LIMIT 1"
        ).fetchone()
        is None
    )


def up(conn) -> None:
    foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("DROP VIEW IF EXISTS transaction_cash_flows")
        conn.execute(TRANSACTIONS_DDL)
        cols = ", ".join(r["name"] for r in conn.execute("PRAGMA table_info(transactions)").fetchall())
        conn.execute(f"INSERT INTO transactions_new ({cols}) SELECT {cols} FROM transactions")
        conn.execute("DROP TABLE transactions")
        conn.execute("ALTER TABLE transactions_new RENAME TO transactions")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_profile ON transactions(profile_id)")
        conn.execute(VIEW_DDL)
        _convert_generated_pairs(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute(f"PRAGMA foreign_keys={foreign_keys}")
