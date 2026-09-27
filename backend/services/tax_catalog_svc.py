"""Tax catalog CRUD (§17.7-§17.8).

Manages the versioned tax data catalog that replaces the retired ``tax_rates``
table and hardcoded ``TaxModel`` classes:

  - ``tax_bases`` (+ nested ``tax_base_categories``/``tax_base_rates``)
  - ``tax_definitions`` (per-operation taxes/levies, stable ``slug``)
  - ``broker_fee_definitions`` (pure broker-fee catalog)

The catalog tables are global — they have no ``profile_id`` column. A
definition referenced by a ``transaction_taxes``/``transaction_fees`` row
cannot be deleted (would orphan the confirmed amount).
"""

import sqlite3

from db import queries
from db.connection import get_db
from models import (
    BrokerFeeDefinitionCreate,
    BrokerFeeDefinitionResponse,
    TaxBaseCreate,
    TaxBaseRate,
    TaxBaseResponse,
    TaxDefinitionCreate,
    TaxDefinitionResponse,
)


class TaxCatalogError(Exception):
    pass


class TaxBaseNotFound(TaxCatalogError):
    pass


class TaxDefinitionNotFound(TaxCatalogError):
    pass


class BrokerFeeDefinitionNotFound(TaxCatalogError):
    pass


class TaxDefinitionInUse(TaxCatalogError):
    pass


class BrokerFeeDefinitionInUse(TaxCatalogError):
    pass


class TaxDefinitionSlugTaken(TaxCatalogError):
    pass


def _base_response(row: dict, categories: list[str], rates: list[dict]) -> TaxBaseResponse:
    return TaxBaseResponse(
        id=row["id"],
        ruleset_key=row["ruleset_key"],
        name=row["name"],
        computation=row["computation"],
        flat_rate=row.get("flat_rate"),
        year_start=row.get("year_start"),
        categories=categories,
        rates=[TaxBaseRate(from_amount=r["from_amount"], to_amount=r["to_amount"], rate=r["rate"]) for r in rates],
    )


def _base_with_children(conn, row: dict) -> TaxBaseResponse:
    return _base_response(
        row, queries.get_tax_base_categories(conn, row["id"]), queries.get_tax_base_rates(conn, row["id"])
    )


def create_tax_base(body: TaxBaseCreate) -> TaxBaseResponse:
    conn = get_db()
    try:
        base_id = queries.create_tax_base(
            conn,
            ruleset_key=body.ruleset_key,
            name=body.name,
            computation=body.computation,
            flat_rate=body.flat_rate,
            year_start=body.year_start,
        )
        queries.replace_tax_base_categories(conn, base_id, list(body.categories))
        queries.replace_tax_base_rates(conn, base_id, [r.model_dump() for r in body.rates])
    except sqlite3.IntegrityError as e:
        raise TaxCatalogError(str(e)) from e
    conn.commit()
    row = queries.get_tax_base(conn, base_id)
    if row is None:
        raise TaxBaseNotFound(f"Tax base {base_id} not found after create")
    return _base_with_children(conn, row)


def get_tax_base(base_id: int) -> TaxBaseResponse:
    conn = get_db()
    row = queries.get_tax_base(conn, base_id)
    if row is None:
        raise TaxBaseNotFound(f"Tax base {base_id} not found")
    return _base_with_children(conn, row)


def list_tax_bases() -> list[TaxBaseResponse]:
    conn = get_db()
    return [_base_with_children(conn, row) for row in queries.get_all_tax_bases(conn)]


def update_tax_base(base_id: int, body: TaxBaseCreate) -> TaxBaseResponse:
    conn = get_db()
    if queries.get_tax_base(conn, base_id) is None:
        raise TaxBaseNotFound(f"Tax base {base_id} not found")
    try:
        queries.update_tax_base(
            conn,
            base_id,
            ruleset_key=body.ruleset_key,
            name=body.name,
            computation=body.computation,
            flat_rate=body.flat_rate,
            year_start=body.year_start,
        )
        queries.replace_tax_base_categories(conn, base_id, list(body.categories))
        queries.replace_tax_base_rates(conn, base_id, [r.model_dump() for r in body.rates])
    except sqlite3.IntegrityError as e:
        raise TaxCatalogError(str(e)) from e
    conn.commit()
    row = queries.get_tax_base(conn, base_id)
    if row is None:
        raise TaxBaseNotFound(f"Tax base {base_id} not found after update")
    return _base_with_children(conn, row)


def delete_tax_base(base_id: int) -> None:
    conn = get_db()
    if queries.get_tax_base(conn, base_id) is None:
        raise TaxBaseNotFound(f"Tax base {base_id} not found")
    queries.delete_tax_base(conn, base_id)
    conn.commit()


