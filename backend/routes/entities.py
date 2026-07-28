from fastapi import APIRouter, HTTPException

from models import EntityCreate, EntityDependentsResponse, EntityResponse
from services.entity_svc import (
    EntityAlreadyExists,
    EntityHasDependents,
    EntityNotFound,
    create,
    delete,
    get,
    get_dependents,
    list_all,
    update,
)

router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("", response_model=list[EntityResponse])
async def list_entities():
    return list_all()


@router.post("", response_model=EntityResponse, status_code=201)
async def create_entity(body: EntityCreate):
    try:
        return create(body)
    except EntityAlreadyExists as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.get("/{entity_id}", response_model=EntityResponse)
async def get_entity(entity_id: int):
    try:
        return get(entity_id)
    except EntityNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put("/{entity_id}", response_model=EntityResponse)
async def update_entity(entity_id: int, body: EntityCreate):
    try:
        return update(entity_id, body)
    except EntityNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except EntityAlreadyExists as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.delete("/{entity_id}", status_code=204)
async def delete_entity(entity_id: int):
    try:
        delete(entity_id)
    except EntityNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except EntityHasDependents as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.get("/{entity_id}/dependents", response_model=EntityDependentsResponse)
async def get_entity_dependents(entity_id: int):
    try:
        return get_dependents(entity_id)
    except EntityNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
