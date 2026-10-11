from app.database.base import Base
from app.models.admin_user import AdminUser
from app.models.attachment import Attachment
from app.models.email import Email
from app.models.mail_generation_record import MailGenerationRecord
from app.models.mailbox import Mailbox, mailbox_tags
from app.models.system_setting import SystemSetting
from app.models.tag import Tag

__all__ = [
    "AdminUser",
    "Attachment",
    "Base",
    "Email",
    "MailGenerationRecord",
    "Mailbox",
    "SystemSetting",
    "Tag",
    "mailbox_tags",
]
