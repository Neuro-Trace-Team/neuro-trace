from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from src.core.roles import Role
from src.core.security import decode_access_token
from src.db.sessions import get_audit_db, get_auth_db
from src.models.auth import User
from src.repositories.auth import get_user_by_id
from src.services import audit as audit_service

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


def require_roles(*roles: Role):
    """Return a FastAPI dependency that permits only the supplied roles."""
    if not roles:
        raise ValueError("At least one role is required")
    permitted_roles = frozenset(roles)

    def role_dependency(
        request: Request,
        current_user: Annotated[User, Depends(get_current_user)],
        audit_db: Annotated[Session, Depends(get_audit_db)],
    ) -> User:
        if current_user.role not in permitted_roles:
            audit_service.log(
                audit_db,
                event_code="ACCESS_DENIED",
                user_id=current_user.id,
                resource_type="USER",
                resource_id=current_user.id,
                metadata={
                    "required_roles": sorted(role.value for role in permitted_roles),
                    "actual_role": current_user.role,
                    "path": request.url.path,
                },
                ip_address=request.client.host if request.client else None,
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user

    return role_dependency
