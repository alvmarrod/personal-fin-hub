from fastapi import APIRouter, HTTPException

from models import ProfileCreate, ProfileRename, ProfileResponse, ProfileUnlock
from services.profile_svc import (
    InvalidPassword,
    InvalidProfileName,
    LastProfileError,
    ProfileNameTaken,
    ProfileNotFound,
    create,
    delete,
    get,
    list_profiles,
    rename,
    unlock,
)

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("", response_model=list[ProfileResponse])
async def list_profiles_route():
    return list_profiles()


@router.post("", response_model=ProfileResponse, status_code=201)
async def create_profile(body: ProfileCreate):
    try:
        return create(body)
    except (ProfileNameTaken, InvalidProfileName) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.get("/{profile_id}", response_model=ProfileResponse)
async def get_profile(profile_id: int):
    try:
        return get(profile_id)
    except ProfileNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch("/{profile_id}", response_model=ProfileResponse)
async def rename_profile(profile_id: int, body: ProfileRename):
    try:
        return rename(profile_id, body.name)
    except ProfileNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (ProfileNameTaken, InvalidProfileName) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/{profile_id}/unlock", response_model=ProfileResponse)
async def unlock_profile(profile_id: int, body: ProfileUnlock):
    try:
        return unlock(profile_id, body.password)
    except ProfileNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except InvalidPassword as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(profile_id: int):
    try:
        delete(profile_id)
    except ProfileNotFound as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except LastProfileError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
