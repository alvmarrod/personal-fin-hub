from fastapi import APIRouter, HTTPException

from models import BrokerFeeDefinitionCreate, BrokerFeeDefinitionResponse
from services.tax_catalog_svc import (
    BrokerFeeDefinitionInUse,
    BrokerFeeDefinitionNotFound,
    create_broker_fee_definition,
    delete_broker_fee_definition,
    get_broker_fee_definition,
    list_broker_fee_definitions,
    update_broker_fee_definition,
)

router = APIRouter(prefix="/broker-fee-definitions", tags=["broker-fee-definitions"])


@router.get("", response_model=list[BrokerFeeDefinitionResponse])
async def list_all():
    return list_broker_fee_definitions()


@router.post("", response_model=BrokerFeeDefinitionResponse, status_code=201)
async def create(body: BrokerFeeDefinitionCreate):
    return create_broker_fee_definition(body)


@router.get("/{definition_id}", response_model=BrokerFeeDefinitionResponse)
async def get(definition_id: int):
    try:
        return get_broker_fee_definition(definition_id)
    except BrokerFeeDefinitionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.put("/{definition_id}", response_model=BrokerFeeDefinitionResponse)
async def update(definition_id: int, body: BrokerFeeDefinitionCreate):
    try:
        return update_broker_fee_definition(definition_id, body)
    except BrokerFeeDefinitionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/{definition_id}", status_code=204)
async def delete(definition_id: int):
    try:
        delete_broker_fee_definition(definition_id)
    except BrokerFeeDefinitionNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except BrokerFeeDefinitionInUse as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
