from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, require_roles
from src.core.roles import Role
from src.db.sessions import get_audit_db, get_auth_db
from src.models.auth import User
from src.schemas.users import (
    CurrentUserUpdate,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserUpdate,
)
from src.services import audit as audit_service
from src.services import users as users_service

router = APIRouter(prefix="/users", tags=["users"])
admin_only = Depends(require_roles(Role.ADMIN))


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=UserListResponse, dependencies=[admin_only])
def list_users(
    auth_db: Annotated[Session, Depends(get_auth_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> UserListResponse:
    users, total = users_service.list_users(auth_db, page=page, page_size=page_size)
    return UserListResponse(items=users, page=page, page_size=page_size, total=total)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED, dependencies=[admin_only])
def create_user(
    payload: UserCreate,
    request: Request,
    actor: Annotated[User, Depends(get_current_user)],
    auth_db: Annotated[Session, Depends(get_auth_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
) -> User:
    try:
        user = users_service.create_user(auth_db, payload)
    except users_service.UserConflictError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail address is already in use") from None
    audit_service.log_event(
        audit_db,
        event_code="ACCOUNT_CREATED",
        user_id=actor.id,
        resource_type="USER",
        resource_id=user.id,
        metadata={"role": user.role},
        ip_address=_client_ip(request),
    )
    return user


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user


@router.patch("/me", response_model=UserResponse)
def update_current_user_profile(
    payload: CurrentUserUpdate,
    auth_db: Annotated[Session, Depends(get_auth_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    try:
        return users_service.update_current_user(auth_db, user=current_user, payload=payload)
    except users_service.UserConflictError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail address is already in use") from None


@router.get("/{user_id}", response_model=UserResponse, dependencies=[admin_only])
def get_user(user_id: UUID, auth_db: Annotated[Session, Depends(get_auth_db)]) -> User:
    try:
        return users_service.get_user(auth_db, user_id)
    except users_service.UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from None


@router.patch("/{user_id}", response_model=UserResponse, dependencies=[admin_only])
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    request: Request,
    actor: Annotated[User, Depends(get_current_user)],
    auth_db: Annotated[Session, Depends(get_auth_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
) -> User:
    try:
        user, role_changed, deactivated = users_service.update_user(
            auth_db, actor=actor, user_id=user_id, payload=payload
        )
    except users_service.UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from None
    except users_service.UserConflictError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail address is already in use") from None
    except users_service.UserOperationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from None

    if role_changed:
        audit_service.log_event(
            audit_db,
            event_code="ROLE_CHANGED",
            user_id=actor.id,
            resource_type="USER",
            resource_id=user.id,
            metadata={"new_role": user.role},
            ip_address=_client_ip(request),
        )
    if deactivated:
        audit_service.log_event(
            audit_db,
            event_code="ACCOUNT_DEACTIVATED",
            user_id=actor.id,
            resource_type="USER",
            resource_id=user.id,
            ip_address=_client_ip(request),
        )
    return user
