from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.models.auth import PasswordResetToken, RefreshToken, User


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(func.lower(User.email) == email.lower()))


def get_user_by_id(session: Session, user_id: UUID) -> User | None:
    return session.get(User, user_id)


def list_users(
    session: Session, *, page: int, page_size: int, sort_by: str = "created_at", sort_order: str = "desc"
) -> tuple[list[User], int]:
    total = session.scalar(select(func.count()).select_from(User)) or 0
    sort_columns = {"created_at": User.created_at, "updated_at": User.updated_at, "email": User.email}
    order_column = sort_columns[sort_by]
    ordering = order_column.asc() if sort_order == "asc" else order_column.desc()
    users = list(
        session.scalars(
            select(User).order_by(ordering, User.id.asc()).offset((page - 1) * page_size).limit(page_size)
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


def get_password_reset_token(session: Session, token_hash: str, *, lock: bool = False) -> PasswordResetToken | None:
    statement = select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    if lock:
        statement = statement.with_for_update()
    return session.scalar(statement)


def revoke_refresh_tokens_for_user(session: Session, user_id: UUID, revoked_at: datetime) -> None:
    for token in session.scalars(
        select(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
    ):
        token.revoked_at = revoked_at
