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
        "SELECT id, name, entity_type, country, description FROM entities WHERE id = ?",
        (entity_id,),
    ).fetchone()
    return dict(row) if row else None


def get_all_entities(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, name, entity_type, country, description FROM entities ORDER BY id"
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
        "DELETE FROM entities WHERE id = ?", (entity_id,)
    )
    return cursor.rowcount > 0


def entity_exists(
    conn: sqlite3.Connection, name: str, entity_type: EntityType
) -> bool:
    row = conn.execute(
        "SELECT 1 FROM entities WHERE name = ? AND entity_type = ? LIMIT 1",
        (name, entity_type.value),
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
