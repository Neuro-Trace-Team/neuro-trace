from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from src.core.security import decode_access_token
from src.db.sessions import get_auth_db
from src.models.auth import User
from src.repositories.auth import get_user_by_id

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    auth_db: Annotated[Session, Depends(get_auth_db)],
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        if not isinstance(subject, str):
            raise credentials_error
        user_id = UUID(subject)
    except (jwt.InvalidTokenError, ValueError):
        raise credentials_error from None

    user = get_user_by_id(auth_db, user_id)
    if user is None or not user.is_active:
        raise credentials_error
    return user
