import os
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.config.settings import Settings
from app.models import Email, Mailbox
from app.services.code_service import extract_verification_code
from app.services.attachment_service import save_relevant_attachments
from app.services.parser_service import ParsedMail

mail_logger = get_logger("mail")


class MailReceiveError(Exception):
    pass


class MailboxNotFoundError(MailReceiveError):
    """Permanent SMTP rejection for an unknown or disabled mailbox."""


def _save_eml(raw_message: bytes, data_dir: Path) -> Path:
    eml_dir = data_dir / "eml"
    eml_dir.mkdir(parents=True, exist_ok=True)
    final_path = eml_dir / f"{uuid.uuid4().hex}.eml"
    temp_path = eml_dir / f".{final_path.name}.tmp"
    try:
        temp_path.write_bytes(raw_message)
        os.replace(temp_path, final_path)
        return final_path
    except OSError as exc:
        temp_path.unlink(missing_ok=True)
        mail_logger.error("EML file save failed path=%s", final_path, exc_info=True)
        raise MailReceiveError("邮件文件保存失败") from exc


def _find_mailbox(db: Session, receiver: str) -> Mailbox | None:
    return db.scalar(
        select(Mailbox).where(
            Mailbox.email_address == receiver.lower(),
            Mailbox.enabled.is_(True),
        )
    )


def _remove_stored_files(email: Email) -> None:
    if email.eml_path:
        Path(email.eml_path).unlink(missing_ok=True)
    for attachment in email.attachments:
        Path(attachment.file_path).unlink(missing_ok=True)


def _cleanup_mailbox(db: Session, mailbox: Mailbox, settings: Settings) -> None:
    emails = list(
        db.scalars(
            select(Email)
            .where(Email.mailbox_id == mailbox.id)
            .order_by(Email.received_at.desc(), Email.id.desc())
        )
    )
    for old_email in emails[settings.max_emails_per_mailbox :]:
        _remove_stored_files(old_email)
        db.delete(old_email)
        mail_logger.info(
            "Delete old mail mailbox=%s email_id=%s reason=mailbox_limit",
            mailbox.email_address,
            old_email.id,
        )


def store_received_mail(
    db: Session,
    settings: Settings,
    parsed_mail: ParsedMail,
    raw_message: bytes,
) -> Email:
    mailbox = _find_mailbox(db, parsed_mail.receiver)
    if mailbox is None:
        mail_logger.warning("Recipient mailbox not found or disabled receiver=%s", parsed_mail.receiver)
        raise MailboxNotFoundError("收件邮箱不存在或已停用")
    eml_path = _save_eml(raw_message, settings.data_dir)
    saved_attachments = []
    email = Email(
        mailbox_id=mailbox.id,
        sender=parsed_mail.sender,
        receiver=parsed_mail.receiver,
        subject=parsed_mail.subject,
        body_text=parsed_mail.body_text,
        body_html=parsed_mail.body_html,
        verification_code=extract_verification_code(
            parsed_mail.subject, parsed_mail.body_text, parsed_mail.body_html
        ),
        is_read=False,
        eml_path=str(eml_path),
        message_date=parsed_mail.message_date,
        received_at=parsed_mail.received_at,
    )
    db.add(email)
    try:
        db.flush()
        saved_attachments = save_relevant_attachments(db, settings, email, parsed_mail.attachments)
        _cleanup_mailbox(db, mailbox, settings)
        db.commit()
        db.refresh(email)
    except Exception as exc:
        db.rollback()
        eml_path.unlink(missing_ok=True)
        for attachment in saved_attachments:
            Path(attachment.file_path).unlink(missing_ok=True)
        mail_logger.error("Mail database save failed receiver=%s", parsed_mail.receiver, exc_info=True)
        raise MailReceiveError("邮件保存失败") from exc
    mail_logger.info(
        "Receive mail from=%s to=%s email_id=%s",
        email.sender,
        email.receiver,
        email.id,
    )
    return email
