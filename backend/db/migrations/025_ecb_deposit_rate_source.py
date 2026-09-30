"""Repoint the ECB deposit-rate series to the official ECB data-api (SDMX).

Data-only migration (no schema change): the ``ecb-deposit-rate`` row seeded by
024 pointed at the Investing.com economic calendar. It now uses the ECB Data
Portal ``data-api`` SDMX endpoint for the deposit-facility "date of changes"
series:

    series key : FM.D.U2.EUR.4F.KR.DFR.LEV
    dataset    : FM (Financial market data)
    frequency  : daily
    unit       : percent per annum

The daily series repeats a value until the rate changes; the client keeps only
change points, so the stored series stays one observation per policy-rate
change (the existing normalized semantics).

The ``provider`` moves from ``investing-com`` to ``ecb`` (both are allowed by
the schema's CHECK constraint), and the client selects the SDMX-JSON parse
path from the ``data-api.ecb.europa.eu`` source URL.

Idempotent: the update is repeated-safe (same values), and ``verify`` asserts
the row is on the ECB provider and the new URL.
"""

_PROVIDER = "ecb"
_SOURCE_URL = "https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.DFR.LEV?format=jsondata"
_SLUG = "ecb-deposit-rate"
_NAME = "ECB Deposit Facility Rate (date of changes)"


def up(conn):
    conn.execute(
        "UPDATE macro_series SET provider = ?, source_url = ?, name = ? WHERE slug = ?",
        (_PROVIDER, _SOURCE_URL, _NAME, _SLUG),
    )
    conn.commit()


def verify(conn):
    row = conn.execute(
        "SELECT provider, source_url FROM macro_series WHERE slug = ?",
        (_SLUG,),
    ).fetchone()
    if row is None:
        return False
    return row["provider"] == _PROVIDER and row["source_url"] == _SOURCE_URL
