from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.api.deps import get_current_user
from src.db.sessions import get_audit_db, get_auth_db
from src.models.auth import User
from src.schemas.auth import (
    ChangePasswordRequest,
    CurrentUserResponse,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from src.services import audit as audit_service
from src.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["authentication"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    auth_db: Annotated[Session, Depends(get_auth_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
) -> dict[str, str | int]:
    try:
        user, tokens = auth_service.authenticate(auth_db, email=payload.email, password=payload.password)
    except auth_service.AuthenticationError:
        audit_service.log(
            audit_db,
            event_code="FAILED_LOGIN_ATTEMPT",
            metadata={"email": payload.email.lower()},
            ip_address=_client_ip(request),
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials") from None
    audit_service.log(
        audit_db,
        event_code="LOGIN",
        user_id=user.id,
        resource_type="USER",
        resource_id=user.id,
        ip_address=_client_ip(request),
    )
    return tokens


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    payload: RefreshRequest,
    auth_db: Annotated[Session, Depends(get_auth_db)],
) -> dict[str, str | int]:
    try:
        _, tokens = auth_service.refresh_session(auth_db, raw_refresh_token=payload.refresh_token)
        return tokens
    except auth_service.AuthenticationError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from None


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    payload: LogoutRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    auth_db: Annotated[Session, Depends(get_auth_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
) -> None:
    try:
        auth_service.logout(auth_db, user_id=current_user.id, raw_refresh_token=payload.refresh_token)
    except auth_service.AuthenticationError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from None
    audit_service.log(
        audit_db,
        event_code="LOGOUT",
        user_id=current_user.id,
        resource_type="USER",
        resource_id=current_user.id,
        ip_address=_client_ip(request),
    )


@router.get("/me", response_model=CurrentUserResponse)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
    payload: ForgotPasswordRequest,
    auth_db: Annotated[Session, Depends(get_auth_db)],
) -> dict[str, str]:
    auth_service.create_password_reset(auth_db, email=payload.email)
    # Deliberately generic to avoid exposing whether an e-mail is registered.
    # A future mail adapter will receive the raw token instead of this endpoint.
    return {"message": "If the account exists, password reset instructions will be sent."}


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    auth_db: Annotated[Session, Depends(get_auth_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
) -> None:
    try:
        user = auth_service.reset_password(auth_db, raw_token=payload.token, new_password=payload.new_password)
    except auth_service.PasswordResetError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token") from None
    audit_service.log(
        audit_db,
        event_code="PASSWORD_RESET",
        user_id=user.id,
        resource_type="USER",
        resource_id=user.id,
        ip_address=_client_ip(request),
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    auth_db: Annotated[Session, Depends(get_auth_db)],
    audit_db: Annotated[Session, Depends(get_audit_db)],
) -> None:
    try:
        auth_service.change_password(
            auth_db,
            user=current_user,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except auth_service.AuthenticationError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is invalid") from None
    audit_service.log(
        audit_db,
        event_code="PASSWORD_CHANGED",
        user_id=current_user.id,
        resource_type="USER",
        resource_id=current_user.id,
        ip_address=_client_ip(request),
    )
