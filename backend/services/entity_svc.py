from db.connection import get_db
from db import queries
from models import EntityCreate, EntityResponse
from models.enums import EntityType


class EntityError(Exception):
    pass


class EntityNotFound(EntityError):
    pass


class EntityAlreadyExists(EntityError):
    pass


class EntityHasDependents(EntityError):
    pass


def create(body: EntityCreate) -> EntityResponse:
    conn = get_db()
    if queries.entity_exists(conn, body.name, body.entity_type):
        raise EntityAlreadyExists(
            f"Entity '{body.name}' of type '{body.entity_type.value}' already exists"
        )
    entity_id = queries.create_entity(
        conn, body.name, body.entity_type, body.country, body.description
    )
    conn.commit()
    return EntityResponse(
        id=entity_id,
        name=body.name,
        entity_type=body.entity_type,
        country=body.country,
        description=body.description,
    )


def get(entity_id: int) -> EntityResponse:
    conn = get_db()
    row = queries.get_entity(conn, entity_id)
    if row is None:
        raise EntityNotFound(f"Entity {entity_id} not found")
    return EntityResponse(
        id=row["id"],
        name=row["name"],
        entity_type=EntityType(row["entity_type"]),
        country=row["country"],
        description=row["description"],
    )


def list_all() -> list[EntityResponse]:
    conn = get_db()
    rows = queries.get_all_entities(conn)
    return [
        EntityResponse(
            id=r["id"],
            name=r["name"],
            entity_type=EntityType(r["entity_type"]),
            country=r["country"],
            description=r["description"],
        )
        for r in rows
    ]


def update(entity_id: int, body: EntityCreate) -> EntityResponse:
    conn = get_db()
    existing = queries.get_entity(conn, entity_id)
    if existing is None:
        raise EntityNotFound(f"Entity {entity_id} not found")
    # Check duplicate only if name or type changed
    if body.name != existing["name"] or body.entity_type.value != existing["entity_type"]:
        if queries.entity_exists(conn, body.name, body.entity_type):
            raise EntityAlreadyExists(
                f"Entity '{body.name}' of type '{body.entity_type.value}' already exists"
            )
    queries.update_entity(conn, entity_id, body.name, body.entity_type, body.country, body.description)
    conn.commit()
    return EntityResponse(
        id=entity_id,
        name=body.name,
        entity_type=body.entity_type,
        country=body.country,
        description=body.description,
    )


def delete(entity_id: int) -> None:
    conn = get_db()
    existing = queries.get_entity(conn, entity_id)
    if existing is None:
        raise EntityNotFound(f"Entity {entity_id} not found")
    if queries.entity_has_dependents(conn, entity_id):
        raise EntityHasDependents(
            f"Entity {entity_id} has transactions or balance snapshots referencing it"
        )
    queries.delete_entity(conn, entity_id)
    conn.commit()


def has_assets(entity_id: int) -> bool:
    conn = get_db()
    return queries.entity_has_assets(conn, entity_id)


def get_dependents(entity_id: int) -> dict:
    conn = get_db()
    existing = queries.get_entity(conn, entity_id)
    if existing is None:
        raise EntityNotFound(f"Entity {entity_id} not found")
    return queries.get_entity_dependents(conn, entity_id)
