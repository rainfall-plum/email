from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.database.session import get_db
from app.models import AdminUser
from app.schemas.auth import AdminResponse, LoginRequest, TokenResponse
from app.utils.security import create_access_token, decode_access_token, verify_password

router = APIRouter(prefix="/api", tags=["auth"])
security = HTTPBearer(auto_error=False)
auth_logger = get_logger("auth")


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(AdminUser).where(AdminUser.username == payload.username))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        auth_logger.warning("Login failed username=%s", payload.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(str(user.id), user.username)
    auth_logger.info("Admin login username=%s", user.username)
    return TokenResponse(access_token=token)


def get_current_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Session = Depends(get_db),
) -> AdminUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        auth_logger.warning("Invalid access token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已失效，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    user = db.get(AdminUser, user_id)
    if user is None or not user.is_active:
        auth_logger.warning("Inactive or missing admin user id=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已失效，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@router.get("/me", response_model=AdminResponse)
def current_admin(admin: AdminUser = Depends(get_current_admin)) -> AdminResponse:
    return AdminResponse(id=admin.id, username=admin.username)
