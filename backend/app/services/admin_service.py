from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.config.settings import Settings
from app.models import AdminUser
from app.schemas.auth import CredentialsRequest
from app.utils.security import hash_password, verify_password

admin_logger = get_logger("admin")


def ensure_bootstrap_admin(db: Session, settings: Settings) -> AdminUser | None:
    """Create the first local admin only when both development values are configured."""
    if not settings.bootstrap_admin_username or not settings.bootstrap_admin_password:
        return None

    # Bootstrap only an empty installation, never resurrect a renamed account.
    existing = db.scalar(select(AdminUser).order_by(AdminUser.id).limit(1))
    if existing is not None:
        return existing

    admin = AdminUser(
        username=settings.bootstrap_admin_username,
        password_hash=hash_password(settings.bootstrap_admin_password),
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    admin_logger.info("Bootstrap admin created username=%s", admin.username)
    return admin


class CredentialsError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(code)


def change_credentials(db: Session, admin: AdminUser, payload: CredentialsRequest) -> None:
    admin_id, previous_version = admin.id, admin.auth_version
    try:
        if not verify_password(payload.current_password, admin.password_hash):
            raise CredentialsError("CURRENT_PASSWORD_INCORRECT", "当前密码错误")
        username = payload.new_username if payload.new_username is not None else admin.username
        password_changed = payload.new_password is not None and not verify_password(payload.new_password, admin.password_hash)
        if username == admin.username and not password_changed:
            raise CredentialsError("NO_CREDENTIAL_CHANGES", "请提供与当前信息不同的新用户名或新密码")
        if db.scalar(select(AdminUser.id).where(AdminUser.username == username, AdminUser.id != admin_id)) is not None:
            raise CredentialsError("ADMIN_USERNAME_EXISTS", "管理员用户名已存在", 409)
        password_hash = admin.password_hash
        if password_changed:
            try:
                password_hash = hash_password(payload.new_password)
            except Exception as exc:
                admin_logger.error("Password hashing failed admin_id=%s exception_type=%s", admin_id, type(exc).__name__)
                raise CredentialsError("CREDENTIAL_UPDATE_FAILED", "管理员信息保存失败，请稍后重试", 500) from None
        result = db.execute(
            update(AdminUser)
            .where(AdminUser.id == admin_id, AdminUser.auth_version == previous_version, AdminUser.is_active.is_(True))
            .values(username=username, password_hash=password_hash, auth_version=AdminUser.auth_version + 1)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise CredentialsError("AUTH_SESSION_REVOKED", "登录状态已失效，请重新登录", 401)
        db.commit()
        admin_logger.info("Admin credentials changed admin_id=%s session_version=%s all_previous_sessions_revoked=true", admin_id, previous_version + 1)
    except CredentialsError as exc:
        db.rollback()
        admin_logger.error("Admin credentials change failed admin_id=%s code=%s", admin_id, exc.code)
        raise
    except IntegrityError:
        db.rollback()
        admin_logger.error("Admin credentials unique constraint failed admin_id=%s", admin_id)
        raise CredentialsError("ADMIN_USERNAME_EXISTS", "管理员用户名已存在", 409) from None
    except Exception as exc:
        db.rollback()
        admin_logger.error("Admin credentials transaction failed admin_id=%s exception_type=%s", admin_id, type(exc).__name__)
        raise CredentialsError("CREDENTIAL_UPDATE_FAILED", "管理员信息保存失败，请稍后重试", 500) from None
