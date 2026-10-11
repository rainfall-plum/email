from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.config.settings import Settings
from app.models import AdminUser
from app.utils.security import hash_password

admin_logger = get_logger("admin")


def ensure_bootstrap_admin(db: Session, settings: Settings) -> AdminUser | None:
    """Create the first local admin only when both development values are configured."""
    if not settings.bootstrap_admin_username or not settings.bootstrap_admin_password:
        return None

    existing = db.scalar(
        select(AdminUser).where(AdminUser.username == settings.bootstrap_admin_username)
    )
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
