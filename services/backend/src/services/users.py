from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from src.core.roles import Role
from src.core.security import hash_password
from src.models.auth import User
from src.repositories import auth as auth_repository
from src.schemas.users import CurrentUserUpdate, UserCreate, UserUpdate


class UserNotFoundError(Exception):
    pass


class UserConflictError(Exception):
    pass


class UserOperationError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _normalise_email(email: str) -> str:
    return email.strip().lower()


def list_users(session: Session, *, page: int, page_size: int) -> tuple[list[User], int]:
    return auth_repository.list_users(session, page=page, page_size=page_size)


def get_user(session: Session, user_id: UUID) -> User:
    user = auth_repository.get_user_by_id(session, user_id)
    if user is None:
        raise UserNotFoundError
    return user


def create_user(session: Session, payload: UserCreate) -> User:
    email = _normalise_email(payload.email)
    if auth_repository.get_user_by_email(session, email) is not None:
        raise UserConflictError
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        role=payload.role.value,
        is_active=True,
    )
    auth_repository.create_user(session, user)
    session.commit()
    session.refresh(user)
    return user


def update_user(session: Session, *, actor: User, user_id: UUID, payload: UserUpdate) -> tuple[User, bool, bool]:
    user = get_user(session, user_id)
    updates = payload.model_dump(exclude_unset=True)
    if user.id == actor.id and ("role" in updates or "is_active" in updates):
        raise UserOperationError("Administrators cannot change their own role or active status.")

    if "email" in updates:
        email = _normalise_email(updates["email"])
        matching_user = auth_repository.get_user_by_email(session, email)
        if matching_user is not None and matching_user.id != user.id:
            raise UserConflictError
        user.email = email
    if "first_name" in updates:
        user.first_name = updates["first_name"].strip()
    if "last_name" in updates:
        user.last_name = updates["last_name"].strip()

    role_changed = "role" in updates and updates["role"] != Role(user.role)
    deactivated = "is_active" in updates and not updates["is_active"] and user.is_active
    if "role" in updates:
        user.role = updates["role"].value
    if "is_active" in updates:
        user.is_active = updates["is_active"]
    user.updated_at = _now()
    session.commit()
    session.refresh(user)
    return user, role_changed, deactivated


def update_current_user(session: Session, *, user: User, payload: CurrentUserUpdate) -> User:
    updates = payload.model_dump(exclude_unset=True)
    if "email" in updates:
        email = _normalise_email(updates["email"])
        matching_user = auth_repository.get_user_by_email(session, email)
        if matching_user is not None and matching_user.id != user.id:
            raise UserConflictError
        user.email = email
    if "first_name" in updates:
        user.first_name = updates["first_name"].strip()
    if "last_name" in updates:
        user.last_name = updates["last_name"].strip()
    user.updated_at = _now()
    session.commit()
    session.refresh(user)
    return user
