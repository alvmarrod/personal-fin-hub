from fastapi import APIRouter, HTTPException

from models import EntityCreate, EntityResponse
from services.entity_svc import (
    EntityAlreadyExists,
    EntityError,
    EntityHasDependents,
    EntityNotFound,
    create,
    list_all,
    get,
    update,
    delete,
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
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/{entity_id}", response_model=EntityResponse)
async def get_entity(entity_id: int):
    try:
        return get(entity_id)
    except EntityNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{entity_id}", response_model=EntityResponse)
async def update_entity(entity_id: int, body: EntityCreate):
    try:
        return update(entity_id, body)
    except EntityNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except EntityAlreadyExists as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/{entity_id}", status_code=204)
async def delete_entity(entity_id: int):
    try:
        delete(entity_id)
    except EntityNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except EntityHasDependents as e:
        raise HTTPException(status_code=409, detail=str(e))
