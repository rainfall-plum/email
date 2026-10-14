from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.database.session import get_db
from app.models import AdminUser
from app.schemas.auth import AdminResponse, CredentialsRequest, CredentialsResponse, LoginRequest, TokenResponse, VerifyPasswordRequest, VerifyPasswordResponse
from app.services.admin_service import CredentialsError, change_credentials
from app.utils.security import create_access_token, decode_access_token, verify_password

router = APIRouter(prefix="/api", tags=["auth"])
security = HTTPBearer(auto_error=False)
auth_logger = get_logger("auth")


def auth_failure(code: str = "AUTH_SESSION_REVOKED", message: str = "登录状态已失效，请重新登录") -> HTTPException:
    auth_logger.error("Authentication rejected code=%s", code)
    return HTTPException(status_code=401, detail={"code": code, "message": message}, headers={"WWW-Authenticate": "Bearer"})


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        user = db.scalar(select(AdminUser).where(AdminUser.username == payload.username))
        if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
            raise auth_failure("INVALID_CREDENTIALS", "用户名或密码错误")
        token = create_access_token(str(user.id), user.username, user.auth_version)
        auth_logger.info("Admin login admin_id=%s", user.id)
        return TokenResponse(access_token=token)
    except HTTPException:
        raise
    except Exception as exc:
        auth_logger.error("Login authentication failed exception_type=%s", type(exc).__name__)
        raise HTTPException(503, detail={"code": "AUTH_UNAVAILABLE", "message": "登录服务暂不可用，请稍后重试"}) from None


def get_current_admin(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Session = Depends(get_db),
) -> AdminUser:
    if credentials is None:
        raise auth_failure("AUTH_REQUIRED")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise auth_failure() from None
    try:
        # Refresh any existing session identity before checking revocation.
        user = db.get(AdminUser, user_id, populate_existing=True)
    except Exception as exc:
        auth_logger.error("Session validation failed exception_type=%s", type(exc).__name__)
        raise HTTPException(503, detail={"code": "AUTH_UNAVAILABLE", "message": "登录服务暂不可用，请稍后重试"}) from None
    if user is None or not user.is_active:
        raise auth_failure()
    if type(payload.get("auth_version")) is not int or payload["auth_version"] != user.auth_version:
        auth_logger.info("Revoked admin session rejected admin_id=%s", user_id)
        raise auth_failure()
    return user


@router.get("/me", response_model=AdminResponse)
@router.get("/admin/profile", response_model=AdminResponse)
def current_admin(admin: AdminUser = Depends(get_current_admin)) -> AdminResponse:
    return AdminResponse(id=admin.id, username=admin.username)


@router.post("/admin/verify-password", response_model=VerifyPasswordResponse)
def verify_admin_password(payload: VerifyPasswordRequest, admin: AdminUser = Depends(get_current_admin)) -> VerifyPasswordResponse:
    if not verify_password(payload.current_password, admin.password_hash):
        raise HTTPException(status_code=400, detail={"code": "CURRENT_PASSWORD_INCORRECT", "message": "当前密码错误"})
    return VerifyPasswordResponse()


@router.patch("/admin/credentials", response_model=CredentialsResponse)
def update_credentials(payload: CredentialsRequest, admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)) -> CredentialsResponse:
    try:
        change_credentials(db, admin, payload)
    except CredentialsError as exc:
        raise HTTPException(exc.status_code, detail={"code": exc.code, "message": exc.message}) from None
    return CredentialsResponse()
