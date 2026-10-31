import secrets
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from src.config import get_settings

password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def generate_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def hash_opaque_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def create_access_token(*, user_id: UUID, role: str) -> tuple[str, int]:
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_ttl_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": expires_at,
    }
    return (
        jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm),
        settings.access_token_ttl_minutes * 60,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def decode_preprocessing_service_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.preprocessing_service_jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
    if (
        payload.get("service") != "preprocessing"
        or payload.get("token_type") != "service"
        or not isinstance(payload.get("exp"), (int, float))
    ):
        raise jwt.InvalidTokenError("Invalid preprocessing service token claims")
    return payload
