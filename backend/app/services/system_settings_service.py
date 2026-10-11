from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.config.settings import Settings
from app.models import SystemSetting

settings_logger = get_logger("settings")

SETTING_DEFINITIONS = {
    "allowed_domain": {"label": "邮件域名", "editable": False, "requires_restart": True},
    "max_emails_per_mailbox": {
        "label": "每个邮箱最多保留邮件数",
        "editable": True,
        "requires_restart": False,
    },
    "access_token_expire_minutes": {
        "label": "登录令牌有效期（分钟）",
        "editable": False,
        "requires_restart": True,
    },
    "environment": {"label": "运行环境", "editable": False, "requires_restart": True},
}


def _default_values(settings: Settings) -> dict[str, str]:
    return {
        "allowed_domain": settings.allowed_domain,
        "max_emails_per_mailbox": str(settings.max_emails_per_mailbox),
        "access_token_expire_minutes": str(settings.access_token_expire_minutes),
        "environment": settings.environment,
    }


def list_system_settings(db: Session, settings: Settings) -> list[dict]:
    stored = {
        item.key: item.value
        for item in db.scalars(
            select(SystemSetting).where(SystemSetting.key.in_(SETTING_DEFINITIONS))
        )
    }
    defaults = _default_values(settings)
    return [
        {
            "key": key,
            "label": definition["label"],
            "value": stored.get(key) or defaults[key],
            "editable": definition["editable"],
            "requires_restart": definition["requires_restart"],
        }
        for key, definition in SETTING_DEFINITIONS.items()
    ]


def get_effective_max_emails(db: Session, settings: Settings) -> int:
    stored = db.scalar(
        select(SystemSetting.value).where(SystemSetting.key == "max_emails_per_mailbox")
    )
    try:
        value = int(stored) if stored is not None else settings.max_emails_per_mailbox
    except (TypeError, ValueError):
        settings_logger.error("Invalid stored max_emails_per_mailbox value", exc_info=True)
        return settings.max_emails_per_mailbox
    return value if 1 <= value <= 100 else settings.max_emails_per_mailbox


def update_system_setting(db: Session, key: str, value: str) -> SystemSetting:
    definition = SETTING_DEFINITIONS.get(key)
    if definition is None:
        raise ValueError("不支持修改此配置")
    if not definition["editable"]:
        raise ValueError("此配置仅支持查看")
    if key == "max_emails_per_mailbox":
        try:
            parsed = int(value)
        except ValueError as exc:
            raise ValueError("邮件保留数量必须是整数") from exc
        if not 1 <= parsed <= 100:
            raise ValueError("邮件保留数量必须在 1 到 100 之间")
        value = str(parsed)
    item = db.scalar(select(SystemSetting).where(SystemSetting.key == key))
    if item is None:
        item = SystemSetting(key=key, value=value)
        db.add(item)
    else:
        item.value = value
    db.commit()
    db.refresh(item)
    settings_logger.info("System setting updated key=%s", key)
    return item
