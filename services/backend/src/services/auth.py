from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from src.config import get_settings
from src.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    verify_password,
)
from src.models.auth import PasswordResetToken, RefreshToken, User
from src.repositories import auth as auth_repository


class AuthenticationError(Exception):
    pass


class PasswordResetError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _new_refresh_token(user_id: UUID) -> tuple[str, RefreshToken]:
    settings = get_settings()
    raw_token = generate_opaque_token()
    token = RefreshToken(
        user_id=user_id,
        token_hash=hash_opaque_token(raw_token),
        expires_at=_now() + timedelta(days=settings.refresh_token_ttl_days),
    )
    return raw_token, token


def _token_response(user: User, refresh_token: str) -> dict[str, str | int]:
    access_token, expires_in = create_access_token(user_id=user.id, role=user.role)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": expires_in,
    }


def authenticate(session: Session, *, email: str, password: str) -> tuple[User, dict[str, str | int]]:
    user = auth_repository.get_user_by_email(session, email)
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise AuthenticationError

    raw_refresh_token, refresh_token = _new_refresh_token(user.id)
    auth_repository.create_refresh_token(session, refresh_token)
    session.commit()
    return user, _token_response(user, raw_refresh_token)


def refresh_session(session: Session, *, raw_refresh_token: str) -> tuple[User, dict[str, str | int]]:
    token = auth_repository.get_refresh_token(session, hash_opaque_token(raw_refresh_token), lock=True)
    now = _now()
    if token is None or token.revoked_at is not None or token.expires_at <= now:
        session.rollback()
        raise AuthenticationError

    user = auth_repository.get_user_by_id(session, token.user_id)
    if user is None or not user.is_active:
        token.revoked_at = now
        session.commit()
        raise AuthenticationError

    token.revoked_at = now
    token.last_used_at = now
    next_raw_token, next_token = _new_refresh_token(user.id)
    auth_repository.create_refresh_token(session, next_token)
    session.commit()
    return user, _token_response(user, next_raw_token)


def logout(session: Session, *, user_id: UUID, raw_refresh_token: str) -> None:
    token = auth_repository.get_refresh_token(session, hash_opaque_token(raw_refresh_token), lock=True)
    now = _now()
    if token is None or token.user_id != user_id or token.revoked_at is not None:
        session.rollback()
        raise AuthenticationError
    token.revoked_at = now
    session.commit()


def create_password_reset(session: Session, *, email: str) -> str | None:
    """Create the opaque token; its delivery belongs to a future notification adapter."""
    user = auth_repository.get_user_by_email(session, email)
    if user is None or not user.is_active:
        return None
    raw_token = generate_opaque_token()
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_opaque_token(raw_token),
            expires_at=_now() + timedelta(hours=1),
        )
    )
    session.commit()
    return raw_token


def reset_password(session: Session, *, raw_token: str, new_password: str) -> User:
    reset_token = auth_repository.get_password_reset_token(session, hash_opaque_token(raw_token), lock=True)
    now = _now()
    if reset_token is None or reset_token.used_at is not None or reset_token.expires_at <= now:
        session.rollback()
        raise PasswordResetError
    user = auth_repository.get_user_by_id(session, reset_token.user_id)
    if user is None or not user.is_active:
        session.rollback()
        raise PasswordResetError

    user.password_hash = hash_password(new_password)
    user.updated_at = now
    reset_token.used_at = now
    auth_repository.revoke_refresh_tokens_for_user(session, user.id, now)
    session.commit()
    return user


def change_password(session: Session, *, user: User, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.password_hash):
        raise AuthenticationError
    now = _now()
    user.password_hash = hash_password(new_password)
    user.updated_at = now
    auth_repository.revoke_refresh_tokens_for_user(session, user.id, now)
    session.commit()
