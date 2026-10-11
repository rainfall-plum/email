import re

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.config.settings import Settings
from app.models import Mailbox, MailGenerationRecord, Tag
from app.utils.name_library import NameLibrary, NameLibraryError

mailbox_logger = get_logger("mailbox")
LOCAL_PART_PATTERN = re.compile(r"^[a-z0-9]+$")


class MailboxServiceError(Exception):
    pass


def _validate_tags(db: Session, tag_ids: list[int]) -> list[Tag]:
    if not tag_ids:
        return []
    unique_ids = list(dict.fromkeys(tag_ids))
    tags = list(db.scalars(select(Tag).where(Tag.id.in_(unique_ids))))
    if len(tags) != len(unique_ids):
        raise MailboxServiceError("存在无效标签")
    return tags


def _email_address(local_part: str, settings: Settings) -> str:
    return f"{local_part}@{settings.allowed_domain}"


def create_mailbox(
    db: Session,
    settings: Settings,
    local_part: str,
    display_name: str | None = None,
    expires_at=None,
    tag_ids: list[int] | None = None,
    created_source: str = "manual",
) -> Mailbox:
    if not LOCAL_PART_PATTERN.fullmatch(local_part):
        raise MailboxServiceError("邮箱前缀只允许小写字母和数字")
    tags = _validate_tags(db, tag_ids or [])
    mailbox = Mailbox(
        email_address=_email_address(local_part, settings),
        local_part=local_part,
        display_name=display_name,
        expires_at=expires_at,
        created_source=created_source,
        tags=tags,
    )
    db.add(mailbox)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        mailbox_logger.warning("Mailbox duplicate local_part=%s", local_part)
        raise MailboxServiceError("邮箱前缀已存在") from exc
    db.refresh(mailbox)
    mailbox_logger.info("Mailbox created email=%s source=%s", mailbox.email_address, created_source)
    return mailbox


def list_mailboxes(db: Session) -> list[Mailbox]:
    return list(db.scalars(select(Mailbox).order_by(Mailbox.id)))


def get_mailbox(db: Session, mailbox_id: int) -> Mailbox:
    mailbox = db.get(Mailbox, mailbox_id)
    if mailbox is None:
        raise MailboxServiceError("邮箱不存在")
    return mailbox


def update_mailbox(db: Session, mailbox: Mailbox, values: dict) -> Mailbox:
    if values.get("tag_ids") is not None:
        mailbox.tags = _validate_tags(db, values.pop("tag_ids"))
    for field, value in values.items():
        setattr(mailbox, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        mailbox_logger.error("Mailbox update failed id=%s", mailbox.id, exc_info=True)
        raise MailboxServiceError("邮箱更新失败") from exc
    db.refresh(mailbox)
    mailbox_logger.info("Mailbox updated id=%s", mailbox.id)
    return mailbox


def delete_mailbox(db: Session, mailbox: Mailbox) -> None:
    email_address = mailbox.email_address
    db.delete(mailbox)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        mailbox_logger.error("Mailbox delete failed email=%s", email_address, exc_info=True)
        raise MailboxServiceError("邮箱删除失败") from exc
    mailbox_logger.info("Mailbox deleted email=%s", email_address)


def generate_mailboxes(db: Session, settings: Settings, count: int, tag_ids: list[int]) -> list[Mailbox]:
    tags = _validate_tags(db, tag_ids)
    library = NameLibrary(settings.names_dir)
    generated: list[Mailbox] = []
    used_locals = {value.lower() for value in db.scalars(select(Mailbox.local_part))}
    try:
        pairs = library.reserve_pairs(count)
        for first, last in pairs:
            base = f"{first}{last}".lower()
            local_part = base
            suffix = 1
            while local_part in used_locals:
                local_part = f"{base}{suffix}"
                suffix += 1
            used_locals.add(local_part)
            generated.append(
                Mailbox(
                    email_address=_email_address(local_part, settings),
                    local_part=local_part,
                    display_name=f"{first.title()} {last.title()}",
                    created_source="batch",
                    tags=list(tags),
                )
            )
        db.add_all(generated)
        db.add(
            MailGenerationRecord(
                requested_count=count,
                generated_count=len(generated),
                source="batch",
            )
        )
        db.commit()
        library.consume_pairs(pairs)
    except NameLibraryError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        mailbox_logger.error("Batch mailbox generation failed", exc_info=True)
        raise MailboxServiceError("批量生成邮箱失败") from exc
    mailbox_logger.info("Mailboxes generated count=%s", len(generated))
    return generated
