"""Data-driven tax engine (§17.7-§17.12).

Replaces the retired ``TaxModel`` protocol/classes. Reads the versioned
catalog (``tax_bases``/``tax_base_categories``/``tax_base_rates``/
``tax_definitions``) plus confirmed ``transaction_taxes`` rows and computes:

  - per-category ``tax_owed`` (progressive: chronological bracket
    attribution per decision 10; flat: ``base × flat_rate``)
  - per-item core tax (§17.12)
  - year-level withholding for progressive rulesets (decision 8)
  - per-definition ``computed``/``confirmed`` resolution (§17.11)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from db import queries


class TaxBand:
    """One progressive bracket row (``tax_base_rates``)."""

    def __init__(self, from_amount: float, to_amount: float | None, rate: float):
        self.from_amount = from_amount
        self.to_amount = to_amount
        self.rate = rate


@dataclass(frozen=True)
class TaxDefinitionResult:
    """Per-definition resolution on one item (§17.11/§17.12)."""

    tax_definition_id: int
    slug: str
    name: str
    computed: float
    confirmed: float | None = None


@dataclass(frozen=True)
class ItemTaxResult:
    """Per-item result (§17.12)."""

    transaction_id: int
    category: str
    tax_owed: float
    taxes: list[TaxDefinitionResult] = field(default_factory=list)


@dataclass(frozen=True)
class FiscalYearTaxResult:
    """Internal per-fiscal-year tax computation, independent of the API shape."""

    tax_owed: dict[str, float]
    base: float
    total_tax: float
    withholding: float
    total_tax_owed: float
    combined_base: float | None
    confirmed: dict[str, float] = field(default_factory=dict)  # per-category, display currency
    total_confirmed: float = 0.0
    per_item: list[ItemTaxResult] = field(default_factory=list)


Convert = Callable[[float, str, datetime], float]


def resolve_tax_base(conn, ruleset_key: str, year: int | None) -> dict | None:
    """Resolve the ``tax_bases`` row for *ruleset_key* + *year* (§17.8).

    Prefers the most recent ``year_start <= year``; falls back to the
    ``year_start IS NULL`` default row. Returns None when no base is seeded.
    """
    rows = conn.execute(
        "SELECT * FROM tax_bases WHERE ruleset_key = ? AND (year_start IS NULL OR year_start <= ?)"
        " ORDER BY year_start IS NOT NULL DESC, year_start DESC",
        (ruleset_key, year if year is not None else 10**9),
    ).fetchall()
    return dict(rows[0]) if rows else None


def get_base_categories(conn, tax_base_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT category FROM tax_base_categories WHERE tax_base_id = ? ORDER BY category", (tax_base_id,)
    ).fetchall()
    return [r["category"] for r in rows]


def get_base_rates(conn, tax_base_id: int) -> list[TaxBand]:
    rows = conn.execute(
        "SELECT from_amount, to_amount, rate FROM tax_base_rates WHERE tax_base_id = ? ORDER BY from_amount",
        (tax_base_id,),
    ).fetchall()
    return [TaxBand(r["from_amount"], r["to_amount"], r["rate"]) for r in rows]


def get_tax_definitions(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM tax_definitions ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def get_confirmed_tax_map(conn) -> dict[tuple[int, int], dict]:
    """Map ``(transaction_id, tax_definition_id)`` → confirmed row (profile-scoped)."""
    rows = conn.execute(
        "SELECT transaction_id, tax_definition_id, tax_amount, currency FROM transaction_taxes"
        " WHERE tax_definition_id IS NOT NULL" + queries._profile_clause(conn),
        queries._profile_params(conn),
    ).fetchall()
    return {(r["transaction_id"], r["tax_definition_id"]): dict(r) for r in rows}


def apply_progressive(range_start: float, range_end: float, bands: list[TaxBand]) -> float:
    """Walk ascending brackets and tax the portion of ``[range_start, range_end)`` in each band."""
    if range_end <= range_start or not bands:
        return 0.0
    tax = 0.0
    for band in sorted(bands, key=lambda b: b.from_amount):
        lo = max(range_start, band.from_amount)
        hi = band.to_amount if band.to_amount is not None else float("inf")
        hi = min(range_end, hi)
        if hi > lo:
            tax += (hi - lo) * band.rate
    return round(tax, 4)


def _withholding(confirmed_generic: float, total_tax: float) -> float:
    """Year-level withholding (§17.9/decision 8)."""
    return max(0.0, total_tax - min(confirmed_generic, total_tax))


def compute_fiscal_year(
    items: list[dict],
    base: dict | None,
    categories: list[str],
    bands: list[TaxBand],
    definitions: list[dict],
    confirmed: dict[tuple[int, int], dict],
    convert: Convert,
    display_currency: str,
) -> FiscalYearTaxResult:
    """Compute tax for one fiscal year bucket.

    *items* are the bucket's ``TaxablePnlItem``-shaped dicts (category,
    timestamp, taxable_amount, native_amount, fiscal_rule, currency).
    *base* is the resolved ``tax_bases`` row or None (graceful zeros).
    """
    per_item: dict[int, ItemTaxResult] = {}

    def _resolve_item_taxes(item: dict) -> list[TaxDefinitionResult]:
        out: list[TaxDefinitionResult] = []
        for d in definitions:
            rate = d.get("rate")
            applies = (
                rate is not None
                and rate > 0
                and (d.get("ruleset_key") is None or d["ruleset_key"] == item["fiscal_rule"])
            )
            confirmed_row = confirmed.get((item["transaction_id"], d["id"]))
            confirmed_amt = confirmed_row["tax_amount"] if confirmed_row else None
            if not applies and confirmed_amt is None:
                continue
            computed = round(rate * item["native_amount"], 4) if applies else 0.0
            out.append(
                TaxDefinitionResult(
                    tax_definition_id=d["id"],
                    slug=d["slug"],
                    name=d["name"],
                    computed=computed,
                    confirmed=confirmed_amt,
                )
            )
        return out

    # Per-definition resolution is independent of the base (§17.11/§17.12):
    # a confirmed row on a naive definition is meaningful even when the year
    # has no configured tax_bases row. Resolve it once for every item, then
    # let the base branch fill in the bracket-attributed core tax.
    confirmed_by_cat: dict[str, float] = {}
    for item in items:
        taxes = _resolve_item_taxes(item)
        per_item[item["transaction_id"]] = ItemTaxResult(
            transaction_id=item["transaction_id"],
            category=item["category"],
            tax_owed=0.0,
            taxes=taxes,
        )
        for t in taxes:
            if t.confirmed is None:
                continue
            crate = confirmed.get((item["transaction_id"], t.tax_definition_id))
            currency = crate["currency"] if crate else item["currency"]
            converted = convert(t.confirmed, currency, item["timestamp"])
            confirmed_by_cat[item["category"]] = round(confirmed_by_cat.get(item["category"], 0.0) + converted, 4)
    total_confirmed = round(sum(confirmed_by_cat.values()), 4)

    if base is None:
        return FiscalYearTaxResult(
            tax_owed={},
            base=0.0,
            total_tax=0.0,
            withholding=0.0,
            total_tax_owed=0.0,
            combined_base=None,
            confirmed=confirmed_by_cat,
            total_confirmed=total_confirmed,
            per_item=[per_item[i["transaction_id"]] for i in items],
        )

    computation = base["computation"]
    flat_rate = base.get("flat_rate")
    in_base = [i for i in items if i["category"] in categories]
    base_total = round(sum(i["taxable_amount"] for i in in_base), 4)

    if computation == "progressive":
        running_total = 0.0
        for item in sorted(in_base, key=lambda i: i["timestamp"]):
            item_tax = apply_progressive(running_total, running_total + item["taxable_amount"], bands)
            running_total += item["taxable_amount"]
            per_item[item["transaction_id"]] = ItemTaxResult(
                transaction_id=item["transaction_id"],
                category=item["category"],
                tax_owed=item_tax,
                taxes=per_item[item["transaction_id"]].taxes,
            )
        tax_owed: dict[str, float] = {}
        for tid in (i["transaction_id"] for i in in_base):
            entry = per_item[tid]
            tax_owed[entry.category] = round(tax_owed.get(entry.category, 0.0) + entry.tax_owed, 4)
        total_tax = round(sum(tax_owed.values()), 4)

        # Year-level withholding (decision 8): confirmed amounts on generic
        # (ruleset_key IS NULL) definitions for transactions whose fiscal_rule
        # resolves to this base's ruleset, converted to display_currency.
        generic_confirmed = 0.0
        for item in in_base:
            if item.get("fiscal_rule") != base["ruleset_key"]:
                continue
            for d in definitions:
                if d.get("ruleset_key") is not None:
                    continue
                crate = confirmed.get((item["transaction_id"], d["id"]))
                if crate:
                    generic_confirmed += convert(crate["tax_amount"], crate["currency"], item["timestamp"])
        withholding = round(min(generic_confirmed, total_tax), 4)
        total_tax_owed = round(max(0.0, total_tax - withholding), 4)
        combined_base = base_total
    else:
        tax_owed = {}
        for i in in_base:
            per_item[i["transaction_id"]] = ItemTaxResult(
                transaction_id=i["transaction_id"],
                category=i["category"],
                tax_owed=round(i["taxable_amount"] * flat_rate, 4) if flat_rate else 0.0,
                taxes=per_item[i["transaction_id"]].taxes,
            )
        for tid in (i["transaction_id"] for i in in_base):
            entry = per_item[tid]
            tax_owed[entry.category] = round(tax_owed.get(entry.category, 0.0) + entry.tax_owed, 4)
        total_tax = round(sum(tax_owed.values()), 4)
        withholding = 0.0
        total_tax_owed = total_tax
        combined_base = None

    items_out = []
    for i in items:
        items_out.append(per_item.get(i["transaction_id"], ItemTaxResult(i["transaction_id"], i["category"], 0.0)))

    return FiscalYearTaxResult(
        tax_owed=tax_owed,
        base=base_total,
        total_tax=total_tax,
        withholding=withholding,
        total_tax_owed=total_tax_owed,
        combined_base=combined_base,
        confirmed=confirmed_by_cat,
        total_confirmed=total_confirmed,
        per_item=items_out,
    )
