"""Seed the versioned tax catalog with the real Spain/Japan/default data (Phase 7).

Insert the agreed fiscal seed rows into the Phase-1 catalog tables
(``tax_bases``, ``tax_base_categories``, ``tax_base_rates``,
``tax_definitions``, ``broker_fee_definitions``). This is real fiscal data,
not a design decision — inserted verbatim per ``tax_definitions_engine.md``.

Contents:

  - ``spain`` and ``default``: progressive "IRPF sobre el ahorro" over the
    capital-gains/dividends/interest categories, five brackets
    (0/6000/50000/200000/300000 at 19/21/23/27/30%). ``default`` is a literal
    copy of ``spain``, not an alias.
  - ``japan``: flat "Impuesto de capitales" at 0.20315 over the same three
    categories.
  - ``latest``/``none`` stay base-less by design — the tax engine's graceful
    null handling covers them (§17.9).
  - ``spain_itf`` (Tasa Tobin, 0.2%) applies only under the ``spain``
    ruleset, never the generic ``default`` fallback.
  - ``foreign_withholding`` (generic, no rate) is ensured here so a brand-new
    database always has it: 022 only created it when a legacy ``tax_type``
    column existed, so a fresh install would otherwise never get the row.
  - Three broker-fee definitions ("Fee de compra", "Fee de venta",
    "Fee de cambio de divisa (FX)") — names only, naive by design; a fee is
    never a tax.

Idempotent by presence: each row is inserted only when no row with the same
key already exists, so a catalog row a user created by hand via Settings is
left untouched rather than duplicated or overwritten. ``verify`` asserts
presence-by-key, not value equality.
"""

from db.connection import _table_exists

_CATEGORIES = ["capital_gains", "dividends", "interest"]

# (from_amount, to_amount, rate); to_amount None = open-ended top bracket.
_SPAIN_BRACKETS = [
    (0, 6000, 0.19),
    (6000, 50000, 0.21),
    (50000, 200000, 0.23),
    (200000, 300000, 0.27),
    (300000, None, 0.30),
]

# (ruleset_key, name, computation, flat_rate, has_brackets)
_BASES = [
    ("spain", "IRPF sobre el ahorro", "progressive", None, True),
    ("default", "IRPF sobre el ahorro", "progressive", None, True),
    ("japan", "Impuesto de capitales", "flat", 0.20315, False),
]

_TASA_TOBIN = ("spain_itf", "spain", "Tasa Tobin", 0.002)
_GENERIC_WITHHOLDING = ("foreign_withholding", None, "Foreign Withholding", None)
_BROKER_FEES = ["Fee de compra", "Fee de venta", "Fee de cambio de divisa (FX)"]


def _ensure_definition(conn, slug, ruleset_key, name, rate):
    conn.execute(
        "INSERT OR IGNORE INTO tax_definitions (slug, ruleset_key, name, rate) VALUES (?, ?, ?, ?)",
        (slug, ruleset_key, name, rate),
    )


def up(conn):
    # Generic definitions (slug is UNIQUE, so INSERT OR IGNORE is a safe guard).
    _ensure_definition(conn, *_GENERIC_WITHHOLDING)
    _ensure_definition(conn, *_TASA_TOBIN)

    for ruleset_key, name, computation, flat_rate, has_brackets in _BASES:
        existing = conn.execute(
            "SELECT id FROM tax_bases WHERE ruleset_key = ? AND year_start IS NULL",
            (ruleset_key,),
        ).fetchone()
        if existing is not None:
            continue  # respect a user-created base; never duplicate or overwrite
        cursor = conn.execute(
            "INSERT INTO tax_bases (ruleset_key, name, computation, flat_rate, year_start) VALUES (?, ?, ?, ?, NULL)",
            (ruleset_key, name, computation, flat_rate),
        )
        base_id = cursor.lastrowid
        conn.executemany(
            "INSERT INTO tax_base_categories (tax_base_id, category) VALUES (?, ?)",
            [(base_id, c) for c in _CATEGORIES],
        )
        if has_brackets:
            conn.executemany(
                "INSERT INTO tax_base_rates (tax_base_id, from_amount, to_amount, rate) VALUES (?, ?, ?, ?)",
                [(base_id, from_amount, to_amount, rate) for from_amount, to_amount, rate in _SPAIN_BRACKETS],
            )

    for fee_name in _BROKER_FEES:
        if conn.execute("SELECT 1 FROM broker_fee_definitions WHERE name = ?", (fee_name,)).fetchone() is None:
            conn.execute("INSERT INTO broker_fee_definitions (name) VALUES (?)", (fee_name,))

    conn.commit()


def verify(conn):
    if not (
        _table_exists(conn, "tax_bases")
        and _table_exists(conn, "tax_base_categories")
        and _table_exists(conn, "tax_base_rates")
        and _table_exists(conn, "tax_definitions")
        and _table_exists(conn, "broker_fee_definitions")
    ):
        return False

    # Generic definitions.
    for slug in (_GENERIC_WITHHOLDING[0], _TASA_TOBIN[0]):
        if conn.execute("SELECT 1 FROM tax_definitions WHERE slug = ?", (slug,)).fetchone() is None:
            return False

    # Bases and their children (presence only, not value equality).
    for ruleset_key, _name, _computation, _flat_rate, has_brackets in _BASES:
        row = conn.execute(
            "SELECT id FROM tax_bases WHERE ruleset_key = ? AND year_start IS NULL",
            (ruleset_key,),
        ).fetchone()
        if row is None:
            return False
        base_id = row["id"]
        if (
            conn.execute("SELECT 1 FROM tax_base_categories WHERE tax_base_id = ? LIMIT 1", (base_id,)).fetchone()
            is None
        ):
            return False
        if (
            has_brackets
            and conn.execute("SELECT 1 FROM tax_base_rates WHERE tax_base_id = ? LIMIT 1", (base_id,)).fetchone()
            is None
        ):
            return False

    # Broker fee definitions.
    for fee_name in _BROKER_FEES:
        if conn.execute("SELECT 1 FROM broker_fee_definitions WHERE name = ?", (fee_name,)).fetchone() is None:
            return False

    return True
