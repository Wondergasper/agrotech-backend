import json
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.database import get_session
from app.models import User
from app.schemas import (
    UserPublic, UpdateProfileRequest, UpdatePreferencesRequest,
    UpdateFarmRequest, UpdateRoleRequest,
)
from app.deps import get_current_user

router = APIRouter(prefix="/api/users", tags=["Users"])

VALID_ROLES = {"vendor", "consumer"}


def _to_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        name=user.name,
        email=user.email,
        phone=user.phone,
        role=user.role,
        avatar_url=user.avatar_url,
        farm_name=user.farm_name,
        farm_location=user.farm_location,
        farm_type=user.farm_type,
        budget=user.budget,
        health_tags=user.get_health_tags(),
        preferences=user.get_preferences(),
        created_at=user.created_at,
    )


@router.get("/me", response_model=UserPublic)
def get_me(current_user: User = Depends(get_current_user)):
    return _to_public(current_user)


@router.patch("/me", response_model=UserPublic)
def update_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if body.name is not None:
        current_user.name = body.name
    if body.phone is not None:
        current_user.phone = body.phone
    if body.avatar_url is not None:
        current_user.avatar_url = body.avatar_url
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return _to_public(current_user)


@router.patch("/me/preferences", response_model=UserPublic)
def update_preferences(
    body: UpdatePreferencesRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if body.budget is not None:
        current_user.budget = body.budget
    if body.health_tags is not None:
        current_user.set_health_tags(body.health_tags)
    if body.preferences is not None:
        current_user.set_preferences(body.preferences)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return _to_public(current_user)


@router.patch("/me/farm", response_model=UserPublic)
def update_farm(
    body: UpdateFarmRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if body.farm_name is not None:
        current_user.farm_name = body.farm_name
    if body.farm_location is not None:
        current_user.farm_location = body.farm_location
    if body.farm_type is not None:
        current_user.farm_type = body.farm_type
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return _to_public(current_user)


@router.patch("/me/role", response_model=UserPublic)
def update_role(
    body: UpdateRoleRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Set the user's role (vendor or consumer). Can only be set once per session."""
    if body.role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Role must be one of: {', '.join(VALID_ROLES)}",
        )
    current_user.role = body.role
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return _to_public(current_user)
