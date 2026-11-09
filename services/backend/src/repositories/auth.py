from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.models.auth import RefreshToken, User


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(func.lower(User.email) == email.lower()))


def get_user_by_id(session: Session, user_id: UUID) -> User | None:
    return session.get(User, user_id)


def list_users(
    session: Session, *, page: int, page_size: int, query: str | None, user_id: UUID | None,
    email: str | None, first_name: str | None, last_name: str | None, role: str | None,
    is_active: bool | None, sort_by: str = "created_at", sort_order: str = "desc",
) -> tuple[list[User], int]:
    filters = []
    if query is not None:
        pattern = f"%{query}%"
        filters.append(or_(User.first_name.ilike(pattern), User.last_name.ilike(pattern), User.email.ilike(pattern)))
    if user_id is not None: filters.append(User.id == user_id)
    if email is not None: filters.append(func.lower(User.email) == email.lower())
    if first_name is not None: filters.append(User.first_name == first_name)
    if last_name is not None: filters.append(User.last_name == last_name)
    if role is not None: filters.append(User.role == role)
    if is_active is not None: filters.append(User.is_active == is_active)
    total = session.scalar(select(func.count()).select_from(User).where(*filters)) or 0
    sort_columns = {
        "id": User.id, "email": User.email, "first_name": User.first_name,
        "last_name": User.last_name, "role": User.role, "is_active": User.is_active,
        "created_at": User.created_at, "updated_at": User.updated_at,
    }
    order_column = sort_columns[sort_by]
    ordering = order_column.asc() if sort_order == "asc" else order_column.desc()
    users = list(
        session.scalars(
            select(User).where(*filters).order_by(ordering, User.id.asc()).offset((page - 1) * page_size).limit(page_size)
        )
    )
    return users, total


def create_user(session: Session, user: User) -> User:
    session.add(user)
    return user


def get_refresh_token(session: Session, token_hash: str, *, lock: bool = False) -> RefreshToken | None:
    statement = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    if lock:
        statement = statement.with_for_update()
    return session.scalar(statement)


def create_refresh_token(session: Session, token: RefreshToken) -> RefreshToken:
    session.add(token)
    return token


def revoke_refresh_tokens_for_user(session: Session, user_id: UUID, revoked_at: datetime) -> None:
    for token in session.scalars(
        select(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
    ):
        token.revoked_at = revoked_at