def create_tax_definition(body: TaxDefinitionCreate) -> TaxDefinitionResponse:
    conn = get_db()
    if queries.get_tax_definition_by_slug(conn, body.slug):
        raise TaxDefinitionSlugTaken(f"Tax definition slug '{body.slug}' already exists")
    try:
        definition_id = queries.create_tax_definition(
            conn,
            slug=body.slug,
            ruleset_key=body.ruleset_key,
            name=body.name,
            rate=body.rate,
            year_start=body.year_start,
        )
    except sqlite3.IntegrityError as e:
        raise TaxDefinitionSlugTaken(str(e)) from e
    conn.commit()
    row = queries.get_tax_definition(conn, definition_id)
    if row is None:
        raise TaxDefinitionNotFound(f"Tax definition {definition_id} not found after create")
    return TaxDefinitionResponse(**row)


def get_tax_definition(definition_id: int) -> TaxDefinitionResponse:
    conn = get_db()
    row = queries.get_tax_definition(conn, definition_id)
    if row is None:
        raise TaxDefinitionNotFound(f"Tax definition {definition_id} not found")
    return TaxDefinitionResponse(**row)


def list_tax_definitions() -> list[TaxDefinitionResponse]:
    conn = get_db()
    return [TaxDefinitionResponse(**row) for row in queries.get_all_tax_definitions(conn)]


def update_tax_definition(definition_id: int, body: TaxDefinitionCreate) -> TaxDefinitionResponse:
    conn = get_db()
    if queries.get_tax_definition(conn, definition_id) is None:
        raise TaxDefinitionNotFound(f"Tax definition {definition_id} not found")
    existing = queries.get_tax_definition_by_slug(conn, body.slug)
    if existing is not None and existing["id"] != definition_id:
        raise TaxDefinitionSlugTaken(f"Tax definition slug '{body.slug}' already exists")
    try:
        queries.update_tax_definition(
            conn,
            definition_id,
            slug=body.slug,
            ruleset_key=body.ruleset_key,
            name=body.name,
            rate=body.rate,
            year_start=body.year_start,
        )
    except sqlite3.IntegrityError as e:
        raise TaxDefinitionSlugTaken(str(e)) from e
    conn.commit()
    row = queries.get_tax_definition(conn, definition_id)
    if row is None:
        raise TaxDefinitionNotFound(f"Tax definition {definition_id} not found after update")
    return TaxDefinitionResponse(**row)


def delete_tax_definition(definition_id: int) -> None:
    conn = get_db()
    if queries.get_tax_definition(conn, definition_id) is None:
        raise TaxDefinitionNotFound(f"Tax definition {definition_id} not found")
    if queries.count_transaction_taxes_for_definition(conn, definition_id) > 0:
        raise TaxDefinitionInUse(f"Tax definition {definition_id} is referenced by confirmed transaction taxes")
    queries.delete_tax_definition(conn, definition_id)
    conn.commit()


def create_broker_fee_definition(body: BrokerFeeDefinitionCreate) -> BrokerFeeDefinitionResponse:
    conn = get_db()
    definition_id = queries.create_broker_fee_definition(conn, name=body.name)
    conn.commit()
    row = queries.get_broker_fee_definition(conn, definition_id)
    if row is None:
        raise BrokerFeeDefinitionNotFound(f"Broker fee definition {definition_id} not found after create")
    return BrokerFeeDefinitionResponse(**row)


def get_broker_fee_definition(definition_id: int) -> BrokerFeeDefinitionResponse:
    conn = get_db()
    row = queries.get_broker_fee_definition(conn, definition_id)
    if row is None:
        raise BrokerFeeDefinitionNotFound(f"Broker fee definition {definition_id} not found")
    return BrokerFeeDefinitionResponse(**row)


def list_broker_fee_definitions() -> list[BrokerFeeDefinitionResponse]:
    conn = get_db()
    return [BrokerFeeDefinitionResponse(**row) for row in queries.get_all_broker_fee_definitions(conn)]


def update_broker_fee_definition(definition_id: int, body: BrokerFeeDefinitionCreate) -> BrokerFeeDefinitionResponse:
    conn = get_db()
    if queries.get_broker_fee_definition(conn, definition_id) is None:
        raise BrokerFeeDefinitionNotFound(f"Broker fee definition {definition_id} not found")
    queries.update_broker_fee_definition(conn, definition_id, name=body.name)
    conn.commit()
    row = queries.get_broker_fee_definition(conn, definition_id)
    if row is None:
        raise BrokerFeeDefinitionNotFound(f"Broker fee definition {definition_id} not found after update")
    return BrokerFeeDefinitionResponse(**row)


def delete_broker_fee_definition(definition_id: int) -> None:
    conn = get_db()
    if queries.get_broker_fee_definition(conn, definition_id) is None:
        raise BrokerFeeDefinitionNotFound(f"Broker fee definition {definition_id} not found")
    if queries.count_transaction_fees_for_definition(conn, definition_id) > 0:
        raise BrokerFeeDefinitionInUse(f"Broker fee definition {definition_id} is referenced by transaction fees")
    queries.delete_broker_fee_definition(conn, definition_id)
    conn.commit()
