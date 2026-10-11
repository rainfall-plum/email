import re

from sqlalchemy import case, desc, func, nullslast, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config.logging import get_logger
from app.config.settings import Settings
from app.models import Email, Mailbox, MailGenerationRecord, Tag
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


MAILBOX_SORTS = {
    "created_desc", "created_asc", "latest_email_desc", "oldest_email_asc",
    "email_asc", "email_desc", "unread_desc",
}


def list_mailboxes(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    tag_ids: list[int] | None = None,
    tag_mode: str = "any",
    untagged: bool = False,
    sort_by: str = "created_desc",
) -> tuple[list[Mailbox], int, dict[int, tuple[int, int, object | None]]]:
    if sort_by not in MAILBOX_SORTS:
        raise MailboxServiceError("不支持的邮箱排序方式")
    if tag_mode not in {"any", "all"}:
        raise MailboxServiceError("不支持的标签匹配方式")

    query = select(Mailbox).options(selectinload(Mailbox.tags))
    normalized_tags = list(dict.fromkeys(tag_ids or []))
    if untagged:
        query = query.where(~Mailbox.tags.any())
    elif normalized_tags:
        if tag_mode == "any":
            query = query.where(Mailbox.tags.any(Tag.id.in_(normalized_tags)))
        else:
            for tag_id in normalized_tags:
                query = query.where(Mailbox.tags.any(Tag.id == tag_id))

    latest_email = select(func.max(Email.received_at)).where(Email.mailbox_id == Mailbox.id).scalar_subquery()
    oldest_email = select(func.min(Email.received_at)).where(Email.mailbox_id == Mailbox.id).scalar_subquery()
    unread_count = select(func.count(Email.id)).where(
        Email.mailbox_id == Mailbox.id, Email.is_read.is_(False)
    ).scalar_subquery()
    if sort_by == "created_desc":
        query = query.order_by(desc(Mailbox.created_at), desc(Mailbox.id))
    elif sort_by == "created_asc":
        query = query.order_by(Mailbox.created_at, Mailbox.id)
    elif sort_by == "latest_email_desc":
        query = query.order_by(nullslast(desc(latest_email)), desc(Mailbox.id))
    elif sort_by == "oldest_email_asc":
        query = query.order_by(nullslast(oldest_email), Mailbox.id)
    elif sort_by == "email_asc":
        query = query.order_by(Mailbox.email_address, Mailbox.id)
    elif sort_by == "email_desc":
        query = query.order_by(desc(Mailbox.email_address), desc(Mailbox.id))
    else:
        query = query.order_by(desc(unread_count), desc(Mailbox.id))

    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    rows = list(db.scalars(query.offset((page - 1) * page_size).limit(page_size)))
    if not rows:
        return [], total, {}
    ids = [mailbox.id for mailbox in rows]
    metric_rows = db.execute(
        select(
            Email.mailbox_id,
            func.count(Email.id),
            func.sum(case((Email.is_read.is_(False), 1), else_=0)),
            func.max(Email.received_at),
        ).where(Email.mailbox_id.in_(ids)).group_by(Email.mailbox_id)
    )
    metrics = {
        mailbox_id: (int(email_count), int(unread or 0), latest)
        for mailbox_id, email_count, unread, latest in metric_rows
    }
    return rows, total, metrics


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
